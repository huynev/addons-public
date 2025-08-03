from odoo import models, fields, api
from odoo.exceptions import ValidationError


class SalaryAllowance(models.Model):
    _name = 'salary.allowance'
    _description = 'Salary Allowance Registration'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Tên phụ cấp', readonly=True, compute="_compute_name", store=True)
    employee_id = fields.Many2one('hr.employee', string='Nhân viên', required=True)

    allowance_type_id = fields.Many2one(
        'salary.allowance.type',
        string='Loại Phụ Cấp',
        required=True
    )

    # Số tiền phụ cấp
    amount = fields.Monetary(
        string='Số tiền phụ cấp',
        currency_field='company_currency_id',
        required=True
    )

    # Ngày đăng ký, bắt đầu, kết thúc
    registration_date = fields.Date(string='Ngày đăng ký', default=fields.Date.today)
    start_date = fields.Date(string='Ngày bắt đầu', required=True)
    end_date = fields.Date(string='Ngày kết thúc')

    # Trạng thái
    state = fields.Selection([
        ('draft', 'Dự thảo'),
        ('confirmed', 'Đã xác nhận'),
        ('suspended', 'Tạm dừng'),
        ('closed', 'Đóng'),
    ], string='Trạng thái', default='draft', tracking=True)

    # Thông tin bổ sung
    is_taxable = fields.Boolean(
        string='Chịu thuế',
        related='allowance_type_id.is_taxable',
        store=True,
        readonly=True
    )

    notes = fields.Text(string='Ghi chú')

    # Các trường kế toán
    company_currency_id = fields.Many2one(
        'res.currency',
        string='Đơn vị tiền tệ',
        default=lambda self: self.env.company.currency_id
    )

    # Lịch sử thay đổi
    history_ids = fields.One2many(
        'salary.allowance.history',
        'allowance_id',
        string='Lịch sử thay đổi'
    )

    @api.depends('employee_id', 'allowance_type_id')
    def _compute_name(self):
        """
        Tự động tạo tên phụ cấp từ mã nhân viên và tên loại phụ cấp
        """
        for record in self:
            if record.employee_id and record.allowance_type_id:
                employee_code = record.employee_id.employee_code or record.employee_id.identification_id or f"NV{record.employee_id.id}"
                record.name = f"{employee_code}-{record.allowance_type_id.name}"
            else:
                record.name = "Phụ cấp mới"

    @api.model
    def create(self, vals):
        """
        Tạo bản ghi mới và lịch sử
        """
        record = super().create(vals)
        record._create_history_entry()
        return record

    def write(self, vals):
        """
        Cập nhật bản ghi và lịch sử nếu có thay đổi
        """
        result = super().write(vals)
        self._create_history_entry()
        return result

    def _create_history_entry(self):
        """Tạo mục lịch sử thay đổi"""
        for record in self:
            self.env['salary.allowance.history'].create({
                'allowance_id': record.id,
                'start_date': record.start_date,
                'amount': record.amount,
            })

    def action_confirm(self):
        """Xác nhận đăng ký"""
        self.write({'state': 'confirmed'})

    def action_suspend(self):
        """Tạm dừng"""
        self.write({'state': 'suspended'})

    def action_close(self):
        """Đóng đăng ký"""
        self.write({'state': 'closed', 'end_date': fields.Date.today()})

    @api.onchange('allowance_type_id')
    def _onchange_allowance_type(self):
        """
        Tự động điền số tiền mặc định từ loại phụ cấp được chọn nếu có
        """
        if self.allowance_type_id and self.allowance_type_id.is_fixed:
            self.amount = self.allowance_type_id.default_amount

    def generate_allowance_report(self, date_from, date_to):
        """
        Tạo báo cáo tổng hợp phụ cấp
        """
        domain = [
            ('state', '=', 'confirmed'),
            ('start_date', '>=', date_from),
            ('start_date', '<=', date_to)
        ]

        allowances = self.search(domain)

        report_data = {
            'total_employees': len(allowances.mapped('employee_id')),
            'total_amount': sum(allowances.mapped('amount')),
            'total_taxable_amount': sum(allowances.filtered('is_taxable').mapped('amount')),
            'total_non_taxable_amount': sum(allowances.filtered(lambda a: not a.is_taxable).mapped('amount')),
            'allowances': []
        }

        for allowance in allowances:
            report_data['allowances'].append({
                'employee': allowance.employee_id.name,
                'type': allowance.allowance_type_id.name,
                'amount': allowance.amount,
                'is_taxable': allowance.is_taxable
            })

        return report_data


class SalaryAllowanceHistory(models.Model):
    _name = 'salary.allowance.history'
    _description = 'Salary Allowance History'

    allowance_id = fields.Many2one('salary.allowance', string='Đăng ký phụ cấp')
    start_date = fields.Date(string='Ngày bắt đầu')
    end_date = fields.Date(string='Ngày kết thúc')
    amount = fields.Monetary(string='Số tiền phụ cấp', currency_field='company_currency_id')
    company_currency_id = fields.Many2one(
        'res.currency',
        string='Đơn vị tiền tệ',
        default=lambda self: self.env.company.currency_id
    )