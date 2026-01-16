# Copyright 2024 Wokwy - quochuy.software@gmail.com
import requests
from datetime import timedelta
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ZaloZnsConfig(models.Model):
    _name = 'zalo.zns.config'
    _description = 'Zalo ZNS Configuration'

    name = fields.Char(string='Configuration Name', required=True, default='Default Configuration')
    app_id = fields.Char(string='App ID', required=True)
    secret_key = fields.Char(string='Secret Key (App Secret)', required=True, groups="base.group_system")
    token_endpoint = fields.Char(string='Token Refresh Endpoint', required=True,
                                 default='https://oauth.zaloapp.com/v4/oa/access_token')
    auth_endpoint = fields.Char(
        string='Authorization Endpoint',
        required=True,
        default='https://oauth.zaloapp.com/v4/oa/permission'
    )
    api_url = fields.Char(string='API URL', required=True, default='https://business.openapi.zalo.me')
    access_token = fields.Char(string='Access Token', required=True)
    refresh_token = fields.Char(string='Refresh Token')
    token_expiry_date = fields.Datetime(string='Access Token Expiry')

    @api.model
    def get_config(self):
        config = self.search([], limit=1)
        if not config:
            # Cập nhật giá trị mặc định bao gồm các trường mới
            config = self.create({
                'name': 'Default Configuration',
                'api_url': 'https://business.openapi.zalo.me/message/template',
                'token_endpoint': 'https://oauth.zaloapp.com/v4/oa/access_token',
                'auth_endpoint': 'https://oauth.zaloapp.com/v4/oa/permission',
                'app_id': 'YOUR_ZALO_APP_ID',
                'secret_key': 'YOUR_ZALO_SECRET_KEY',
                'access_token': 'Default Token',
                'refresh_token': 'Default Refresh Token'
            })
        return config

    def _call_zalo_refresh_token_api(self):
        """ Thực hiện cuộc gọi API thực tế đến Zalo để làm mới token. """
        self.ensure_one()

        payload = {
            'app_id': self.app_id,
            'refresh_token': self.refresh_token,
            'grant_type': 'refresh_token'
        }

        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'secret_key': self.secret_key,
        }

        try:
            response = requests.post(self.token_endpoint, data=payload, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()

            if data.get('error'):
                raise UserError(_("Lỗi Zalo API khi làm mới token: %(error_msg)s (Mã lỗi: %(error_code)s)") % {
                    'error_msg': data.get('error_description', 'Không rõ'),
                    'error_code': data.get('error', 'N/A')
                })

            expires_in = data.get('expires_in', 3600)
            try:
                expires_in = int(expires_in)
            except (ValueError, TypeError):
                expires_in = 3600

            expiry_datetime = fields.Datetime.now() + timedelta(seconds=expires_in)

            self.write({
                'access_token': data.get('access_token'),
                'refresh_token': data.get('refresh_token'),
                'token_expiry_date': expiry_datetime,
            })

            return data.get('access_token')

        except requests.exceptions.RequestException as e:
            raise UserError(_("Không thể kết nối đến Zalo API: %s") % str(e))
        except Exception as e:
            raise UserError(_("Đã xảy ra lỗi khi làm mới Access Token: %s") % str(e))

    def action_refresh_access_token(self):
        """ Phương thức được gọi từ giao diện để làm mới Access Token. """
        self.ensure_one()

        if not self.refresh_token:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Lỗi',
                    'message': 'Không có Refresh Token. Vui lòng lấy Refresh Token trước.',
                    'sticky': True,
                }
            }

        try:
            new_token = self._call_zalo_refresh_token_api()

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Thành công',
                    'message': 'Access Token và Refresh Token đã được làm mới.',
                    'type': 'success',
                    'sticky': False,
                    'next': {'type': 'ir.actions.client', 'tag': 'reload'},
                }
            }
        except UserError as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Lỗi',
                    'message': str(e),
                    'type': 'danger',
                    'sticky': True,
                }
            }
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Lỗi không xác định',
                    'message': f'Đã xảy ra lỗi: {str(e)}',
                    'type': 'danger',
                    'sticky': True,
                }
            }

    def action_authorize_zalo(self):
        """ Tạo URL và chuyển hướng người dùng đến trang cấp quyền của Zalo """
        self.ensure_one()
        if not self.app_id:
            raise UserError(_("Vui lòng nhập App ID trước khi lấy Token."))

        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        redirect_uri = f"{base_url}/zalo/callback"

        # URL của Zalo dành cho OA (Official Account)
        zalo_auth_url = (
            f"{self.auth_endpoint}"
            f"?app_id={self.app_id}"
            f"&redirect_uri={redirect_uri}"
        )

        return {
            'type': 'ir.actions.act_url',
            'url': zalo_auth_url,
            'target': 'new',  # Mở tab mới để tránh bị mất trang hiện tại
        }