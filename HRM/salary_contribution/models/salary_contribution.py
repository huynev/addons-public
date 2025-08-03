from odoo import models, fields, api
from odoo.exceptions import ValidationError


class SalaryContribution(models.Model):
    _name = 'salary.contribution'
    _description = 'Salary Contribution Registration'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Tên đóng góp', readonly=True, compute="_compute_name", store=True)
    employee_id = fields.Many2one('hr.employee', string='Nhân viên', required=True)
    contract_id = fields.Many2one('hr.contract', string='Hợp đồng', domain="[('employee_id', '=', employee_id)]")

    contribution_type_id = fields.Many2one(
        'salary.contribution.type',
        string='Loại Đóng Góp',
        required=True
    )

    # Thay đổi: Cấu hình cơ sở tính toán
    calculation_base_type = fields.Selection([
        ('fixed', 'Số tiền cố định'),
        ('contract_field', 'Trường từ hợp đồng')
    ], string='Loại cơ sở tính toán', default='fixed', required=True)

    # Cơ sở tính toán (số tiền cố định)
    calculation_base_fixed = fields.Monetary(string='Số tiền cố định', currency_field='company_currency_id')

    # Cơ sở tính toán (trường từ hợp đồng)
    calculation_base_contract_field = fields.Selection([
        ('wage', 'Lương cơ bản'),
        ('wage_social_insurance', 'Lương BHXH'),
        # Thêm các trường khác từ hợp đồng nếu cần
    ], string='Trường từ hợp đồng')

    # Cơ sở tính toán (kết quả tính toán - chỉ đọc)
    calculation_base = fields.Monetary(string='Cơ sở tính toán (kết quả)',
                                       currency_field='company_currency_id',
                                       compute='_compute_calculation_base',
                                       store=True)

    # Tỷ lệ đóng góp
    employee_contribution_rate = fields.Float(string='Tỷ lệ đóng góp nhân viên (%)', default=0.0)
    company_contribution_rate = fields.Float(string='Tỷ lệ đóng góp công ty (%)', default=0.0)

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

    # Giới hạn số ngày không hưởng lương
    max_unpaid_days = fields.Integer(string='Số ngày không hưởng lương tối đa', default=14)

    # Các trường kế toán
    company_currency_id = fields.Many2one('res.currency', string='Đơn vị tiền tệ',
                                          default=lambda self: self.env.company.currency_id)

    # Lịch sử thay đổi
    history_ids = fields.One2many('salary.contribution.history', 'contribution_id',
                                  string='Lịch sử thay đổi')

    @api.depends('employee_id', 'contribution_type_id')
    def _compute_name(self):
        for record in self:
            if record.employee_id and record.contribution_type_id:
                employee_code = record.employee_id.employee_code or record.employee_id.identification_id or record.employee_id.id
                record.name = f"{employee_code}-{record.contribution_type_id.name}"
            else:
                record.name = "Đóng góp mới"

    @api.depends('calculation_base_type', 'calculation_base_fixed', 'calculation_base_contract_field', 'contract_id')
    def _compute_calculation_base(self):
        """Tính toán cơ sở tính toán dựa trên loại đã chọn"""
        for record in self:
            if record.calculation_base_type == 'fixed':
                record.calculation_base = record.calculation_base_fixed
            elif record.calculation_base_type == 'contract_field' and record.employee_id.contract_id:
                # Lấy giá trị từ trường tương ứng trong hợp đồng
                if record.calculation_base_contract_field and hasattr(record.employee_id.contract_id,
                                                                      record.calculation_base_contract_field):
                    record.calculation_base = getattr(record.employee_id.contract_id, record.calculation_base_contract_field)
                else:
                    record.calculation_base = 0
            else:
                record.calculation_base = 0

    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        """Tự động tìm hợp đồng hiện tại của nhân viên"""
        if self.employee_id:
            # Tìm hợp đồng hiện tại của nhân viên
            contract = self.env['hr.contract'].search([
                ('employee_id', '=', self.employee_id.id),
                ('state', '=', 'open')  # Chỉ lấy hợp đồng đang hoạt động
            ], limit=1)

            if contract:
                self.contract_id = contract.id
            else:
                self.contract_id = False

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
            self.env['salary.contribution.history'].create({
                'contribution_id': record.id,
                'start_date': record.start_date,
                'calculation_base': record.calculation_base,
                'employee_contribution_rate': record.employee_contribution_rate,
                'company_contribution_rate': record.company_contribution_rate,
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

    @api.onchange('contribution_type_id')
    def _onchange_contribution_type(self):
        """
        Tự động điền tỷ lệ đóng góp từ loại đóng góp được chọn
        """
        if self.contribution_type_id:
            # Điền tỷ lệ đóng góp từ loại đóng góp
            self.employee_contribution_rate = self.contribution_type_id.employee_contribution_rate
            self.company_contribution_rate = self.contribution_type_id.company_contribution_rate

            # Điền số ngày không hưởng lương tối đa
            self.max_unpaid_days = self.contribution_type_id.max_unpaid_days

    @api.onchange('calculation_base_type')
    def _onchange_calculation_base_type(self):
        """
        Xử lý khi thay đổi loại cơ sở tính toán
        """
        # Reset các giá trị khi thay đổi loại
        if self.calculation_base_type == 'fixed':
            self.calculation_base_contract_field = False
        elif self.calculation_base_type == 'contract_field':
            self.calculation_base_fixed = 0

    def calculate_contribution_amount(self):
        """
        Tính toán số tiền đóng góp
        """
        for record in self:
            # Tính toán số tiền đóng góp của nhân viên
            employee_contribution = record.calculation_base * (record.employee_contribution_rate / 100)

            # Tính toán số tiền đóng góp của công ty
            company_contribution = record.calculation_base * (record.company_contribution_rate / 100)

            return {
                'employee_contribution': employee_contribution,
                'company_contribution': company_contribution,
                'total_contribution': employee_contribution + company_contribution
            }

    def generate_contribution_report(self, date_from, date_to):
        """
        Tạo báo cáo tổng hợp đóng góp
        """
        domain = [
            ('state', '=', 'confirmed'),
            ('start_date', '>=', date_from),
            ('start_date', '<=', date_to)
        ]

        contributions = self.search(domain)

        report_data = {
            'total_employees': len(contributions.mapped('employee_id')),
            'total_calculation_base': sum(contributions.mapped('calculation_base')),
            'total_employee_contribution': 0,
            'total_company_contribution': 0,
            'contributions': []
        }

        for contribution in contributions:
            amounts = contribution.calculate_contribution_amount()

            report_data['total_employee_contribution'] += amounts['employee_contribution']
            report_data['total_company_contribution'] += amounts['company_contribution']

            report_data['contributions'].append({
                'employee': contribution.employee_id.name,
                'type': contribution.contribution_type_id.name,
                'calculation_base': contribution.calculation_base,
                'employee_contribution_rate': contribution.employee_contribution_rate,
                'company_contribution_rate': contribution.company_contribution_rate,
                'employee_contribution_amount': amounts['employee_contribution'],
                'company_contribution_amount': amounts['company_contribution']
            })

        return report_data


class SalaryContributionHistory(models.Model):
    _name = 'salary.contribution.history'
    _description = 'Salary Contribution History'

    contribution_id = fields.Many2one('salary.contribution', string='Đăng ký đóng góp')
    start_date = fields.Date(string='Ngày bắt đầu')
    end_date = fields.Date(string='Ngày kết thúc')

    calculation_base = fields.Monetary(string='Cơ sở tính toán', currency_field='company_currency_id')
    employee_contribution_rate = fields.Float(string='Tỷ lệ đóng góp nhân viên (%)')
    company_contribution_rate = fields.Float(string='Tỷ lệ đóng góp công ty (%)')

    company_currency_id = fields.Many2one('res.currency', string='Đơn vị tiền tệ',
                                          default=lambda self: self.env.company.currency_id)