# hr_employee.py
from odoo import models, fields, api


class HREmployee(models.Model):
    _inherit = 'hr.employee'

    salary_contribution_ids = fields.One2many(
        'salary.contribution',
        'employee_id',
        string='Đăng ký đóng góp từ lương'
    )

    # Thêm trường tính toán số lượng đóng góp
    salary_contribution_count = fields.Integer(
        string='Số lượng đóng góp',
        compute='_compute_salary_contribution_count'
    )

    @api.depends('salary_contribution_ids')
    def _compute_salary_contribution_count(self):
        """
        Tính toán số lượng đóng góp cho mỗi nhân viên
        """
        for employee in self:
            employee.salary_contribution_count = len(employee.salary_contribution_ids)

    def action_view_salary_contributions(self):
        """
        Xem các đăng ký đóng góp của nhân viên
        """
        self.ensure_one()
        return {
            'name': 'Đóng góp từ lương',
            'type': 'ir.actions.act_window',
            'res_model': 'salary.contribution',
            'view_mode': 'tree,form',
            'domain': [('employee_id', '=', self.id)],
            'context': {
                'default_employee_id': self.id,
            }
        }