from odoo import models, fields, api

class HRContract(models.Model):
    _inherit = 'hr.contract'

    salary_allowance_ids = fields.One2many(
        'salary.allowance',
        'employee_id',
        string='Đăng Ký Phụ Cấp',
        related='employee_id.salary_allowance_ids',
        readonly=True
    )

    def action_view_salary_allowances(self):
        """
        Xem các đăng ký phụ cấp của nhân viên
        """
        self.ensure_one()
        return {
            'name': 'Phụ Cấp Lương',
            'type': 'ir.actions.act_window',
            'res_model': 'salary.allowance',
            'view_mode': 'tree,form',
            'domain': [('employee_id', '=', self.employee_id.id)],
            'context': {
                'default_employee_id': self.employee_id.id,
            }
        }