import requests
from datetime import timedelta
from odoo import http, fields
from odoo.http import request


class ZaloAuthController(http.Controller):

    @http.route('/zalo/callback', type='http', auth='public')
    def zalo_callback(self, **kw):
        config = request.env['zalo.zns.config'].sudo().get_config()
        if not config.app_id:
            return "Vui lòng cấu hình App ID trong Odoo trước!"

        code = kw.get('code')

        # Thông tin App
        app_id = config.app_id
        app_secret = config.secret_key

        response = requests.post(
            config.token_endpoint,
            headers={"secret_key": app_secret, "Content-Type": "application/x-www-form-urlencoded"},
            data={
                "app_id": app_id,
                "code": code,
                "grant_type": "authorization_code",
            }
        )
        data = response.json()

        if 'access_token' in data:
            expires_in = data.get('expires_in', 3600)
            try:
                expires_in = int(expires_in)
            except (ValueError, TypeError):
                expires_in = 3600

            expiry_datetime = fields.Datetime.now() + timedelta(seconds=expires_in)
            config = request.env['zalo.zns.config'].sudo().get_config()
            config.write({
                'access_token': data['access_token'],
                'refresh_token': data.get('refresh_token'),
                'token_expiry_date': expiry_datetime,
            })
            return """
                    <script type="text/javascript">
                        alert("Kết nối Zalo thành công! Hệ thống sẽ quay về trang danh sách cấu hình.");
                        if (window.opener) {
                            // Reload lại tab cha và chuyển hướng tới view list
                            window.opener.location.href = '/web#model=zalo.zns.config&view_type=list';
                            // Đóng tab hiện tại (tab Zalo callback)
                            window.close();
                        } else {
                            // Nếu không tìm thấy tab cha, chuyển hướng ngay tại tab này
                            window.location.href = '/web#model=zalo.zns.config&view_type=list&notif=success';
                        }
                    </script>
                """
        return f"Lỗi: {data.get('error_description')}"