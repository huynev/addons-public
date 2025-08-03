# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class HrLoanAutoAddEmployeesWizard(models.TransientModel):
    """Wizard for adding employees to automatic loan configuration"""
    _name = 'hr.loan.auto.add.employees.wizard'
    _description = "Add Employees to Loan Configuration Wizard"

    config_id = fields.Many2one('hr.loan.auto.config', string="Configuration",
                                required=True, readonly=True)
    default_loan_amount = fields.Float(string="Default Loan Amount", default=0.0,
                                       help="Default loan amount for new employees")
    employee_ids = fields.Many2many('hr.employee', string="Employees", required=True,
                                    help="Select employees to add to the configuration")
    department_id = fields.Many2one('hr.department', string='Phòng ban',
                                    help='Chọn phòng ban để lọc nhân viên')
    employee_count = fields.Integer(string='Số lượng nhân viên đã chọn',
                                    compute='_compute_employee_count',
                                    store=False)
    available_employee_count = fields.Integer(string='Số lượng nhân viên có thể thêm',
                                              compute='_compute_available_employees',
                                              store=False)
    available_employee_domain = fields.Char(string='Domain nhân viên có thể thêm',
                                            compute='_compute_available_employee_domain',
                                            readonly=True)

    @api.depends('employee_ids')
    def _compute_employee_count(self):
        """Tính số lượng nhân viên đã chọn"""
        for record in self:
            record.employee_count = len(record.employee_ids)

    @api.depends('config_id', 'department_id')
    def _compute_available_employees(self):
        """Tính số lượng nhân viên có thể thêm vào cấu hình"""
        for record in self:
            available_employees = self._get_available_employees()
            record.available_employee_count = len(available_employees)

    @api.depends('config_id', 'department_id')
    def _compute_available_employee_domain(self):
        """Tính toán domain động cho trường employee_ids"""
        for record in self:
            if not record.config_id:
                record.available_employee_domain = "[]"
            else:
                # Lấy ID của các nhân viên đã được thêm vào cấu hình
                existing_employee_ids = record.config_id.employee_line_ids.mapped('employee_id.id')

                # Tạo domain loại trừ các nhân viên đã có trong cấu hình
                domain = [('id', 'not in', existing_employee_ids)]

                # Nếu có chọn phòng ban, thêm điều kiện lọc theo phòng ban
                if record.department_id:
                    domain.append(('department_id', '=', record.department_id.id))

                # Chỉ hiển thị nhân viên đang hoạt động
                domain.append(('active', '=', True))

                # Chuyển đổi domain thành chuỗi
                record.available_employee_domain = str(domain)

    def _get_available_employees(self):
        """Lấy danh sách nhân viên chưa được thêm vào cấu hình"""
        self.ensure_one()

        # Nếu không có cấu hình, trả về rỗng
        if not self.config_id:
            return self.env['hr.employee']

        # Lấy ID của các nhân viên đã có trong cấu hình
        existing_employee_ids = self.config_id.employee_line_ids.mapped('employee_id.id')

        # Tìm tất cả nhân viên trừ những người đã có trong cấu hình
        domain = [('id', 'not in', existing_employee_ids), ('active', '=', True)]

        # Nếu đã chọn phòng ban, thêm điều kiện lọc theo phòng ban
        if self.department_id:
            domain.append(('department_id', '=', self.department_id.id))

        return self.env['hr.employee'].search(domain)

    @api.model
    def default_get(self, fields):
        """Thiết lập giá trị mặc định khi mở wizard"""
        res = super(HrLoanAutoAddEmployeesWizard, self).default_get(fields)

        # Lấy cấu hình từ context
        config_id = self.env.context.get('active_id')
        if config_id:
            res['config_id'] = config_id

        return res

    @api.onchange('department_id')
    def _onchange_department(self):
        """Lọc nhân viên theo phòng ban được chọn"""
        self.employee_ids = False  # Xóa lựa chọn hiện tại

        if self.config_id and self.department_id:
            # Tự động cập nhật domain động
            self._compute_available_employee_domain()

    def action_add_employees(self):
        """Thêm nhân viên đã chọn vào cấu hình"""
        self.ensure_one()

        if not self.employee_ids:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Warning'),
                    'message': _('No employees selected.'),
                    'sticky': False,
                    'type': 'warning',
                }
            }

        # Kiểm tra lại một lần nữa xem nhân viên đã chọn có thể thêm vào không
        available_employees = self._get_available_employees()
        valid_employee_ids = [emp.id for emp in self.employee_ids if emp.id in available_employees.ids]

        if len(valid_employee_ids) < len(self.employee_ids):
            # Nếu có nhân viên không hợp lệ, thông báo cho người dùng
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Warning'),
                    'message': _('%s employees are already in this configuration and will be skipped.')
                               % (len(self.employee_ids) - len(valid_employee_ids)),
                    'sticky': True,
                    'type': 'warning',
                }
            }

        # Tạo employee lines cho nhân viên được chọn
        new_employee_lines = []
        for employee in self.employee_ids:
            if employee.id in available_employees.ids:
                new_employee_lines.append((0, 0, {
                    'employee_id': employee.id,
                    'loan_amount': self.default_loan_amount,
                    'active': True,
                }))

        # Cập nhật cấu hình với employee lines mới
        if new_employee_lines:
            self.config_id.write({'employee_line_ids': new_employee_lines})

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Employees Added'),
                'message': _('%s employees have been added to the configuration.') % len(valid_employee_ids),
                'sticky': False,
                'type': 'success',
                'next': {
                    'type': 'ir.actions.act_window_close',
                }
            }
        }

class HrLoanBatchCreateWizard(models.TransientModel):
    """Wizard để tạo đợt ứng lương thủ công"""
    _name = 'hr.loan.batch.create.wizard'
    _description = "Create Loan Batch Wizard"

    name = fields.Char(string="Batch Name", help="Leave empty to auto-generate")
    month = fields.Selection([
        ('1', 'January'), ('2', 'February'), ('3', 'March'), ('4', 'April'),
        ('5', 'May'), ('6', 'June'), ('7', 'July'), ('8', 'August'),
        ('9', 'September'), ('10', 'October'), ('11', 'November'), ('12', 'December')
    ], string="Month", required=True, default=lambda self: str(fields.Date.today().month))

    year = fields.Integer(string="Year", required=True, default=lambda self: fields.Date.today().year)
    company_id = fields.Many2one('res.company', string="Company",
                                 default=lambda self: self.env.user.company_id,
                                 required=True)

    def create_batch(self):
        """Tạo đợt ứng lương mới"""
        month_int = int(self.month)

        batch = self.env['hr.loan.batch'].create({
            'month': month_int,
            'year': self.year,
            'company_id': self.company_id.id,
        })

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'hr.loan.batch',
            'res_id': batch.id,
            'view_mode': 'form',
            'target': 'current',
        }


class HrLoanBatchProcessWizard(models.TransientModel):
    """Wizard để xử lý hàng loạt các thao tác trên đợt ứng lương"""
    _name = 'hr.loan.batch.process.wizard'
    _description = "Batch Process Loans Wizard"

    batch_id = fields.Many2one('hr.loan.batch', string="Batch", required=True)
    action_type = fields.Selection([
        ('submit_all', 'Submit All Draft Loans'),
        ('approve_all', 'Approve All Pending Loans'),
        ('refuse_all', 'Refuse All Pending Loans'),
        ('compute_installments', 'Compute Installments for All'),
    ], string="Action", required=True)

    confirmation_message = fields.Html(compute='_compute_confirmation_message')

    @api.depends('batch_id', 'action_type')
    def _compute_confirmation_message(self):
        """Tính toán thông điệp xác nhận"""
        for wizard in self:
            if not wizard.batch_id or not wizard.action_type:
                wizard.confirmation_message = ""
                continue

            batch = wizard.batch_id

            if wizard.action_type == 'submit_all':
                draft_count = len(batch.loan_ids.filtered(lambda l: l.state == 'draft'))
                wizard.confirmation_message = f"<p>Thao tác này sẽ gửi {draft_count} khoản tạm ứng nháp để phê duyệt.</p>"

            elif wizard.action_type == 'approve_all':
                pending_count = len(batch.loan_ids.filtered(lambda l: l.state == 'waiting_approval_1'))
                wizard.confirmation_message = f"<p>Thao tác này sẽ phê duyệt {pending_count} khoản tạm ứng đang chờ duyệt.</p>"

            elif wizard.action_type == 'refuse_all':
                pending_count = len(batch.loan_ids.filtered(lambda l: l.state == 'waiting_approval_1'))
                wizard.confirmation_message = f"<p>Thao tác này sẽ từ chối {pending_count} khoản tạm ứng đang chờ duyệt.</p>"

            elif wizard.action_type == 'compute_installments':
                no_installments = len(batch.loan_ids.filtered(lambda l: not l.loan_lines))
                wizard.confirmation_message = f"<p>Thao tác này sẽ tính toán kỳ trả góp cho {no_installments} khoản tạm ứng chưa có lịch trả.</p>"

    @api.model
    def default_get(self, fields_list):
        """Set default batch from context"""
        res = super().default_get(fields_list)
        if self.env.context.get('active_id'):
            res['batch_id'] = self.env.context['active_id']
        return res

    def process_loans(self):
        """Xử lý các khoản ứng theo action được chọn"""
        batch = self.batch_id

        if self.action_type == 'submit_all':
            draft_loans = batch.loan_ids.filtered(lambda l: l.state == 'draft')
            if draft_loans:
                return draft_loans.action_batch_submit()

        elif self.action_type == 'approve_all':
            pending_loans = batch.loan_ids.filtered(lambda l: l.state == 'waiting_approval_1')
            if pending_loans:
                return pending_loans.action_batch_approve()

        elif self.action_type == 'refuse_all':
            pending_loans = batch.loan_ids.filtered(lambda l: l.state == 'waiting_approval_1')
            if pending_loans:
                return pending_loans.action_batch_refuse()

        elif self.action_type == 'compute_installments':
            loans_without_installments = batch.loan_ids.filtered(lambda l: not l.loan_lines)
            for loan in loans_without_installments:
                loan.action_compute_installment()

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _('Computed installments for %d loan(s).') % len(loans_without_installments),
                    'type': 'success',
                }
            }

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('No Action'),
                'message': _('No loans to process.'),
                'type': 'warning',
            }
        }


class HrLoanBulkCreateWizard(models.TransientModel):
    """Wizard để tạo hàng loạt khoản ứng"""
    _name = 'hr.loan.bulk.create.wizard'
    _description = "Bulk Create Loans Wizard"

    batch_id = fields.Many2one('hr.loan.batch', string="Batch")
    employee_ids = fields.Many2many('hr.employee', string="Employees", required=True)
    loan_amount = fields.Float(string="Loan Amount", required=True)
    installment = fields.Integer(string="Number of Installments", default=1, required=True)
    payment_date = fields.Date(string="Payment Start Date", default=fields.Date.today(), required=True)
    auto_submit = fields.Boolean(string="Auto Submit for Approval", default=False)
    auto_compute_installments = fields.Boolean(string="Auto Compute Installments", default=True)

    @api.model
    def default_get(self, fields_list):
        """Set default batch from context"""
        res = super().default_get(fields_list)
        if self.env.context.get('active_model') == 'hr.loan.batch' and self.env.context.get('active_id'):
            res['batch_id'] = self.env.context['active_id']
        return res

    def create_loans(self):
        """Tạo hàng loạt khoản ứng"""
        created_loans = []
        skipped_employees = []

        for employee in self.employee_ids:
            # Kiểm tra nhân viên có khoản ứng đang chờ không
            existing_loan = self.env['hr.loan'].search_count([
                ('employee_id', '=', employee.id),
                ('state', 'in', ['approve', 'waiting_approval_1']),
                ('balance_amount', '>', 0)
            ])

            if existing_loan:
                skipped_employees.append(employee.name)
                continue

            # Tạo khoản ứng
            loan_vals = {
                'employee_id': employee.id,
                'loan_amount': self.loan_amount,
                'installment': self.installment,
                'payment_date': self.payment_date,
                'batch_id': self.batch_id.id if self.batch_id else False,
            }

            loan = self.env['hr.loan'].create(loan_vals)
            created_loans.append(loan)

            # Tính toán trả góp nếu được yêu cầu
            if self.auto_compute_installments:
                loan.action_compute_installment()

            # Gửi duyệt nếu được yêu cầu
            if self.auto_submit:
                loan.action_submit()

        # Thông báo kết quả
        message = _("Created %d loan(s) successfully.") % len(created_loans)
        if skipped_employees:
            message += _("\nSkipped employees (have pending loans): %s") % ', '.join(skipped_employees)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Bulk Create Result'),
                'message': message,
                'type': 'success' if created_loans else 'warning',
            }
        }