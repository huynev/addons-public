# -*- coding: utf-8 -*-
from odoo import models, api
from odoo.http import request


class PosConfig(models.Model):
    _inherit = "pos.config"

    @api.model
    def get_direct_login_employee(self):
        """Trả về employee_id được lưu khi user đăng nhập qua /pos-login.

        Key 'pos_direct_login_employee_id' được set trong HTTP session
        bởi controller sau khi xác thực PIN thành công.
        Xóa key ngay sau khi đọc để tránh dùng lại.
        """
        if not request:
            return {"employee_id": False}

        employee_id = request.session.pop("pos_direct_login_employee_id", False)
        return {"employee_id": employee_id}
