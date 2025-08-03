from odoo import models, fields, api
from odoo.exceptions import ValidationError

class AllowanceType(models.Model):
    _name = 'salary.allowance.type'
    _description = 'Loại Phụ Cấp Lương'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Tên Loại Phụ Cấp',
        required=True,
        tracking=True
    )
    code = fields.Char(
        string='Mã',
        required=True,
        tracking=True,
        copy=False
    )
    description = fields.Text(
        string='Mô Tả Chi Tiết'
    )
    active = fields.Boolean(
        string='Đang Hoạt Động',
        default=True
    )
    is_taxable = fields.Boolean(
        string='Chịu Thuế',
        default=True,
        help='Đánh dấu nếu phụ cấp này chịu thuế thu nhập cá nhân'
    )
    is_fixed = fields.Boolean(
        string='Giá Trị Cố Định',
        default=False,
        help='Đánh dấu nếu phụ cấp này có giá trị cố định cho mọi nhân viên'
    )
    default_amount = fields.Monetary(
        string='Giá Trị Mặc Định',
        currency_field='company_currency_id',
        help='Giá trị mặc định cho phụ cấp này'
    )
    company_currency_id = fields.Many2one(
        'res.currency',
        string='Đơn vị tiền tệ',
        default=lambda self: self.env.company.currency_id
    )
    allowance_ids = fields.One2many(
        'salary.allowance',
        'allowance_type_id',
        string='Các Đăng Ký Phụ Cấp'
    )
    allowance_count = fields.Integer(
        string='Số Lần Đăng Ký',
        compute='_compute_allowance_count'
    )

    @api.depends('allowance_ids')
    def _compute_allowance_count(self):
        """Tính số lần đăng ký cho mỗi loại phụ cấp"""
        for record in self:
            record.allowance_count = len(record.allowance_ids)

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

    def action_view_allowances(self):
        """Xem các đăng ký phụ cấp của loại này"""
        return {
            'name': f'Đăng Ký {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'salary.allowance',
            'view_mode': 'tree,form',
            'domain': [('allowance_type_id', '=', self.id)],
            'context': {
                'default_allowance_type_id': self.id,
            }
        }

    def toggle_active(self):
        """Chuyển đổi trạng thái hoạt động"""
        for record in self:
            record.active = not record.active

    def action_open_mass_allowance_wizard(self):
        """Mở wizard đăng ký phụ cấp hàng loạt với loại phụ cấp được chọn sẵn"""
        self.ensure_one()

        # Lấy view_id của form wizard
        view = self.env.ref('hr_salary_allowance.view_mass_allowance_wizard_form')

        # Tạo context mới thay vì sử dụng context hiện tại
        # Điều này tránh việc truyền active_ids không mong muốn
        context = {
            'default_allowance_type_id': self.id,
        }

        # Nếu là loại phụ cấp cố định, truyền luôn số tiền mặc định
        if self.is_fixed and self.default_amount:
            context.update({
                'default_amount': self.default_amount
            })

        # Lấy action
        action = {
            'name': 'Đăng Ký Phụ Cấp Hàng Loạt',
            'type': 'ir.actions.act_window',
            'res_model': 'mass.allowance.wizard',
            'view_mode': 'form',
            'view_id': view.id,
            'target': 'new',
            'context': context
        }

        return action