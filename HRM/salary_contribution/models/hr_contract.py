from odoo import models, fields, api

class HRContract(models.Model):
    _inherit = 'hr.contract'

    salary_contribution_ids = fields.One2many(
        'salary.contribution',
        'employee_id',
        string='Đăng Ký Đóng Góp',
        related='employee_id.salary_contribution_ids',
        readonly=True
    )

    wage_social_insurance = fields.Monetary('Lương đóng BHXH', required=True, tracking=True, help="Đây là mức lương dùng đóng BHXH",
                           group_operator="avg")

    def action_view_salary_contributions(self):
        """
        Xem các đăng ký đóng góp của nhân viên
        """
        self.ensure_one()
        return {
            'name': 'Đóng Góp Từ Lương',
            'type': 'ir.actions.act_window',
            'res_model': 'salary.contribution',
            'view_mode': 'tree,form',
            'domain': [('employee_id', '=', self.employee_id.id)],
            'context': {
                'default_employee_id': self.employee_id.id,
            }
        }