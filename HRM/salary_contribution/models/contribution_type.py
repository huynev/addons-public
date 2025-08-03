from odoo import models, fields, api
from odoo.exceptions import ValidationError

class ContributionType(models.Model):
    _name = 'salary.contribution.type'
    _description = 'Loại Đóng Góp Từ Lương'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Tên Loại Đóng Góp',
        required=True,
        tracking=True
    )
    code = fields.Char(
        string='Mã',
        required=True,
        tracking=True,
        copy=False
    )
    employee_contribution_rate = fields.Float(
        string='Tỷ Lệ Đóng Góp Nhân Viên (%)',
        default=0.0,
        tracking=True
    )
    company_contribution_rate = fields.Float(
        string='Tỷ Lệ Đóng Góp Công Ty (%)',
        default=0.0,
        tracking=True
    )
    description = fields.Text(
        string='Mô Tả Chi Tiết'
    )
    active = fields.Boolean(
        string='Đang Hoạt Động',
        default=True
    )
    max_unpaid_days = fields.Integer(
        string='Số Ngày Không Hưởng Lương Tối Đa',
        default=14
    )
    contribution_ids = fields.One2many(
        'salary.contribution',
        'contribution_type_id',
        string='Các Đăng Ký Đóng Góp'
    )
    contribution_count = fields.Integer(
        string='Số Lần Đăng Ký',
        compute='_compute_contribution_count'
    )

    @api.depends('contribution_ids')
    def _compute_contribution_count(self):
        """Tính số lần đăng ký cho mỗi loại đóng góp"""
        for record in self:
            record.contribution_count = len(record.contribution_ids)

    @api.constrains('code')
    def _check_unique_code(self):
        """Đảm bảo mã là duy nhất"""
        for record in self:
            existing = self.search([
                ('code', '=', record.code),
                ('id', '!=', record.id)
            ])
            if existing:
                raise ValidationError(f"Mã '{record.code}' đã tồn tại. Vui lòng chọn mã khác.")

    def action_view_contributions(self):
        """Xem các đăng ký đóng góp của loại này"""
        return {
            'name': f'Đăng Ký {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'salary.contribution',
            'view_mode': 'tree,form',
            'domain': [('contribution_type_id', '=', self.id)],
            'context': {
                'default_contribution_type_id': self.id,
            }
        }

    def toggle_active(self):
        """Chuyển đổi trạng thái hoạt động"""
        for record in self:
            record.active = not record.active

    def action_register_contribution(self):
        """Mở wizard đăng ký đóng góp từ loại đóng góp"""
        self.ensure_one()
        return {
            'name': 'Đăng Ký Đóng Góp',
            'type': 'ir.actions.act_window',
            'res_model': 'salary.contribution.register.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_contribution_type_id': self.id,
                'default_employee_contribution_rate': self.employee_contribution_rate,
                'default_company_contribution_rate': self.company_contribution_rate,
                'default_max_unpaid_days': self.max_unpaid_days,
            }
        }