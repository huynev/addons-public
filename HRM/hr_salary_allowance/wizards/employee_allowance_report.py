from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, date
import calendar
import logging

_logger = logging.getLogger(__name__)


class EmployeeAllowanceReport(models.TransientModel):
    _name = 'employee.allowance.report'
    _description = 'Employee Allowance Report Wizard'

    # Bộ lọc thời gian
    date_from = fields.Date(
        string='Từ ngày',
        required=True,
        default=lambda self: date.today().replace(day=1)
    )
    date_to = fields.Date(
        string='Đến ngày',
        required=True,
        default=lambda self: date.today()
    )

    # Bộ lọc nhân viên
    filter_type = fields.Selection([
        ('all', 'Tất cả nhân viên'),
        ('department', 'Theo phòng ban'),
        ('employee', 'Theo nhân viên cụ thể'),
    ], string='Bộ lọc', default='all', required=True)

    department_ids = fields.Many2many(
        'hr.department',
        'employee_allowance_report_department_rel',
        'report_id', 'department_id',
        string='Phòng ban'
    )

    employee_ids = fields.Many2many(
        'hr.employee',
        'employee_allowance_report_employee_rel',
        'report_id', 'employee_id',
        string='Nhân viên'
    )

    # Tùy chọn báo cáo
    report_type = fields.Selection([
        ('current', 'Phụ cấp hiện tại'),
        ('history', 'Lịch sử phụ cấp'),
    ], string='Loại báo cáo', default='current', required=True)

    include_inactive = fields.Boolean(
        string='Bao gồm nhân viên không active',
        default=False
    )

    include_zero_allowance = fields.Boolean(
        string='Hiển thị nhân viên không có phụ cấp',
        default=True
    )

    group_by_department = fields.Boolean(
        string='Nhóm theo phòng ban',
        default=False
    )

    # Computed fields
    employee_count = fields.Integer(
        string='Số lượng nhân viên',
        compute='_compute_employee_count'
    )

    @api.depends('filter_type', 'department_ids', 'employee_ids', 'include_inactive')
    def _compute_employee_count(self):
        for record in self:
            try:
                employees = record._get_employees()
                record.employee_count = len(employees)
            except:
                record.employee_count = 0

    @api.onchange('filter_type')
    def _onchange_filter_type(self):
        if self.filter_type != 'department':
            self.department_ids = [(5, 0, 0)]
        if self.filter_type != 'employee':
            self.employee_ids = [(5, 0, 0)]

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for record in self:
            if record.date_from > record.date_to:
                raise ValidationError("Ngày bắt đầu phải nhỏ hơn ngày kết thúc")

    def action_generate_report(self):
        """Tạo báo cáo Excel"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': f'/employee/allowance/report/excel?wizard_id={self.id}',
            'target': 'new',
        }

    def _get_employees(self):
        """Lấy danh sách nhân viên theo filter"""
        domain = [('active', '=', True)] if not self.include_inactive else []

        if self.filter_type == 'employee' and self.employee_ids:
            domain.append(('id', 'in', self.employee_ids.ids))
        elif self.filter_type == 'department' and self.department_ids:
            domain.append(('department_id', 'in', self.department_ids.ids))

        # Always order by department_id if grouping is enabled, or as fallback
        order_by = 'department_id, employee_code, name'
        employees = self.env['hr.employee'].search(domain, order=order_by)
        return employees

    def _get_allowance_types(self):
        """Lấy danh sách loại phụ cấp theo thứ tự ưu tiên và sau đó là theo mã code"""
        # Define the desired order of allowance types by their codes
        ordered_codes = ['THAMNIEN', 'CHUYENCAN', 'TRACHNHIEM', 'DOCHAI', 'DIENTHOAI', 'XANGXE', 'KHAC', 'DACBIET']

        all_allowance_types = self.env['salary.allowance.type'].search([('active', '=', True)])

        # Create a dictionary for quick lookup by code
        allowance_dict = {allowance_type.code: allowance_type for allowance_type in all_allowance_types}

        sorted_allowance_types = []
        # Add allowances in the predefined order
        for code in ordered_codes:
            if code in allowance_dict:
                sorted_allowance_types.append(allowance_dict[code])
                del allowance_dict[code]  # Remove to avoid adding again

        # Add remaining allowances, sorted by code
        remaining_allowances = sorted(allowance_dict.values(), key=lambda x: x.code)
        sorted_allowance_types.extend(remaining_allowances)

        return sorted_allowance_types

    def _prepare_report_data(self):
        """Chuẩn bị dữ liệu báo cáo"""
        self.ensure_one()

        employees = self._get_employees()
        allowance_types = self._get_allowance_types()

        if not employees:
            raise UserError("Không tìm thấy nhân viên nào phù hợp với điều kiện lọc.")

        if not allowance_types:
            raise UserError("Không tìm thấy loại phụ cấp nào trong hệ thống.")

        # Lấy dữ liệu phụ cấp
        allowance_data = self._get_allowance_data(employees, allowance_types)

        # Tính toán thống kê
        statistics = self._calculate_statistics(employees, allowance_types, allowance_data)

        return {
            'wizard_id': self.id,
            'date_from': self.date_from,
            'date_to': self.date_to,
            'report_type': self.report_type,
            'employees': self._format_employees(employees),
            'allowance_types': self._format_allowance_types(allowance_types),
            'allowance_data': allowance_data,
            'statistics': statistics,
            'report_date': datetime.now().strftime('%d/%m/%Y %H:%M'),
            'user_name': self.env.user.name,
            'company_name': self.env.company.name,
            'group_by_department': self.group_by_department,  # Pass this new option
        }

    def _get_allowance_data(self, employees, allowance_types):
        """Lấy dữ liệu phụ cấp theo nhân viên và loại phụ cấp"""
        allowance_data = {}

        # Domain cơ bản
        domain = [
            ('state', '=', 'confirmed'),
            ('start_date', '<=', self.date_to),
            '|',
            ('end_date', '=', False),
            ('end_date', '>=', self.date_from)
        ]

        # Lấy tất cả allowance trong khoảng thời gian
        allowances = self.env['salary.allowance'].search(domain)

        # Tổ chức dữ liệu theo employee_id và allowance_type_id
        for employee in employees:
            allowance_data[employee.id] = {}
            for allowance_type in allowance_types:
                allowance_data[employee.id][allowance_type.id] = {
                    'amount': 0,
                    'count': 0,
                    'allowances': []
                }

        # Điền dữ liệu từ allowances
        for allowance in allowances:
            if allowance.employee_id.id in allowance_data:
                type_id = allowance.allowance_type_id.id
                if type_id in allowance_data[allowance.employee_id.id]:
                    data = allowance_data[allowance.employee_id.id][type_id]
                    # Update the logic here
                    if allowance.allowance_type_id.code == 'THAMNIEN':
                        amount = allowance.amount * (allowance.employee_id.employment_years or 0)
                    else:
                        amount = allowance.amount

                    data['amount'] += amount
                    data['count'] += 1
                    data['allowances'].append({
                        'id': allowance.id,
                        'amount': amount,
                        'start_date': allowance.start_date,
                        'end_date': allowance.end_date,
                    })

        return allowance_data

    def _format_employees(self, employees):
        """Format thông tin nhân viên, bao gồm lương cơ bản và ngày vào làm"""
        result = []
        # Use a dictionary to group employees by department name
        grouped_employees = {}
        for idx, emp in enumerate(employees, 1):
            department_name = emp.department_id.name if emp.department_id else 'Chưa phân phòng ban'
            if department_name not in grouped_employees:
                grouped_employees[department_name] = []

            basic_salary = 0
            # Get basic salary from the active contract
            if emp.contract_id and emp.contract_id.state in ('open', 'draft'):
                basic_salary = emp.contract_id.wage

            # Calculate employment years
            employment_years = 0
            if emp.first_contract_date:
                today = date.today()
                employment_years = today.year - emp.first_contract_date.year - \
                                   ((today.month, today.day) < (emp.first_contract_date.month, emp.first_contract_date.day))

            grouped_employees[department_name].append({
                'id': emp.id,
                'stt': idx,
                'employee_code': emp.employee_code or f'EMP{emp.id:04d}',
                'name': emp.name,
                'department': department_name,
                'basic_salary': basic_salary,
                'work_email': emp.work_email or '',
                'active': emp.active,
                'date_of_joining': emp.first_contract_date.strftime('%d/%m/%Y') if emp.first_contract_date else '',
                'employment_years': employment_years, # Add new field for seniority years
            })

        # Flatten the list while preserving department grouping for later use
        for dept_name in sorted(grouped_employees.keys()):  # Sort departments for consistent output
            for emp_data in grouped_employees[dept_name]:
                result.append(emp_data)

        return result

    def _format_allowance_types(self, allowance_types):
        """Format thông tin loại phụ cấp"""
        result = []
        for allowance_type in allowance_types:
            result.append({
                'id': allowance_type.id,
                'code': allowance_type.code,
                'name': allowance_type.name,
                'is_taxable': allowance_type.is_taxable,
                'is_fixed': allowance_type.is_fixed,
                'default_amount': allowance_type.default_amount,
            })
        return result

    def _calculate_statistics(self, employees, allowance_types, allowance_data):
        """Tính toán thống kê báo cáo và thống kê theo phòng ban"""
        stats = {
            'total_employees': len(employees),
            'total_allowance_types': len(allowance_types),
            'total_amount': 0,  # This will now include basic salary
            'total_taxable_amount': 0,  # This remains only for taxable allowance
            'total_non_taxable_amount': 0,  # This remains only for non-taxable allowance
            'total_basic_salary': 0,  # New: to track total basic salary
            'employee_totals': {},
            'type_totals': {},
            'employees_with_allowance': 0,
            'department_totals': {},  # New: to store totals per department
        }

        # Initialize type totals
        for allowance_type in allowance_types:
            stats['type_totals'][allowance_type.id] = {
                'total_amount': 0,
                'employee_count': 0,
            }

        # Calculate totals per employee, per type, and per department
        employees_with_allowance = set()
        for employee_obj in employees:  # Use employee_obj to get department_id
            employee_id = employee_obj.id
            department_name = employee_obj.department_id.name if employee_obj.department_id else 'Chưa phân phòng ban'

            if department_name not in stats['department_totals']:
                stats['department_totals'][department_name] = {
                    'total_amount': 0,  # This will now include basic salary for department
                    'employee_count': 0,
                    'allowance_type_totals': {at.id: 0 for at in allowance_types},
                    # Totals for each allowance type in this department
                    'basic_salary_total': 0,  # New: Basic salary total for this department
                }

            basic_salary = 0
            if employee_obj.contract_id and employee_obj.contract_id.state in ('open', 'draft'):
                basic_salary = employee_obj.contract_id.wage

            employee_total = basic_salary  # Start employee total with basic salary
            stats['total_basic_salary'] += basic_salary  # Add to overall basic salary total
            stats['department_totals'][department_name][
                'basic_salary_total'] += basic_salary  # Add to department basic salary total

            stats['department_totals'][department_name]['employee_count'] += 1

            for allowance_type in allowance_types:
                amount = allowance_data[employee_id][allowance_type.id]['amount']

                if amount > 0:
                    employees_with_allowance.add(employee_id)
                    employee_total += amount  # Add allowance to employee total
                    # Do not add allowance amount to overall total here, it will be added when processing allowances

                    # Classify by tax (only for allowances, not basic salary)
                    if allowance_type.is_taxable:
                        stats['total_taxable_amount'] += amount
                    else:
                        stats['total_non_taxable_amount'] += amount

                    # Total by allowance type
                    stats['type_totals'][allowance_type.id]['total_amount'] += amount
                    stats['type_totals'][allowance_type.id]['employee_count'] += 1

                    # Total by allowance type for this department
                    stats['department_totals'][department_name]['allowance_type_totals'][allowance_type.id] += amount

            stats['employee_totals'][employee_id] = employee_total
            stats['total_amount'] += employee_total  # Add employee's total (basic + allowance) to grand total
            stats['department_totals'][department_name]['total_amount'] += employee_total

        stats['employees_with_allowance'] = len(employees_with_allowance)

        return stats