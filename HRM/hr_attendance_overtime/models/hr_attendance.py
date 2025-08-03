from odoo import models, fields, api
from datetime import datetime, timedelta, time
from pytz import UTC
import pytz


class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    # Overtime fields
    overtime_hours = fields.Float(
        string='Overtime Hours',
        compute='_compute_overtime_hours',
        store=True,
        help='Tổng số giờ tăng ca được tính toán tự động (bao gồm tăng ca trước và sau giờ làm việc)'
    )
    overtime_early = fields.Float(
        string='Early Overtime (before work)',
        compute='_compute_overtime_hours',
        store=True,
        help='Tăng ca trước giờ làm việc (vào sớm hơn 1 tiếng)'
    )
    overtime_regular = fields.Float(
        string='Regular Overtime (before 18h)',
        compute='_compute_overtime_hours',
        store=True
    )
    overtime_evening = fields.Float(
        string='Evening Overtime (18h-21h)',
        compute='_compute_overtime_hours',
        store=True
    )
    overtime_night = fields.Float(
        string='Night Overtime (after 21h)',
        compute='_compute_overtime_hours',
        store=True
    )
    overtime_holiday = fields.Float(
        string='Holiday Overtime',
        compute='_compute_overtime_hours',
        store=True
    )

    is_discharge_shift = fields.Boolean(
        string='Xả ca',
        default=False,
        help='Đánh dấu ngày công hôm nay nhân viên xả ca'
    )

    # Late/Early fields
    late_minutes = fields.Integer(
        string='Late Minutes',
        compute='_compute_late_early',
        store=True,
        help='Số phút đi trễ so với giờ quy định'
    )

    early_minutes = fields.Integer(
        string='Early Minutes',
        compute='_compute_late_early',
        store=True,
        help='Số phút về sớm so với giờ quy định'
    )

    scheduled_check_in = fields.Datetime(
        string='Scheduled Check In',
        compute='_compute_late_early',
        store=True,
        help='Giờ vào theo lịch làm việc'
    )

    scheduled_check_out = fields.Datetime(
        string='Scheduled Check Out',
        compute='_compute_late_early',
        store=True,
        help='Giờ ra theo lịch làm việc'
    )

    is_late = fields.Boolean(
        string='Is Late',
        compute='_compute_late_early',
        store=True,
        help='Có đi trễ hay không'
    )

    is_early = fields.Boolean(
        string='Is Early',
        compute='_compute_late_early',
        store=True,
        help='Có về sớm hay không'
    )

    @api.depends('employee_id', 'check_in', 'check_out')
    def _compute_late_early(self):
        """Tính toán đi trễ/về sớm dựa trên lịch làm việc"""
        for attendance in self:
            # Reset values
            attendance.late_minutes = 0
            attendance.early_minutes = 0
            attendance.scheduled_check_in = False
            attendance.scheduled_check_out = False
            attendance.is_late = False
            attendance.is_early = False

            # Kiểm tra dữ liệu cần thiết
            if not attendance.employee_id or not attendance.check_in or not attendance.check_out:
                continue

            # Lấy hợp đồng và lịch làm việc
            contract = attendance.employee_id.contract_id
            if not contract or not contract.resource_calendar_id:
                continue

            work_calendar = contract.resource_calendar_id

            # Tính toán late/early cho ngày này
            result = attendance._calculate_late_early_for_day(work_calendar)

            # Cập nhật các field
            attendance.late_minutes = result['late_minutes']
            attendance.early_minutes = result['early_minutes']
            attendance.scheduled_check_in = result['scheduled_check_in']
            attendance.scheduled_check_out = result['scheduled_check_out']
            attendance.is_late = result['late_minutes'] > 0
            attendance.is_early = result['early_minutes'] > 0

    def _calculate_late_early_for_day(self, work_calendar):
        """Tính toán đi trễ/về sớm cho bản ghi attendance này"""

        def _convert_datetime_to_target_timezone(dt, target_tz_name='Asia/Ho_Chi_Minh'):
            """Chuyển đổi datetime từ UTC sang múi giờ đích"""
            if not dt:
                return dt

            if not dt.tzinfo:
                dt = dt.replace(tzinfo=pytz.UTC)
            elif dt.tzinfo != pytz.UTC:
                dt = dt.astimezone(pytz.UTC)

            target_tz = pytz.timezone(target_tz_name)
            target_dt = dt.astimezone(target_tz)
            return target_dt

        def _convert_to_naive_utc(dt):
            """Convert datetime to naive UTC (for Odoo datetime fields)"""
            if not dt:
                return None

            # If timezone-aware, convert to UTC first
            if dt.tzinfo:
                dt = dt.astimezone(pytz.UTC)

            # Return naive datetime (Odoo expects this)
            return dt.replace(tzinfo=None)

        result = {
            'scheduled_check_in': None,
            'scheduled_check_out': None,
            'late_minutes': 0,
            'early_minutes': 0
        }

        # Lấy ngày chấm công
        attendance_date = _convert_datetime_to_target_timezone(
            self.check_in,
            work_calendar.tz or 'Asia/Ho_Chi_Minh'
        ).date()

        # Tạo datetime cho ngày làm việc
        day_start = datetime.combine(attendance_date, datetime.min.time()).replace(tzinfo=UTC)
        day_end = datetime.combine(attendance_date, datetime.max.time()).replace(tzinfo=UTC)

        # Lấy khoảng thời gian làm việc theo lịch cho ngày này
        intervals = work_calendar._work_intervals_batch(day_start, day_end)[False]
        work_intervals = [(start, stop) for start, stop, meta in intervals]

        # Nếu không có lịch làm việc cho ngày này, không tính đi trễ/về sớm
        if not work_intervals:
            return result

        # Giả định work_intervals đã được sắp xếp theo thời gian
        # Lấy ca sáng và ca chiều
        morning_shift = work_intervals[0]  # (7:30-11:30)
        afternoon_shift = work_intervals[1] if len(work_intervals) > 1 else None  # (13:00-17:30)

        # Cập nhật thời gian theo lịch - CONVERT TO NAIVE UTC
        result['scheduled_check_in'] = _convert_to_naive_utc(morning_shift[0])  # 7:30
        result['scheduled_check_out'] = _convert_to_naive_utc(
            afternoon_shift[1] if afternoon_shift else morning_shift[1]
        )  # 17:30 hoặc 11:30

        # Đảm bảo datetime có múi giờ
        check_in = self.check_in if self.check_in.tzinfo else self.check_in.replace(tzinfo=UTC)
        check_out = self.check_out if self.check_out.tzinfo else self.check_out.replace(tzinfo=UTC)

        # Tính đi trễ (nếu check-in sau thời gian bắt đầu ca sáng)
        if check_in > morning_shift[0]:
            late_delta = (check_in - morning_shift[0]).total_seconds() / 60
            if int(late_delta) >= 240:
                if check_in > afternoon_shift[0]:
                    late_delta = (check_in - afternoon_shift[0]).total_seconds() / 60
                else:
                    late_delta = 0
            result['late_minutes'] = int(late_delta)

        # Tính về sớm dựa trên ca làm việc
        if afternoon_shift:
            # Nếu có ca chiều (ngày làm việc đầy đủ)
            if check_out < afternoon_shift[1]:  # Check-out trước 17:30
                # Kiểm tra xem có phải đang trong giờ nghỉ trưa không (11:30-13:00)
                lunch_break_start = morning_shift[1]  # 11:30
                lunch_break_end = afternoon_shift[0]  # 13:00

                if check_out <= lunch_break_start or check_out >= lunch_break_end:
                    # Nếu về trước 11:30 hoặc sau 13:00 thì mới tính về sớm
                    if check_out >= lunch_break_end:  # Về sau 13:00
                        early_delta = (afternoon_shift[1] - check_out).total_seconds() / 60
                    else:  # Về trước 11:30
                        early_delta = (morning_shift[1] - check_out).total_seconds() / 60
                        result['scheduled_check_out'] = _convert_to_naive_utc(morning_shift[1])
                    result['early_minutes'] = int(early_delta)
        else:
            # Nếu chỉ có ca sáng
            if check_out < morning_shift[1]:  # Check-out trước 11:30
                early_delta = (morning_shift[1] - check_out).total_seconds() / 60
                result['early_minutes'] = int(early_delta)
                result['scheduled_check_out'] = _convert_to_naive_utc(morning_shift[1])

        return result

    def action_recompute_overtime(self):
        """
        Action để tính lại overtime hours và late/early cho các record được chọn
        """
        for record in self:
            record._compute_overtime_hours()
            record._compute_late_early()

        # Hiển thị thông báo thành công
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Thành công!',
                'message': f'Đã tính lại overtime và late/early cho {len(self)} bản ghi.',
                'type': 'success',
                'sticky': False,
            }
        }

    def action_recompute_single_overtime(self):
        """
        Action để tính lại overtime hours và late/early cho 1 record (dùng trong form view)
        """
        self.ensure_one()
        self._compute_overtime_hours()
        self._compute_late_early()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Thành công!',
                'message': 'Đã tính lại overtime và late/early cho bản ghi này.',
                'type': 'success',
                'sticky': False,
            }
        }

    def action_recompute_late_early(self):
        """
        Action để chỉ tính lại late/early cho các record được chọn
        """
        for record in self:
            record._compute_late_early()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Thành công!',
                'message': f'Đã tính lại late/early cho {len(self)} bản ghi.',
                'type': 'success',
                'sticky': False,
            }
        }

    @api.depends('employee_id', 'check_in', 'check_out')
    def _compute_overtime_hours(self):
        for attendance in self:
            # Reset all overtime fields
            attendance.overtime_hours = 0.0
            attendance.overtime_regular = 0.0
            attendance.overtime_evening = 0.0
            attendance.overtime_night = 0.0
            attendance.overtime_holiday = 0.0
            attendance.overtime_early = 0.0

            # Kiểm tra dữ liệu cần thiết
            if not attendance.employee_id or not attendance.check_in or not attendance.check_out:
                continue

            # Những nhân viên thuộc nhóm văn phòng hoặc bảo vệ không tính tăng ca
            if (attendance.employee_id.department_id.parent_id.name == "Văn phòng" or
                    attendance.employee_id.department_id.name == "Bảo vệ"):
                continue

            # Lấy hợp đồng hiện tại của nhân viên
            contract = attendance.employee_id.contract_id
            if not contract or not contract.resource_calendar_id:
                continue

            work_calendar = contract.resource_calendar_id

            # Tính toán giờ tăng ca
            overtime_details = attendance._calculate_attendance_overtime(work_calendar)

            # Cập nhật các field
            attendance.overtime_early = overtime_details['early']
            # Chỉ tính tăng ca sớm cho nhân viên Kim Hậu và Nguyễn Trương Thanh
            if attendance.employee_id.employee_code != '240064' and attendance.employee_id.employee_code != '190124':
                overtime_details['total'] = overtime_details['total'] - attendance.overtime_early
                attendance.overtime_early = 0

            attendance.overtime_regular = overtime_details['regular']
            attendance.overtime_evening = overtime_details['evening']
            attendance.overtime_night = overtime_details['night']
            attendance.overtime_holiday = overtime_details['holiday']
            attendance.overtime_hours = overtime_details['total']
            if attendance.overtime_evening > 0:
                attendance.overtime_hours -= attendance.overtime_regular
                attendance.overtime_regular = 0

            if attendance.overtime_regular <= 0.5:
                attendance.overtime_regular = 0
                if attendance.overtime_hours == 0.5 and attendance.overtime_evening == 0 and attendance.overtime_night == 0:
                    attendance.overtime_hours -= 0.5

    def _calculate_attendance_overtime(self, work_calendar):
        """Tính toán số giờ tăng ca cho bản ghi attendance này"""

        def _convert_datetime_to_target_timezone(dt, target_tz_name='Asia/Ho_Chi_Minh'):
            """Chuyển đổi datetime từ UTC sang múi giờ đích"""
            if not dt:
                return dt

            if not dt.tzinfo:
                dt = dt.replace(tzinfo=pytz.UTC)
            elif dt.tzinfo != pytz.UTC:
                dt = dt.astimezone(pytz.UTC)

            target_tz = pytz.timezone(target_tz_name)
            target_dt = dt.astimezone(target_tz)
            return target_dt

        # Lấy ngày chấm công
        attendance_date = _convert_datetime_to_target_timezone(
            self.check_in,
            work_calendar.tz or 'Asia/Ho_Chi_Minh'
        ).date()

        # Tạo datetime cho ngày làm việc
        day_start = datetime.combine(attendance_date, datetime.min.time()).replace(tzinfo=UTC)
        day_end = datetime.combine(attendance_date, datetime.max.time()).replace(tzinfo=UTC)

        # Lấy múi giờ
        user_tz = pytz.timezone(self.env.user.tz or work_calendar.tz or 'Asia/Ho_Chi_Minh')

        # Tạo thời điểm 18:00 và 21:00 ở múi giờ địa phương
        local_evening = datetime.combine(attendance_date, time(18, 0))
        local_night = datetime.combine(attendance_date, time(21, 0))

        # Chuyển đổi sang UTC
        evening_start = user_tz.localize(local_evening).astimezone(UTC)
        night_start = user_tz.localize(local_night).astimezone(UTC)

        # Kết quả trả về
        result = {
            'early': 0.0,
            'regular': 0.0,
            'evening': 0.0,
            'night': 0.0,
            'holiday': 0.0,
            'total': 0.0
        }

        # Lấy giờ làm việc theo lịch
        scheduled_hours = work_calendar.get_work_hours_count(
            day_start, day_end,
            compute_leaves=True
        )

        # Lấy các khoảng thời gian làm việc
        intervals = work_calendar._work_intervals_batch(day_start, day_end)[False]
        work_intervals = [(start, stop) for start, stop, meta in intervals]

        # Kiểm tra ngày nghỉ
        is_rest_day = scheduled_hours <= 0 or not work_intervals

        if is_rest_day:
            # Tất cả thời gian làm việc trong ngày nghỉ đều tính là tăng ca
            check_in = self.check_in if self.check_in.tzinfo else self.check_in.replace(tzinfo=UTC)
            check_out = self.check_out if self.check_out.tzinfo else self.check_out.replace(tzinfo=UTC)

            # Đảm bảo thời gian nằm trong ngày
            check_in = max(check_in, day_start.replace(tzinfo=None).replace(tzinfo=UTC))
            check_out = min(check_out, day_end.replace(tzinfo=None).replace(tzinfo=UTC))

            if check_out > check_in:
                hours = (check_out - check_in).total_seconds() / 3600
                result['holiday'] = self._round_overtime_minutes(max(0, hours))
                result['total'] = result['holiday']
                return result

        if not work_intervals:
            return result

        # Lấy thời gian bắt đầu và kết thúc ca làm việc
        work_start = min(start for start, _ in work_intervals)
        work_end = max(end for _, end in work_intervals)

        # Đảm bảo datetime có múi giờ
        check_in = self.check_in if self.check_in.tzinfo else self.check_in.replace(tzinfo=UTC)
        check_out = self.check_out if self.check_out.tzinfo else self.check_out.replace(tzinfo=UTC)

        # Xử lý tăng ca trước giờ làm việc
        # Điều kiện: vào sớm hơn 1 tiếng mới tính tăng ca
        # Phần tăng ca: toàn bộ thời gian từ check-in đến bắt đầu ca làm việc
        early_overtime_threshold = work_start - timedelta(hours=1)
        if check_in < early_overtime_threshold:
            # Tính toàn bộ thời gian từ check-in đến bắt đầu ca làm việc
            early_hours = (work_start - check_in).total_seconds() / 3600
            result['early'] = self._round_overtime_minutes(max(0, early_hours))

        # Xử lý tăng ca sau giờ làm việc
        if check_out > work_end:
            overtime_start = work_end
            overtime_end = check_out

            # Phân loại theo khung giờ
            self._categorize_overtime(overtime_start, overtime_end, evening_start, night_start, result)

        # Cập nhật tổng số giờ tăng ca
        result['total'] = result['early'] + result['regular'] + result['evening'] + result['night'] + result['holiday']

        # Làm tròn giờ tăng ca
        for key in result:
            if key != 'total':
                result[key] = self._round_overtime_minutes(result[key])

        # Tính lại total sau khi làm tròn
        result['total'] = result['early'] + result['regular'] + result['evening'] + result['night'] + result['holiday']

        return result

    def _categorize_overtime(self, start_time, end_time, evening_start, night_start, result):
        """Phân loại thời gian tăng ca theo khung giờ"""
        if end_time <= start_time:
            return

        regular_hours = 0
        evening_hours = 0
        night_hours = 0

        # Phần trước 18h (tăng ca thường)
        if start_time < evening_start:
            regular_end = min(end_time, evening_start)
            regular_hours = (regular_end - start_time).total_seconds() / 3600

        # Phần từ 18h đến 21h (tăng ca tối)
        if start_time < night_start and end_time > evening_start:
            evening_start_time = max(start_time, evening_start)
            evening_end_time = min(end_time, night_start)
            if evening_end_time > evening_start_time:
                evening_hours = (evening_end_time - evening_start_time).total_seconds() / 3600

        # Phần sau 21h (tăng ca đêm)
        if end_time > night_start:
            night_start_time = max(start_time, night_start)
            night_hours = (end_time - night_start_time).total_seconds() / 3600

        # Cập nhật kết quả
        result['regular'] += regular_hours
        result['evening'] += evening_hours
        result['night'] += night_hours

    def _round_overtime_minutes(self, hours):
        """
        Làm tròn giờ tăng ca theo quy tắc:
        - 0-24 phút: làm tròn thành 0
        - 25-44 phút: làm tròn thành 0.5 giờ
        - 45-60 phút: làm tròn thành 1 giờ
        """
        if hours <= 0:
            return 0.0

        whole_hours = int(hours)
        minutes = (hours - whole_hours) * 60

        if minutes <= 24:
            return float(whole_hours)
        elif minutes <= 44:
            return whole_hours + 0.5
        else:
            return whole_hours + 1.0

    @api.model_create_multi
    def create(self, vals_list):
        """Override create để tự động tính toán overtime và late/early khi tạo mới"""
        records = super(HrAttendance, self).create(vals_list)
        # Trigger compute for overtime and late/early fields
        records._compute_overtime_hours()
        records._compute_late_early()
        return records

    def write(self, vals):
        """Override write để tự động tính toán lại overtime và late/early khi cập nhật"""
        result = super(HrAttendance, self).write(vals)
        # Nếu thay đổi thông tin liên quan đến overtime hoặc late/early, tính toán lại
        if any(field in vals for field in ['check_in', 'check_out', 'employee_id']):
            self._compute_overtime_hours()
            self._compute_late_early()
        return result