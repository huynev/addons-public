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

        # Chuẩn bị dữ liệu
        invoice_data = self.invoice_id._prepare_minvoice_data()

        try:
            # Tạo hóa đơn trên M-Invoice
            minvoice_api = self.env['minvoice.api']
            result = minvoice_api.create_invoice(invoice_data, self.invoice_id.company_id.id)

            # Cập nhật thông tin M-Invoice
            self.invoice_id.write({
                'minvoice_id': result.get('hoadon68_id'),
                'minvoice_number': result.get('inv_invoiceNumber'),
                'minvoice_code': result.get('sobaomat'),
                'minvoice_status': 'waiting',
            })

            # Tự động ký và gửi nếu được chọn
            if self.auto_sign:
                success = minvoice_api.sign_and_send_invoice(
                    self.invoice_id.minvoice_id,
                    self.invoice_id.company_id.id
                )
                if success:
                    self.invoice_id.minvoice_status = 'signed'

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _('Hóa đơn đã được gửi lên M-Invoice thành công!'),
                    'type': 'success'
                }
            }

        except Exception as e:
            self.invoice_id.write({
                'minvoice_status': 'error',
                'minvoice_error_message': str(e)
            })
            raise ValidationError(str(e))