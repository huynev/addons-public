from datetime import timedelta
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import requests
import json


class MInvoiceConfig(models.Model):
    _name = 'minvoice.config'
    _description = 'M-Invoice Configuration'
    _rec_name = 'company_id'

    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    base_url = fields.Char('Base URL', required=True, default='https://0106026495-999.minvoice.app')
    username = fields.Char('Username', required=True)
    password = fields.Char('Password', required=True)
    ma_dvcs = fields.Char('Mã đơn vị', default='VP')
    token = fields.Text('Access Token', readonly=True)
    token_expiry = fields.Datetime('Token Expiry', readonly=True)
    active = fields.Boolean('Active', default=True)

    @api.model
    def get_config(self, company_id=None):
        """Lấy cấu hình M-Invoice cho công ty"""
        if not company_id:
            company_id = self.env.company.id

        config = self.search([('company_id', '=', company_id), ('active', '=', True)], limit=1)
        if not config:
            raise ValidationError(_('Chưa cấu hình M-Invoice cho công ty này'))

        return config

    def action_test_connection(self):
        """Test kết nối với M-Invoice"""
        try:
            token = self.get_access_token()
            if token:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Success'),
                        'message': _('Kết nối M-Invoice thành công!'),
                        'type': 'success'
                    }
                }
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': str(e),
                    'type': 'danger'
                }
            }

    def get_access_token(self):
        """Lấy access token từ M-Invoice"""
        url = f"{self.base_url}/api/Account/Login"

        payload = {
            "username": self.username,
            "password": self.password,
            "ma_dvcs": self.ma_dvcs
        }

        headers = {
            'Content-Type': 'application/json'
        }

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()

            result = response.json()
            if result.get('code') == '00' and result.get('ok'):
                self.token = result.get('token')
                # Token có thời hạn (thường 24h), set expiry
                self.token_expiry = fields.Datetime.now() + timedelta(hours=24)
                return self.token
            else:
                raise ValidationError(f"Lỗi đăng nhập M-Invoice: {result.get('message', 'Unknown error')}")

        except requests.exceptions.RequestException as e:
            raise ValidationError(f"Lỗi kết nối M-Invoice: {str(e)}")

    def get_valid_token(self):
        """Lấy token hợp lệ, refresh nếu cần"""
        if not self.token or (self.token_expiry and self.token_expiry <= fields.Datetime.now()):
            return self.get_access_token()
        return self.token