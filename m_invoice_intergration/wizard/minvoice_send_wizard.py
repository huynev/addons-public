from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class MInvoiceSendWizard(models.TransientModel):
    _name = 'minvoice.send.wizard'
    _description = 'Send Invoice to M-Invoice Wizard'

    invoice_id = fields.Many2one('account.move', string='Invoice', required=True)
    company_id = fields.Many2one('res.company', string='Company', related='invoice_id.company_id', readonly=True)
    series_id = fields.Many2one(
        'minvoice.series',
        string='Ký hiệu hóa đơn',
        required=True,
        domain="[('company_id', '=', company_id), ('active', '=', True)]"
    )
    auto_sign = fields.Boolean('Tự động ký và gửi', default=False)

    def action_send(self):
        """Gửi hóa đơn lên M-Invoice"""
        if not self.invoice_id or not self.series_id:
            raise ValidationError(_('Vui lòng chọn hóa đơn và ký hiệu'))

        # Cập nhật ký hiệu cho hóa đơn
        self.invoice_id.minvoice_series_id = self.series_id

        # ✅ THÊM: Kiểm tra xem là tạo mới hay update
        is_update = bool(self.invoice_id.minvoice_id)
        action_text = "cập nhật" if is_update else "tạo"

        # Chuẩn bị dữ liệu
        invoice_data = self.invoice_id._prepare_minvoice_data()

        try:
            # Tạo hoặc cập nhật hóa đơn trên M-Invoice
            minvoice_api = self.env['minvoice.api']
            result = minvoice_api.create_invoice(invoice_data, self.invoice_id.company_id.id)

            # ✅ CẬP NHẬT: Cập nhật thông tin M-Invoice với trạng thái mới
            update_vals = {
                'minvoice_status': 'pending',
                'minvoice_error_message': False,
            }

            # Nếu là tạo mới hoặc có thông tin mới từ response
            if not is_update or result.get('hoadon68_id'):
                if result.get('hoadon68_id'):
                    update_vals['minvoice_id'] = result.get('hoadon68_id')
                if result.get('inv_invoiceNumber'):
                    update_vals['minvoice_number'] = result.get('inv_invoiceNumber')
                if result.get('sobaomat'):
                    update_vals['minvoice_code'] = result.get('sobaomat')

            self.invoice_id.write(update_vals)

            # Tự động ký và gửi nếu được chọn
            if self.auto_sign and self.invoice_id.minvoice_id:
                success = minvoice_api.sign_and_send_invoice(
                    self.invoice_id.minvoice_id,
                    self.invoice_id.company_id.id
                )
                if success:
                    # ✅ CẬP NHẬT: Sau khi ký thành công, trạng thái sẽ là 'signed' (Đã ký)
                    self.invoice_id.minvoice_status = 'signed'

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _('Hóa đơn đã được {} trên M-Invoice thành công!').format(action_text),
                    'type': 'success'
                }
            }

        except Exception as e:
            self.invoice_id.write({
                'minvoice_status': 'error',
                'minvoice_error_message': str(e)
            })
            raise ValidationError(str(e))