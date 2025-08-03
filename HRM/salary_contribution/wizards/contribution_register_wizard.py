from odoo import models, fields, api
from odoo.exceptions import ValidationError


class ContributionRegisterWizard(models.TransientModel):
    _name = 'salary.contribution.register.wizard'
    _description = 'Wizard đăng ký đóng góp từ lương'

    # Trường nhóm nhân viên
    employee_ids = fields.Many2many('hr.employee', string='Nhân viên', required=True)

    # Loại đóng góp
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
    calculation_base_fixed = fields.Monetary(
        string='Số tiền cố định',
        currency_field='company_currency_id'
    )

    # Cơ sở tính toán (trường từ hợp đồng)
    calculation_base_contract_field = fields.Selection([
        ('wage', 'Lương cơ bản'),
        ('wage_social_insurance', 'Lương BHXH'),
        # Thêm các trường khác từ hợp đồng nếu cần
    ], string='Trường từ hợp đồng')

    # Tỷ lệ đóng góp
    employee_contribution_rate = fields.Float(
        string='Tỷ lệ đóng góp nhân viên (%)',
        default=0.0
    )
    company_contribution_rate = fields.Float(
        string='Tỷ lệ đóng góp công ty (%)',
        default=0.0
    )

    # Ngày bắt đầu, kết thúc
    start_date = fields.Date(
        string='Ngày bắt đầu',
        required=True,
        default=fields.Date.today
    )
    end_date = fields.Date(string='Ngày kết thúc')

    # Số ngày không hưởng lương tối đa
    max_unpaid_days = fields.Integer(
        string='Số ngày không hưởng lương tối đa',
        default=14
    )

    # Trường tiền tệ công ty
    company_currency_id = fields.Many2one(
        'res.currency',
        string='Đơn vị tiền tệ',
        default=lambda self: self.env.company.currency_id
    )

    # Thêm các trường mới
    department_id = fields.Many2one(
        'hr.department',
        string='Phòng ban',
        help='Chọn phòng ban để lọc nhân viên'
    )

    employee_count = fields.Integer(
        string='Số lượng nhân viên đã chọn',
        compute='_compute_employee_count',
        store=False
    )

    available_employee_count = fields.Integer(
        string='Số lượng nhân viên có thể đăng ký',
        compute='_compute_available_employees',
        store=False
    )

    available_employee_domain = fields.Char(
        string='Domain Nhân Viên Có Thể Đăng Ký',
        compute='_compute_available_employee_domain',
        readonly=True
    )

    @api.depends('employee_ids')
    def _compute_employee_count(self):
        for record in self:
            record.employee_count = len(record.employee_ids)

    @api.depends('contribution_type_id', 'department_id')
    def _compute_available_employees(self):
        """Tính số lượng nhân viên có thể đăng ký đóng góp (chưa đăng ký)"""
        for record in self:
            available_employees = self._get_available_employees()
            record.available_employee_count = len(available_employees)

    @api.depends('contribution_type_id', 'department_id')
    def _compute_available_employee_domain(self):
        """Tính toán domain động cho trường employee_ids"""
        for record in self:
            if not record.contribution_type_id:
                # Nếu chưa chọn loại đóng góp, cho phép chọn tất cả nhân viên
                record.available_employee_domain = "[]"
            else:
                # Lấy ID của các nhân viên đã đăng ký đóng góp này
                registered_employee_ids = self._get_registered_employee_ids()

                # Tạo domain loại trừ các nhân viên đã đăng ký
                domain = [('id', 'not in', registered_employee_ids)]

                # Nếu có chọn phòng ban, thêm điều kiện lọc theo phòng ban
                if record.department_id:
                    domain.append(('department_id', '=', record.department_id.id))

                # Chuyển đổi domain thành chuỗi để lưu trữ trong trường Char
                record.available_employee_domain = str(domain)

    def _get_registered_employee_ids(self):
        """Lấy danh sách ID của nhân viên đã đăng ký đóng góp này"""
        self.ensure_one()

        if not self.contribution_type_id:
            return []

        # Tìm nhân viên đã đăng ký đóng góp với loại này và trạng thái active
        registered_contributions = self.env['salary.contribution'].search([
            ('contribution_type_id', '=', self.contribution_type_id.id),
            ('state', 'in', ['draft', 'confirmed']),
            '|',
            ('end_date', '>=', fields.Date.today()),
            ('end_date', '=', False)
        ])

        return registered_contributions.mapped('employee_id.id')

    def _get_available_employees(self):
        """Lấy danh sách nhân viên chưa đăng ký đóng góp đã chọn"""
        self.ensure_one()

        # Nếu chưa chọn loại đóng góp, trả về tất cả nhân viên
        if not self.contribution_type_id:
            return self.env['hr.employee'].search([])

        # Lấy ID của các nhân viên đã đăng ký
        registered_employee_ids = self._get_registered_employee_ids()

        # Tìm tất cả nhân viên trừ những người đã đăng ký
        domain = [('id', 'not in', registered_employee_ids)]

        # Nếu đã chọn phòng ban, thêm điều kiện lọc theo phòng ban
        if self.department_id:
            domain.append(('department_id', '=', self.department_id.id))

        return self.env['hr.employee'].search(domain)

    @api.model
    def default_get(self, fields):
        """
        Thiết lập giá trị mặc định khi mở wizard
        Chỉ đặt employee_ids từ active_ids khi được gọi từ view nhân viên
        """
        res = super().default_get(fields)

        # Chỉ gán active_ids cho employee_ids nếu đang xem danh sách nhân viên
        # Kiểm tra xem context có chứa active_model='hr.employee' không
        active_model = self.env.context.get('active_model')
        active_ids = self.env.context.get('active_ids', [])

        if active_model == 'hr.employee' and active_ids and 'employee_ids' in fields:
            # Sử dụng Command.set để gán danh sách nhân viên
            from odoo.fields import Command

            # Kiểm tra xem nhân viên có tồn tại và người dùng có quyền đọc không
            valid_employee_ids = []
            for emp_id in active_ids:
                try:
                    employee = self.env['hr.employee'].browse(emp_id).exists()
                    if employee:
                        valid_employee_ids.append(emp_id)
                except Exception:
                    # Bỏ qua nhân viên không tồn tại hoặc không có quyền
                    continue

            if valid_employee_ids:
                res['employee_ids'] = [Command.set(valid_employee_ids)]

        return res

    @api.onchange('contribution_type_id')
    def _onchange_contribution_type(self):
        """
        Tự động điền tỷ lệ đóng góp từ loại đóng góp được chọn
        """
        if self.contribution_type_id:
            self.employee_contribution_rate = self.contribution_type_id.employee_contribution_rate
            self.company_contribution_rate = self.contribution_type_id.company_contribution_rate
            self.max_unpaid_days = self.contribution_type_id.max_unpaid_days

            # Cập nhật danh sách nhân viên có thể đăng ký
            available_employees = self._get_available_employees()

            # Lọc danh sách nhân viên đã chọn, chỉ giữ lại những nhân viên có thể đăng ký
            if self.employee_ids:
                valid_employee_ids = [emp.id for emp in self.employee_ids if emp.id in available_employees.ids]
                self.employee_ids = self.env['hr.employee'].browse(valid_employee_ids)

            # Tính toán lại domain động
            self._compute_available_employee_domain()

            # Thông báo cho người dùng nếu có nhân viên đã bị loại khỏi danh sách
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Danh sách nhân viên đã được cập nhật',
                    'message': f'Chỉ hiển thị {len(available_employees)} nhân viên chưa đăng ký đóng góp này.',
                    'sticky': False,
                    'type': 'info',
                }
            }

    @api.onchange('department_id')
    def _onchange_department(self):
        """
        Lọc nhân viên theo phòng ban được chọn và chỉ hiển thị nhân viên chưa đăng ký đóng góp
        """
        if self.contribution_type_id and self.department_id:
            # Chỉ lấy nhân viên của phòng ban được chọn và chưa đăng ký đóng góp
            available_employees = self._get_available_employees()
            self.employee_ids = available_employees

            # Cập nhật lại domain động
            self._compute_available_employee_domain()
        elif self.department_id:
            # Nếu chưa chọn loại đóng góp, chỉ lọc theo phòng ban
            domain = [('department_id', '=', self.department_id.id)]
            employees = self.env['hr.employee'].search(domain)
            self.employee_ids = employees

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

    def action_create_contributions(self):
        """
        Tạo các đóng góp cho những nhân viên được chọn
        """
        self.ensure_one()
        contributions = self.env['salary.contribution']

        if not self.employee_ids:
            raise ValidationError("Vui lòng chọn ít nhất một nhân viên")

        # Kiểm tra các trường bắt buộc dựa trên loại cơ sở tính toán
        if self.calculation_base_type == 'fixed' and not self.calculation_base_fixed:
            raise ValidationError("Vui lòng nhập số tiền cố định cho cơ sở tính toán")
        elif self.calculation_base_type == 'contract_field' and not self.calculation_base_contract_field:
            raise ValidationError("Vui lòng chọn trường từ hợp đồng cho cơ sở tính toán")

        # Kiểm tra lại một lần nữa xem nhân viên đã chọn có thể đăng ký không
        available_employees = self._get_available_employees()
        valid_employee_ids = [emp.id for emp in self.employee_ids if emp.id in available_employees.ids]

        if len(valid_employee_ids) < len(self.employee_ids):
            # Nếu có nhân viên không hợp lệ, thông báo cho người dùng
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Cảnh báo',
                    'message': f'{len(self.employee_ids) - len(valid_employee_ids)} nhân viên đã đăng ký đóng góp này và sẽ bị bỏ qua.',
                    'sticky': True,
                    'type': 'warning',
                }
            }

        created_count = 0
        for employee in self.employee_ids:
            # Kiểm tra lại một lần nữa xem nhân viên có trong danh sách có thể đăng ký không
            if employee.id in available_employees.ids:
                # Tìm hợp đồng hiện tại của nhân viên nếu cần
                contract = False
                if self.calculation_base_type == 'contract_field':
                    contract = self.env['hr.contract'].search([
                        ('employee_id', '=', employee.id),
                        ('state', '=', 'open')  # Chỉ lấy hợp đồng đang hoạt động
                    ], limit=1)

                    if not contract:
                        # Nếu không tìm thấy hợp đồng đang hoạt động, bỏ qua nhân viên này
                        continue

                contribution_vals = {
                    'employee_id': employee.id,
                    'contribution_type_id': self.contribution_type_id.id,
                    'calculation_base_type': self.calculation_base_type,
                    'employee_contribution_rate': self.employee_contribution_rate,
                    'company_contribution_rate': self.company_contribution_rate,
                    'start_date': self.start_date,
                    'end_date': self.end_date,
                    'max_unpaid_days': self.max_unpaid_days,
                    'state': 'draft',
                }

                # Thêm dữ liệu phù hợp với loại cơ sở tính toán
                if self.calculation_base_type == 'fixed':
                    contribution_vals['calculation_base_fixed'] = self.calculation_base_fixed
                else:
                    # Nếu là từ hợp đồng, thêm contract_id và trường tương ứng
                    contribution_vals['contract_id'] = contract.id
                    contribution_vals['calculation_base_contract_field'] = self.calculation_base_contract_field

                contribution = contributions.create(contribution_vals)
                contribution.action_confirm()
                contributions += contribution
                created_count += 1

        # Hiển thị thông báo thành công
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Thành công',
                'message': f'Đã tạo {created_count} đăng ký đóng góp.',
                'sticky': False,
                'type': 'success',
                'next': {
                    'type': 'ir.actions.act_window_close'
                }
            }
        }