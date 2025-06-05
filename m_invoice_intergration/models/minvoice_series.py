from odoo import models, fields, api
import requests
from odoo.exceptions import ValidationError


class MInvoiceSeries(models.Model):
    _name = 'minvoice.series'
    _description = 'M-Invoice Series'
    _rec_name = 'khhdon'

    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    series_id = fields.Char('Series ID', required=True)
    value = fields.Char('Value', required=True)
    khhdon = fields.Char('Ký hiệu hóa đơn', required=True)
    invoice_form = fields.Selection([
        ('1', 'Hóa đơn giá trị gia tăng'),
        ('2', 'Hóa đơn bán hàng'),
        ('3', 'Hóa đơn bán tài sản công'),
        ('4', 'Hóa đơn bán hàng dự trữ quốc gia'),
        ('5', 'Tem vé thẻ'),
        ('6', 'Phiếu xuất kho'),
    ], string='Loại hóa đơn', required=True)
    invoice_year = fields.Char('Năm ký hiệu')
    invoice_type_name = fields.Char('Tên loại hóa đơn')
    active = fields.Boolean('Active', default=True)

    @api.model
    def sync_series_from_minvoice(self, company_id=None):
        """Đồng bộ ký hiệu hóa đơn từ M-Invoice"""
        if not company_id:
            company_id = self.env.company.id

        config = self.env['minvoice.config'].get_config(company_id)
        token = config.get_valid_token()

        url = f"{config.base_url}/api/Invoice68/GetTypeInvoiceSeries"
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }

        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()

            result = response.json()
            if result.get('code') == '00' and result.get('ok'):
                series_data = result.get('data', [])

                for series in series_data:
                    existing = self.search([
                        ('company_id', '=', company_id),
                        ('series_id', '=', series.get('id'))
                    ])

                    vals = {
                        'company_id': company_id,
                        'series_id': series.get('id'),
                        'value': series.get('value'),
                        'khhdon': series.get('khhdon'),
                        'invoice_form': series.get('invoiceForm'),
                        'invoice_year': series.get('invoiceYear'),
                        'invoice_type_name': series.get('invoiceTypeName'),
                    }

                    if existing:
                        existing.write(vals)
                    else:
                        self.create(vals)

                return len(series_data)
            else:
                raise ValidationError(f"Lỗi lấy ký hiệu hóa đơn: {result.get('message', 'Unknown error')}")

        except requests.exceptions.RequestException as e:
            raise ValidationError(f"Lỗi kết nối M-Invoice: {str(e)}")