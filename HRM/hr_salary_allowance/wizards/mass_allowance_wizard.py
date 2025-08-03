from odoo import models, fields, api
from odoo.exceptions import ValidationError


class MassAllowanceWizard(models.TransientModel):
    _name = 'mass.allowance.wizard'
    _description = 'Wizard Đăng Ký Phụ Cấp Hàng Loạt'

    allowance_type_id = fields.Many2one(
        'salary.allowance.type',
        string='Loại Phụ Cấp',
        required=True
    )

    amount = fields.Monetary(
        string='Số tiền phụ cấp',
        currency_field='company_currency_id',
        required=True
    )

    start_date = fields.Date(
        string='Ngày bắt đầu',
        required=True,
        default=fields.Date.today
    )

    end_date = fields.Date(
        string='Ngày kết thúc'
    )

    notes = fields.Text(
        string='Ghi chú'
    )

    employee_ids = fields.Many2many(
        'hr.employee',
        string='Nhân viên'
    )

    department_id = fields.Many2one(
        'hr.department',
        string='Phòng ban',
        help='Chọn phòng ban để lọc nhân viên'
    )

    company_currency_id = fields.Many2one(
        'res.currency',
        string='Đơn vị tiền tệ',
        default=lambda self: self.env.company.currency_id
    )

    employee_count = fields.Integer(
        string='Số lượng nhân viên đã chọn',
        compute='_compute_employee_count',
        store=False
    )

    # Thêm trường để hiển thị tổng số nhân viên có thể đăng ký
    available_employee_count = fields.Integer(
        string='Số lượng nhân viên có thể đăng ký',
        compute='_compute_available_employees',
        store=False
    )

    # Thêm trường mới để lưu trữ domain động
    available_employee_domain = fields.Char(
        string='Domain Nhân Viên Có Thể Đăng Ký',
        compute='_compute_available_employee_domain',
        readonly=True
    )

    @api.depends('employee_ids')
    def _compute_employee_count(self):
        for record in self:
            record.employee_count = len(record.employee_ids)

    @api.depends('allowance_type_id', 'department_id')
    def _compute_available_employees(self):
        """Tính số lượng nhân viên có thể đăng ký phụ cấp (chưa đăng ký)"""
        for record in self:
            available_employees = self._get_available_employees()
            record.available_employee_count = len(available_employees)

    @api.depends('allowance_type_id', 'department_id')
    def _compute_available_employee_domain(self):
        """Tính toán domain động cho trường employee_ids"""
        for record in self:
            if not record.allowance_type_id:
                # Nếu chưa chọn loại phụ cấp, cho phép chọn tất cả nhân viên
                record.available_employee_domain = "[]"
            else:
                # Lấy ID của các nhân viên đã đăng ký phụ cấp này
                registered_employee_ids = self._get_registered_employee_ids()

                # Tạo domain loại trừ các nhân viên đã đăng ký
                domain = [('id', 'not in', registered_employee_ids)]

                # Nếu có chọn phòng ban, thêm điều kiện lọc theo phòng ban
                if record.department_id:
                    domain.append(('department_id', '=', record.department_id.id))

                # Chuyển đổi domain thành chuỗi để lưu trữ trong trường Char
                record.available_employee_domain = str(domain)

    def _get_registered_employee_ids(self):
        """Lấy danh sách ID của nhân viên đã đăng ký phụ cấp này"""
        self.ensure_one()

        if not self.allowance_type_id:
            return []

        # Tìm nhân viên đã đăng ký phụ cấp với loại này và trạng thái active
        registered_allowances = self.env['salary.allowance'].search([
            ('allowance_type_id', '=', self.allowance_type_id.id),
            ('state', 'in', ['draft', 'confirmed']),
            '|',
            ('end_date', '>=', fields.Date.today()),
            ('end_date', '=', False)
        ])

        return registered_allowances.mapped('employee_id.id')

    def _get_available_employees(self):
        """Lấy danh sách nhân viên chưa đăng ký phụ cấp đã chọn"""
        self.ensure_one()

        # Nếu chưa chọn loại phụ cấp, trả về tất cả nhân viên
        if not self.allowance_type_id:
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

    @api.onchange('allowance_type_id')
    def _onchange_allowance_type(self):
        """
        Tự động điền số tiền mặc định từ loại phụ cấp được chọn nếu có
        Đồng thời cập nhật danh sách nhân viên có thể đăng ký
        """
        if self.allowance_type_id:
            # Cập nhật số tiền mặc định nếu là phụ cấp cố định
            if self.allowance_type_id.is_fixed:
                self.amount = self.allowance_type_id.default_amount

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
                    'message': f'Chỉ hiển thị {len(available_employees)} nhân viên chưa đăng ký phụ cấp này.',
                    'sticky': False,
                    'type': 'info',
                }
            }

    @api.onchange('department_id')
    def _onchange_department(self):
        """
        Lọc nhân viên theo phòng ban được chọn và chỉ hiển thị nhân viên chưa đăng ký phụ cấp
        """
        if self.allowance_type_id and self.department_id:
            # Chỉ lấy nhân viên của phòng ban được chọn và chưa đăng ký phụ cấp
            available_employees = self._get_available_employees()
            self.employee_ids = available_employees

            # Cập nhật lại domain động
            self._compute_available_employee_domain()
        elif self.department_id:
            # Nếu chưa chọn loại phụ cấp, chỉ lọc theo phòng ban
            domain = [('department_id', '=', self.department_id.id)]
            employees = self.env['hr.employee'].search(domain)
            self.employee_ids = employees

    # Đã loại bỏ phương thức action_fill_all_employees

    def action_create_allowances(self):
        """
        Tạo các phụ cấp cho nhân viên được chọn
        """
        self.ensure_one()

        if not self.employee_ids:
            raise ValidationError("Vui lòng chọn ít nhất một nhân viên.")

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
                    'message': f'{len(self.employee_ids) - len(valid_employee_ids)} nhân viên đã đăng ký phụ cấp này và sẽ bị bỏ qua.',
                    'sticky': True,
                    'type': 'warning',
                }
            }

        allowances = self.env['salary.allowance']
        created_count = 0

        for employee in self.employee_ids:
            # Kiểm tra lại một lần nữa xem nhân viên có trong danh sách có thể đăng ký không
            if employee.id in available_employees.ids:
                allowance_vals = {
                    'employee_id': employee.id,
                    'allowance_type_id': self.allowance_type_id.id,
                    'amount': self.amount,
                    'start_date': self.start_date,
                    'end_date': self.end_date,
                    'notes': self.notes,
                    'state': 'draft'
                }

                allowance = allowances.create(allowance_vals)
                allowance.action_confirm()  # Tự động xác nhận phụ cấp
                created_count += 1

        # Hiển thị thông báo thành công
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Thành công',
                'message': f'Đã tạo {created_count} đăng ký phụ cấp.',
                'sticky': False,
                'type': 'success',
                'next': {
                    'type': 'ir.actions.act_window_close'
                }
            }
        }