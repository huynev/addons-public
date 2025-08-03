# hr_employee.py
from odoo import models, fields, api


class HREmployee(models.Model):
    _inherit = 'hr.employee'

    salary_allowance_ids = fields.One2many(
        'salary.allowance',
        'employee_id',
        string='Đăng ký phụ cấp lương'
    )

    # Thêm trường tính toán số lượng phụ cấp
    salary_allowance_count = fields.Integer(
        string='Số lượng phụ cấp',
        compute='_compute_salary_allowance_count'
    )

    @api.depends('salary_allowance_ids')
    def _compute_salary_allowance_count(self):
        """
        Tính toán số lượng phụ cấp cho mỗi nhân viên
        """
        for employee in self:
            employee.salary_allowance_count = len(employee.salary_allowance_ids)

    def action_view_salary_allowances(self):
        """
        Xem các đăng ký phụ cấp của nhân viên
        """
        self.ensure_one()
        return {
            'name': 'Phụ cấp lương',
            'type': 'ir.actions.act_window',
            'res_model': 'salary.allowance',
            'view_mode': 'tree,form',
            'domain': [('employee_id', '=', self.id)],
            'context': {
                'default_employee_id': self.id,
            }
        }