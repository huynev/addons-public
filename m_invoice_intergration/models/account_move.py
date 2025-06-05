from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class AccountMove(models.Model):
    _inherit = 'account.move'

    # M-Invoice fields
    minvoice_series_id = fields.Many2one('minvoice.series', string='Ký hiệu hóa đơn')
    minvoice_number = fields.Char('Số hóa đơn M-Invoice', readonly=True)
    minvoice_id = fields.Char('M-Invoice ID', readonly=True)
    minvoice_status = fields.Selection([
        ('draft', 'Nháp'),
        ('waiting', 'Chờ ký'),
        ('signed', 'Đã ký'),
        ('sent', 'Đã gửi'),
        ('success', 'Thành công'),
        ('error', 'Lỗi'),
        ('rejected', 'Từ chối'),
    ], string='Trạng thái M-Invoice', readonly=True)
    minvoice_code = fields.Char('Mã tra cứu', readonly=True)
    minvoice_cqt_code = fields.Char('Mã CQT', readonly=True)
    minvoice_error_message = fields.Text('Thông báo lỗi', readonly=True)
    minvoice_xml_file = fields.Binary('File XML', readonly=True)
    minvoice_pdf_file = fields.Binary('File PDF', readonly=True)

    def action_send_to_minvoice(self):
        """Gửi hóa đơn lên M-Invoice"""
        if self.move_type not in ['out_invoice', 'out_refund']:
            raise ValidationError(_('Chỉ có thể gửi hóa đơn bán hàng lên M-Invoice'))

        default_series_id = False
        if self.minvoice_series_id:
            default_series_id = self.minvoice_series_id.id
        else:
            # Tìm ký hiệu mặc định cho công ty
            default_series = self.env['minvoice.series'].search([
                ('company_id', '=', self.company_id.id),
                ('active', '=', True),
                ('invoice_form', '=', '1')  # Hóa đơn GTGT
            ], limit=1)
            if default_series:
                default_series_id = default_series.id

        return {
            'type': 'ir.actions.act_window',
            'name': _('Gửi hóa đơn lên M-Invoice'),
            'res_model': 'minvoice.send.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_invoice_id': self.id,
                'default_series_id': default_series_id,
            }
        }

    def action_minvoice_print(self):
        """In hóa đơn từ M-Invoice"""
        if not self.minvoice_id:
            raise ValidationError(_('Hóa đơn chưa được gửi lên M-Invoice'))

        minvoice_api = self.env['minvoice.api']
        pdf_data = minvoice_api.print_invoice(self.minvoice_id, self.company_id.id)

        if pdf_data:
            self.minvoice_pdf_file = pdf_data

            return {
                'type': 'ir.actions.act_url',
                'url': f'/web/content/account.move/{self.id}/minvoice_pdf_file/invoice_{self.name}.pdf',
                'target': 'new',
            }

    def action_minvoice_get_xml(self):
        """Lấy file XML từ M-Invoice"""
        if not self.minvoice_id:
            raise ValidationError(_('Hóa đơn chưa được gửi lên M-Invoice'))

        minvoice_api = self.env['minvoice.api']
        xml_data = minvoice_api.get_xml_file(self.minvoice_id, self.company_id.id)

        if xml_data:
            self.minvoice_xml_file = xml_data

            return {
                'type': 'ir.actions.act_url',
                'url': f'/web/content/account.move/{self.id}/minvoice_xml_file/invoice_{self.name}.xml',
                'target': 'new',
            }

    def action_minvoice_cancel(self):
        """Hủy hóa đơn trên M-Invoice"""
        if not self.minvoice_id:
            raise ValidationError(_('Hóa đơn chưa được gửi lên M-Invoice'))

        if self.minvoice_status not in ['success']:
            raise ValidationError(_('Chỉ có thể hủy hóa đơn đã thành công'))

        # TODO: Implement cancel logic
        pass

    def _prepare_minvoice_data(self):
        """Chuẩn bị dữ liệu gửi lên M-Invoice"""
        if not self.partner_id:
            raise ValidationError(_('Vui lòng chọn khách hàng'))

        # Thông tin đầu phiếu
        data = {
            'editmode': '1',  # Thêm mới
            'data': [{
                'inv_invoiceIssuedDate': self.invoice_date.strftime('%Y-%m-%d'),
                'inv_invoiceSeries': self.minvoice_series_id.value,
                'inv_currencyCode': self.currency_id.name or 'VND',
                'inv_exchangeRate': 1.0 if self.currency_id.name == 'VND' else self.currency_id.rate,

                # Thông tin khách hàng
                'inv_buyerDisplayName': self.partner_id.name,
                'inv_buyerLegalName': self.partner_id.name if self.partner_id.vat else '',
                'inv_buyerTaxCode': self.partner_id.vat or '',
                'inv_buyerAddressLine': self._get_partner_address(),
                'inv_buyerEmail': self.partner_id.email or '',

                # Thông tin thanh toán
                'inv_paymentMethodName': self._get_payment_method(),

                # Tổng tiền
                'inv_TotalAmountWithoutVat': self.amount_untaxed,
                'inv_vatAmount': self.amount_tax,
                'inv_TotalAmount': self.amount_total,
                'inv_discountAmount': 0,  # TODO: Calculate discount

                # Chi tiết hàng hóa
                'details': self._prepare_invoice_lines()
            }]
        }

        return data

    def _get_partner_address(self):
        """Lấy địa chỉ khách hàng"""
        address_parts = []
        if self.partner_id.street:
            address_parts.append(self.partner_id.street)
        if self.partner_id.street2:
            address_parts.append(self.partner_id.street2)
        if self.partner_id.city:
            address_parts.append(self.partner_id.city)
        if self.partner_id.state_id:
            address_parts.append(self.partner_id.state_id.name)
        if self.partner_id.country_id:
            address_parts.append(self.partner_id.country_id.name)

        return ', '.join(address_parts)

    def _get_payment_method(self):
        """Lấy hình thức thanh toán"""
        # TODO: Map payment terms to M-Invoice payment methods
        return 'TM/CK'

    def _prepare_invoice_lines(self):
        """Chuẩn bị chi tiết hàng hóa"""
        lines = []
        for i, line in enumerate(self.invoice_line_ids.filtered(lambda l: l.display_type == 'product'), 1):
            tax_rate = self._get_tax_rate(line)
            line_data = {
                'tchat': 1,  # Hàng hóa dịch vụ
                'stt_rec0': f"{i:04d}",
                'inv_itemCode': line.product_id.default_code or '',
                'inv_itemName': line.name,
                'inv_unitCode': line.product_uom_id.name or 'Cái',
                'inv_quantity': line.quantity,
                'inv_unitPrice': line.price_unit,
                'inv_discountPercentage': line.discount,
                'inv_discountAmount': line.price_unit * line.quantity * line.discount / 100,
                'inv_TotalAmountWithoutVat': line.price_subtotal,
                'ma_thue': str(int(tax_rate)) if tax_rate >= 0 else str(int(tax_rate)),
                'inv_vatAmount': line.price_total - line.price_subtotal,
                'inv_TotalAmount': line.price_total,
            }
            lines.append(line_data)

        return lines

    def _get_tax_rate(self, line):
        """Lấy thuế suất của dòng hàng"""
        if not line.tax_ids:
            return -1  # Không chịu thuế

        for tax in line.tax_ids:
            if tax.type_tax_use == 'sale' and tax.amount_type == 'percent':
                return tax.amount

        return 0