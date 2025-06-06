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

            filename = f"invoice_{self.name}.pdf".replace('/', '_')
            url = f"/web/content?model=account.move&id={self.id}&field=minvoice_pdf_file&filename={filename}&download=true"

            return {
                'type': 'ir.actions.act_url',
                'url': url,
                'target': 'new',
            }

    def action_minvoice_get_xml(self):
        """Lấy file XML từ M-Invoice"""
        if not self.minvoice_id:
            raise ValidationError(_('Hóa đơn chưa được gửi lên M-Invoice'))

        minvoice_api = self.env['minvoice.api']
        xml_data = minvoice_api.get_xml_file(self.minvoice_id, self.company_id.id)

        if xml_data:
            xml_data = xml_data.get('data')
            self.minvoice_xml_file = xml_data

            filename = f"invoice_{self.name}.xml".replace('/', '_')
            url = f"/web/content?model=account.move&id={self.id}&field=minvoice_xml_file&filename={filename}&download=true"

            return {
                'type': 'ir.actions.act_url',
                'url': url,
                'target': 'new',
            }
        else:
            raise ValidationError(_('Không thể lấy file XML từ M-Invoice'))

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

        # Logic kiểm tra hóa đơn đã tồn tại trên M-Invoice
        is_update = bool(self.minvoice_id)
        editmode = '2' if is_update else '1'  # 2: Sửa, 1: Thêm mới

        # Thông tin đầu phiếu
        data = {
            'editmode': editmode,
            'data': [{
                'inv_invoiceIssuedDate': self.invoice_date.strftime('%Y-%m-%d'),
                'inv_invoiceSeries': self.minvoice_series_id.value,
                'inv_currencyCode': self.currency_id.name or 'VND',
                'so_benh_an': self._get_sale_order_number(),
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

        # Nếu là update, thêm thông tin để M-Invoice biết cần sửa hóa đơn nào
        if is_update:
            if self.minvoice_number:
                # Trường hợp đã có số hóa đơn
                data['data'][0]['inv_invoiceNumber'] = int(self.minvoice_number)
            if self.minvoice_id:
                # Trường hợp có ID hóa đơn
                data['data'][0]['inv_invoiceAuth_Id'] = self.minvoice_id

        return data

    def _get_sale_order_number(self):
        """Lấy số đơn hàng từ Sale Order"""
        if self.invoice_origin:
            return self.invoice_origin

        if self.ref:
            return self.ref

        if self.partner_ref:
            return self.partner_ref

        return self.name

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
        """Lấy hình thức thanh toán từ Odoo và map sang M-Invoice"""

        # Mapping phương thức thanh toán Odoo -> M-Invoice
        payment_method_mapping = {
            # Từ Payment Terms Name
            'immediate payment': 'Tiền mặt',
            'cash': 'Tiền mặt',
            'tiền mặt': 'Tiền mặt',
            'cash on delivery': 'Tiền mặt',
            'cod': 'Tiền mặt',
            'bank transfer': 'Chuyển khoản',
            'chuyển khoản': 'Chuyển khoản',
            'transfer': 'Chuyển khoản',
            'wire transfer': 'Chuyển khoản',
            'credit card': 'Chuyển khoản',
            'thẻ tín dụng': 'Chuyển khoản',
            'online payment': 'Chuyển khoản',
            'electronic payment': 'Chuyển khoản',
            # Từ Payment Terms với thời hạn
            '15 days': 'Chuyển khoản',
            '30 days': 'Chuyển khoản',
            '45 days': 'Chuyển khoản',
            '60 days': 'Chuyển khoản',
            '90 days': 'Chuyển khoản',
        }

        # Ưu tiên 1: Lấy từ payment term của invoice
        if self.invoice_payment_term_id:
            term_name = self.invoice_payment_term_id.name.lower()

            # Kiểm tra exact match trước
            if term_name in payment_method_mapping:
                return payment_method_mapping[term_name]

            # Kiểm tra contains
            for key, value in payment_method_mapping.items():
                if key in term_name:
                    return value

            # Logic đặc biệt cho payment terms có số ngày
            if any(word in term_name for word in ['days', 'ngày', 'day']):
                return 'Chuyển khoản'
            elif any(word in term_name for word in ['immediate', 'ngay', 'cash']):
                return 'Tiền mặt'

        if hasattr(self, 'line_ids'):
            for line in self.line_ids:
                if line.account_id.account_type in ['asset_cash', 'asset_current']:
                    if 'cash' in line.account_id.name.lower() or 'tiền mặt' in line.account_id.name.lower():
                        return 'Tiền mặt'
                    elif 'bank' in line.account_id.name.lower() or 'ngân hàng' in line.account_id.name.lower():
                        return 'Chuyển khoản'

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

        return [{'data': lines}]

    def _get_tax_rate(self, line):
        """Lấy thuế suất của dòng hàng"""
        if not line.tax_ids:
            return -1  # Không chịu thuế

        for tax in line.tax_ids:
            if tax.type_tax_use == 'sale' and tax.amount_type == 'percent':
                return tax.amount

        return 0