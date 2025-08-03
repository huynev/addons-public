# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    employee_code = fields.Char(string='Mã nhân viên', required=True, copy=False, index=True)

    hire_date = fields.Date(string='Ngày vào làm',
                            tracking=True,
                            groups="hr.group_hr_user",
                            help="Ngày nhân viên bắt đầu làm việc")
    employment_duration = fields.Char(string='Thâm niên', compute='_compute_employment_duration')

    # Thêm trường mới để lưu số năm thâm niên
    employment_years = fields.Integer(string='Số năm thâm niên', compute='_compute_employment_years', store=True,
                                      help="Số năm thâm niên của nhân viên, dùng để tính phụ cấp thâm niên")

    _sql_constraints = [
        ('employee_code_unique', 'UNIQUE(employee_code)', 'Mã nhân viên đã tồn tại. Vui lòng chọn mã khác!')
    ]

    @api.constrains('employee_code')
    def _check_employee_code(self):
        for record in self:
            if record.employee_code:
                if len(record.employee_code) < 3:
                    raise ValidationError("Mã nhân viên phải có ít nhất 3 ký tự.")
                if not record.employee_code.isalnum():
                    raise ValidationError("Mã nhân viên chỉ được chứa chữ cái và số.")

    @api.depends('hire_date')
    def _compute_employment_duration(self):
        for employee in self:
            if employee.hire_date:
                today = fields.Date.today()
                delta = today - employee.hire_date
                years = delta.days // 365
                months = (delta.days % 365) // 30

                if years > 0 and months > 0:
                    employee.employment_duration = f"{years} năm {months} tháng"
                elif years > 0:
                    employee.employment_duration = f"{years} năm"
                elif months > 0:
                    employee.employment_duration = f"{months} tháng"
                else:
                    employee.employment_duration = f"{delta.days} ngày"
            else:
                employee.employment_duration = "Chưa có thông tin"

    @api.depends('hire_date')
    def _compute_employment_years(self):
        """Tính số năm thâm niên của nhân viên để dùng trong tính phụ cấp"""
        for employee in self:
            if employee.hire_date:
                today = fields.Date.today()
                delta = today - employee.hire_date
                # Chỉ lấy số năm làm tròn xuống
                employee.employment_years = delta.days // 365
            else:
                employee.employment_years = 0

    @api.model
    def update_all_employment_years(self):
        """Cập nhật số năm thâm niên cho tất cả nhân viên, được gọi từ cron job"""
        employees = self.search([('hire_date', '!=', False)])
        employees._compute_employment_years()
        return True