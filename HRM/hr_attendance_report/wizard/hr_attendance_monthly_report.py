from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
import calendar
from datetime import datetime, date
import pytz
import logging

_logger = logging.getLogger(__name__)


class HrAttendanceMonthlyReport(models.TransientModel):
    _name = 'hr.attendance.monthly.report'
    _description = 'HR Attendance Monthly Report Wizard'

    # Basic fields
    month = fields.Selection([
        ('1', 'Tháng 1'), ('2', 'Tháng 2'), ('3', 'Tháng 3'),
        ('4', 'Tháng 4'), ('5', 'Tháng 5'), ('6', 'Tháng 6'),
        ('7', 'Tháng 7'), ('8', 'Tháng 8'), ('9', 'Tháng 9'),
        ('10', 'Tháng 10'), ('11', 'Tháng 11'), ('12', 'Tháng 12'),
    ], string='Tháng', required=True, default=str(datetime.now().month))

    year = fields.Integer(
        string='Năm',
        required=True,
        default=datetime.now().year,
        help='Năm cần xuất báo cáo (2000-2100)'
    )

    # Filter fields
    filter_type = fields.Selection([
        ('all', 'Tất cả nhân viên'),
        ('department', 'Theo phòng ban'),
        ('employee', 'Theo nhân viên cụ thể'),
    ], string='Bộ lọc', default='all', required=True)

    department_ids = fields.Many2many(
        'hr.department',
        'hr_attendance_monthly_report_department_rel',
        'report_id', 'department_id',
        string='Phòng ban',
        help='Chọn các phòng ban cần xuất báo cáo (để trống = tất cả)'
    )

    employee_ids = fields.Many2many(
        'hr.employee',
        'hr_attendance_monthly_report_employee_rel',
        'report_id', 'employee_id',
        string='Nhân viên',
        help='Chọn các nhân viên cần xuất báo cáo (để trống = tất cả)'
    )

    # Report settings
    report_type = fields.Selection([
        ('pdf', 'Báo cáo PDF'),
        ('excel', 'File Excel'),
    ], string='Loại báo cáo', default='excel', required=True)

    include_inactive = fields.Boolean(
        string='Bao gồm nhân viên không active',
        default=False,
        help='Tick để bao gồm cả nhân viên đã nghỉ việc'
    )

    show_summary = fields.Boolean(
        string='Hiển thị tổng kết',
        default=True,
        help='Hiển thị thống kê tổng quan'
    )

    # Thêm tùy chọn hiển thị nghỉ phép
    include_leaves = fields.Boolean(
        string='Bao gồm dữ liệu nghỉ phép',
        default=True,
        help='Hiển thị thông tin nghỉ phép trên báo cáo'
    )

    # Computed fields for display
    employee_count = fields.Integer(
        string='Số lượng nhân viên',
        compute='_compute_employee_count',
        help='Số lượng nhân viên sẽ được bao gồm trong báo cáo'
    )

    @api.depends('filter_type', 'department_ids', 'employee_ids', 'include_inactive')
    def _compute_employee_count(self):
        """Tính số lượng nhân viên sẽ được xuất báo cáo"""
        for record in self:
            try:
                employees = record._get_employees()
                record.employee_count = len(employees)
            except:
                record.employee_count = 0

    # Onchange methods
    @api.onchange('filter_type')
    def _onchange_filter_type(self):
        """Clear dữ liệu khi thay đổi filter type"""
        if self.filter_type != 'department':
            self.department_ids = [(5, 0, 0)]
        if self.filter_type != 'employee':
            self.employee_ids = [(5, 0, 0)]

    @api.onchange('year', 'month')
    def _onchange_date(self):
        """Validate và cảnh báo khi chọn tháng/năm"""
        if self.year and self.month:
            selected_date = date(self.year, int(self.month), 1)
            current_date = date.today()

            if selected_date > current_date:
                return {
                    'warning': {
                        'title': 'Cảnh báo',
                        'message': f'Bạn đang chọn tháng {self.month}/{self.year} trong tương lai. '
                                   'Có thể không có dữ liệu chấm công.'
                    }
                }

    # Constraint methods
    @api.constrains('year')
    def _check_year(self):
        """Kiểm tra năm hợp lệ"""
        for record in self:
            if record.year < 2000 or record.year > 2150:
                raise ValidationError("Năm phải trong khoảng từ 2000 đến 2150")

    @api.constrains('filter_type', 'department_ids', 'employee_ids')
    def _check_filter_data(self):
        """Kiểm tra dữ liệu filter hợp lệ"""
        for record in self:
            if record.filter_type == 'department' and not record.department_ids:
                raise ValidationError("Vui lòng chọn ít nhất một phòng ban")
            if record.filter_type == 'employee' and not record.employee_ids:
                raise ValidationError("Vui lòng chọn ít nhất một nhân viên")

    # Action methods
    def action_generate_report(self):
        """Generate báo cáo theo loại được chọn"""
        self.ensure_one()

        # Validate trước khi generate
        self._validate_before_generate()

        if self.report_type == 'pdf':
            return self.action_print_report()
        else:
            return self.action_export_excel()

    def action_print_report(self):
        """In báo cáo PDF"""
        self.ensure_one()
        data = self._prepare_report_data()
        return self.env.ref('hr_attendance_report.action_hr_attendance_monthly_report').report_action(self, data=data)

    def action_export_excel(self):
        """Xuất báo cáo Excel"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': f'/attendance/monthly/report/excel?wizard_id={self.id}',
            'target': 'new',
        }

    def action_preview_data(self):
        """Preview dữ liệu trước khi xuất báo cáo"""
        self.ensure_one()

        employees = self._get_employees()
        if not employees:
            raise UserError("Không tìm thấy nhân viên nào phù hợp với điều kiện lọc.")

        # Show preview in a new wizard or tree view
        return {
            'name': f'Preview - Báo cáo tháng {self.month}/{self.year}',
            'type': 'ir.actions.act_window',
            'res_model': 'hr.employee',
            'view_mode': 'tree',
            'domain': [('id', 'in', [emp['id'] for emp in employees])],
            'context': {
                'default_month': self.month,
                'default_year': self.year,
            },
            'target': 'new',
        }

    # Validation methods
    def _validate_before_generate(self):
        """Validate dữ liệu trước khi generate báo cáo"""
        self.ensure_one()

        # Check có nhân viên không
        employees = self._get_employees()
        if not employees:
            raise UserError(
                "Không tìm thấy nhân viên nào phù hợp với điều kiện lọc.\n\n"
                "Vui lòng kiểm tra lại:\n"
                "• Bộ lọc đã chọn\n"
                "• Phòng ban/nhân viên đã chọn\n"
                "• Trạng thái active của nhân viên"
            )

        # Check timezone
        user_tz = self._get_user_timezone()
        if not user_tz or user_tz.zone == 'UTC':
            _logger.warning(f"User {self.env.user.name} không có timezone được set, sử dụng UTC")

    # Core business methods
    def _prepare_report_data(self):
        """Chuẩn bị dữ liệu cho báo cáo"""
        self.ensure_one()

        # Tính số ngày trong tháng
        days_in_month = calendar.monthrange(self.year, int(self.month))[1]

        # Lấy danh sách nhân viên
        employees = self._get_employees()

        # Lấy dữ liệu chấm công
        attendance_data = self._get_attendance_data(employees)

        # Lấy dữ liệu nghỉ phép
        leave_data = self._get_leave_data(employees) if self.include_leaves else {}

        # Tính toán thống kê
        statistics = self._calculate_statistics(employees, attendance_data, leave_data, days_in_month)

        return {
            'wizard_id': self.id,
            'month': self.month,
            'year': self.year,
            'month_name': dict(self._fields['month'].selection)[self.month],
            'days_in_month': days_in_month,
            'employees': employees,
            'attendance_data': attendance_data,
            'leave_data': leave_data,
            'statistics': statistics,
            'show_summary': self.show_summary,
            'include_leaves': self.include_leaves,
            'filter_type': self.filter_type,
            'report_date': datetime.now().strftime('%d/%m/%Y %H:%M'),
            'user_name': self.env.user.name,
            'company_name': self.env.company.name,
        }

    def _get_employees(self):
        """Lấy danh sách nhân viên theo filter"""
        domain = [('active', '=', True)] if not self.include_inactive else []

        if self.filter_type == 'employee' and self.employee_ids:
            domain.append(('id', 'in', self.employee_ids.ids))
        elif self.filter_type == 'department' and self.department_ids:
            domain.append(('department_id', 'in', self.department_ids.ids))
        # filter_type == 'all' thì không thêm điều kiện gì

        employees = self.env['hr.employee'].search(domain, order='department_id, employee_code, name')

        return [{
            'id': emp.id,
            'name': emp.name,
            'employee_code': emp.employee_code or f'EMP{emp.id:04d}',
            'department': emp.department_id.name if emp.department_id else 'Chưa phân phòng ban',
            'job_title': emp.job_title or emp.job_id.name or 'N/A',
            'manager': emp.parent_id.name if emp.parent_id else '',
            'work_email': emp.work_email or '',
            'work_phone': emp.work_phone or '',
            'active': emp.active,
        } for emp in employees]

    def _get_user_timezone(self):
        """Lấy timezone của user hoặc company"""
        # Ưu tiên timezone của user
        user_tz = self.env.user.tz
        if not user_tz:
            # Fallback sang timezone của company
            user_tz = self.env.company.partner_id.tz
        if not user_tz:
            # Fallback cuối cùng là UTC
            user_tz = 'UTC'

        try:
            return pytz.timezone(user_tz)
        except:
            _logger.warning(f"Invalid timezone: {user_tz}, fallback to UTC")
            return pytz.timezone('UTC')

    def _get_attendance_data(self, employees):
        """Lấy dữ liệu chấm công theo tháng - Xử lý timezone chính xác"""

        # Lấy timezone của user hoặc company
        user_tz = self._get_user_timezone()

        # Tạo range ngày trong tháng theo timezone local
        days_in_month = calendar.monthrange(self.year, int(self.month))[1]

        # Convert local time range sang UTC để query
        try:
            local_start = user_tz.localize(datetime(self.year, int(self.month), 1, 0, 0, 0))
            local_end = user_tz.localize(datetime(self.year, int(self.month), days_in_month, 23, 59, 59))

            utc_start = local_start.astimezone(pytz.UTC).replace(tzinfo=None)
            utc_end = local_end.astimezone(pytz.UTC).replace(tzinfo=None)
        except Exception as e:
            _logger.error(f"Timezone conversion error: {e}")
            # Fallback to UTC
            utc_start = datetime(self.year, int(self.month), 1, 0, 0, 0)
            utc_end = datetime(self.year, int(self.month), days_in_month, 23, 59, 59)

        attendance_data = {}

        for emp in employees:
            employee_id = emp['id']
            attendance_data[employee_id] = {}

            # Lấy tất cả bản ghi chấm công trong tháng (query với UTC time)
            attendances = self.env['hr.attendance'].search([
                ('employee_id', '=', employee_id),
                ('check_in', '>=', utc_start),
                ('check_in', '<=', utc_end),
            ], order='check_in')

            # Xử lý dữ liệu theo ngày (convert về local timezone)
            for day in range(1, days_in_month + 1):
                current_date = date(self.year, int(self.month), day)

                # Filter attendances cho ngày hiện tại theo local timezone
                day_attendances = []
                for att in attendances:
                    try:
                        # Convert UTC check_in sang local timezone
                        utc_checkin = pytz.UTC.localize(att.check_in)
                        local_checkin = utc_checkin.astimezone(user_tz)

                        if local_checkin.date() == current_date:
                            day_attendances.append(att)
                    except Exception as e:
                        _logger.warning(f"Error converting attendance time: {e}")
                        continue

                if day_attendances:
                    try:
                        # Lấy checkin đầu tiên và checkout cuối cùng (convert sang local time)
                        first_checkin_utc = min(att.check_in for att in day_attendances)
                        first_checkin_local = pytz.UTC.localize(first_checkin_utc).astimezone(user_tz)

                        # Xử lý checkout
                        checkout_records = [att.check_out for att in day_attendances if att.check_out]
                        if checkout_records:
                            last_checkout_utc = max(checkout_records)
                            last_checkout_local = pytz.UTC.localize(last_checkout_utc).astimezone(user_tz)
                            checkout_time = last_checkout_local.strftime('%H:%M')
                        else:
                            checkout_time = ''

                        # Tính working hours
                        working_hours = 0
                        if checkout_records:
                            total_seconds = (last_checkout_local - first_checkin_local).total_seconds()
                            working_hours = round(total_seconds / 3600, 2)

                        attendance_data[employee_id][day] = {
                            'check_in': first_checkin_local.strftime('%H:%M'),
                            'check_out': checkout_time,
                            'working_hours': working_hours,
                            'has_data': True,
                            'attendance_count': len(day_attendances)
                        }
                    except Exception as e:
                        _logger.error(f"Error processing attendance for employee {employee_id}, day {day}: {e}")
                        attendance_data[employee_id][day] = {
                            'check_in': 'ERROR',
                            'check_out': 'ERROR',
                            'working_hours': 0,
                            'has_data': False,
                            'attendance_count': 0
                        }
                else:
                    attendance_data[employee_id][day] = {
                        'check_in': '',
                        'check_out': '',
                        'working_hours': 0,
                        'has_data': False,
                        'attendance_count': 0
                    }

        return attendance_data

    def _get_leave_data(self, employees):
        """Lấy dữ liệu nghỉ phép theo tháng - Xử lý timezone chính xác"""

        # Lấy timezone của user hoặc company
        user_tz = self._get_user_timezone()

        # Tạo range ngày trong tháng theo timezone local
        days_in_month = calendar.monthrange(self.year, int(self.month))[1]

        try:
            # Tạo date range cho tháng hiện tại
            month_start = date(self.year, int(self.month), 1)
            month_end = date(self.year, int(self.month), days_in_month)
        except Exception as e:
            _logger.error(f"Error creating date range: {e}")
            return {}

        leave_data = {}

        for emp in employees:
            employee_id = emp['id']
            leave_data[employee_id] = {}

            # Lấy tất cả đơn nghỉ phép đã approved trong tháng
            leaves = self.env['hr.leave'].search([
                ('employee_id', '=', employee_id),
                ('state', '=', 'validate'),
                ('request_date_from', '<=', month_end),
                ('request_date_to', '>=', month_start),
            ])

            # Xử lý từng đơn nghỉ phép
            for leave in leaves:
                try:
                    # Lấy range ngày nghỉ
                    leave_start = leave.request_date_from
                    leave_end = leave.request_date_to

                    # Xử lý từng ngày trong range nghỉ phép
                    current_date = leave_start
                    while current_date <= leave_end:
                        # Chỉ xử lý ngày trong tháng báo cáo
                        if current_date.month == int(self.month) and current_date.year == self.year:
                            day = current_date.day

                            # Xác định loại nghỉ (full day hay half day)
                            leave_type = 'full'
                            if leave.request_unit_half:
                                leave_type = 'half'
                            elif leave.request_unit_hours:
                                # Nếu nghỉ theo giờ, coi là half day nếu < 4 giờ
                                if leave.number_of_hours_display < 4:
                                    leave_type = 'half'

                            # Lưu thông tin nghỉ phép
                            leave_data[employee_id][day] = {
                                'has_leave': True,
                                'leave_type': leave_type,
                                'leave_name': leave.holiday_status_id.name or 'Nghỉ phép',
                                'leave_id': leave.id,
                                'leave_hours': leave.number_of_hours_display if leave.request_unit_hours else (
                                    4 if leave_type == 'half' else 8),
                                'leave_state': leave.state,
                            }

                        # Chuyển sang ngày tiếp theo
                        from datetime import timedelta
                        current_date += timedelta(days=1)

                except Exception as e:
                    _logger.error(f"Error processing leave for employee {employee_id}: {e}")
                    continue

            # Đảm bảo tất cả các ngày đều có entry (ngay cả khi không nghỉ)
            for day in range(1, days_in_month + 1):
                if day not in leave_data[employee_id]:
                    leave_data[employee_id][day] = {
                        'has_leave': False,
                        'leave_type': None,
                        'leave_name': '',
                        'leave_id': None,
                        'leave_hours': 0,
                        'leave_state': None,
                    }

        return leave_data

    def _calculate_statistics(self, employees, attendance_data, leave_data, days_in_month):
        """Tính toán thống kê báo cáo - bao gồm cả nghỉ phép"""

        total_employees = len(employees)
        total_days = days_in_month
        total_working_days = 0
        total_absent_days = 0
        total_leave_days = 0
        total_working_hours = 0

        employee_stats = {}

        for emp in employees:
            employee_id = emp['id']
            emp_working_days = 0
            emp_absent_days = 0
            emp_leave_days = 0
            emp_working_hours = 0

            for day in range(1, days_in_month + 1):
                attendance_day_data = attendance_data.get(employee_id, {}).get(day, {})
                leave_day_data = leave_data.get(employee_id, {}).get(day, {})

                has_attendance = attendance_day_data.get('has_data', False)
                has_leave = leave_day_data.get('has_leave', False)

                if has_leave:
                    # Có nghỉ phép
                    leave_type = leave_day_data.get('leave_type', 'full')
                    if leave_type == 'full':
                        emp_leave_days += 1
                    else:
                        emp_leave_days += 0.5
                        # Nếu nghỉ nửa ngày mà vẫn có chấm công thì tính working hours
                        if has_attendance:
                            emp_working_days += 0.5
                            emp_working_hours += attendance_day_data.get('working_hours', 0)
                        else:
                            emp_absent_days += 0.5
                elif has_attendance:
                    # Có chấm công bình thường
                    emp_working_days += 1
                    emp_working_hours += attendance_day_data.get('working_hours', 0)
                else:
                    # Không có dữ liệu gì
                    emp_absent_days += 1

            employee_stats[employee_id] = {
                'working_days': emp_working_days,
                'absent_days': emp_absent_days,
                'leave_days': emp_leave_days,
                'working_hours': round(emp_working_hours, 2),
                'attendance_rate': round((emp_working_days / total_days) * 100, 1) if total_days > 0 else 0
            }

            total_working_days += emp_working_days
            total_absent_days += emp_absent_days
            total_leave_days += emp_leave_days
            total_working_hours += emp_working_hours

        return {
            'total_employees': total_employees,
            'total_days': total_days,
            'total_working_days': total_working_days,
            'total_absent_days': total_absent_days,
            'total_leave_days': total_leave_days,
            'total_working_hours': round(total_working_hours, 2),
            'average_working_hours': round(total_working_hours / total_employees, 2) if total_employees > 0 else 0,
            'overall_attendance_rate': round((total_working_days / (total_employees * total_days)) * 100, 1) if (
                                                                                                                            total_employees * total_days) > 0 else 0,
            'employee_stats': employee_stats,
        }

    def _get_day_name(self, year, month, day):
        """Lấy tên thứ trong tuần theo timezone local"""
        try:
            # Lấy timezone của user
            user_tz = self._get_user_timezone()

            # Tạo datetime theo timezone local
            local_dt = user_tz.localize(datetime(year, month, day))
            day_names = ['Thứ Hai', 'Thứ Ba', 'Thứ Tư', 'Thứ Năm', 'Thứ Sáu', 'Thứ Bảy', 'Chủ Nhật']
            return day_names[local_dt.weekday()]
        except Exception as e:
            _logger.warning(f"Error getting day name: {e}")
            return ''

    def _get_weekend_days(self, year, month):
        """Lấy danh sách ngày cuối tuần trong tháng"""
        try:
            user_tz = self._get_user_timezone()
            days_in_month = calendar.monthrange(year, month)[1]
            weekend_days = []

            for day in range(1, days_in_month + 1):
                local_dt = user_tz.localize(datetime(year, month, day))
                # 5 = Saturday, 6 = Sunday
                if local_dt.weekday() in [5, 6]:
                    weekend_days.append(day)

            return weekend_days
        except Exception as e:
            _logger.warning(f"Error getting weekend days: {e}")
            return []