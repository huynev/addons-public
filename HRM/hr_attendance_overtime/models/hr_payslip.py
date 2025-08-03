from odoo import models, fields, api
from datetime import datetime, timedelta
import pytz


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    def get_worked_day_lines(self, contracts, date_from, date_to):
        """Override để thêm các dòng worked days cho nghỉ phép"""
        res = super().get_worked_day_lines(contracts, date_from, date_to)

        # Tính toán ngày nghỉ phép nguyên ngày và nửa ngày
        leave_data = self._calculate_leave_days()

        # Tính toán số ngày xả ca
        discharge_days = self._calculate_discharge_days()

        # Kiểm tra và cập nhật/thêm LEAVE110_FULLDAY
        fullday_exists = False
        for line in res:
            if line.get('code') == 'LEAVE110_FULLDAY':
                fullday_exists = True
                line.update({
                    'number_of_days': leave_data['full_days'],
                    'number_of_hours': leave_data['full_days'] * self._get_hours_per_day(),
                })
                break

        if not fullday_exists and leave_data['full_days'] > 0:
            res.append({
                'sequence': 25,
                'name': 'Nghỉ nguyên ngày',
                'code': 'LEAVE110_FULLDAY',
                'number_of_days': leave_data['full_days'],
                'number_of_hours': leave_data['full_days'] * self._get_hours_per_day(),
                'contract_id': self.contract_id.id,
            })

        # Kiểm tra và cập nhật/thêm LEAVE110_HALFDAY
        halfday_exists = False
        for line in res:
            if line.get('code') == 'LEAVE110_HALFDAY':
                halfday_exists = True
                line.update({
                    'number_of_days': leave_data['half_days'],
                    'number_of_hours': leave_data['half_days'] * (self._get_hours_per_day() / 2),
                })
                break

        if not halfday_exists and leave_data['half_days'] > 0:
            res.append({
                'sequence': 26,
                'name': 'Nghỉ nửa ngày',
                'code': 'LEAVE110_HALFDAY',
                'number_of_days': leave_data['half_days'],
                'number_of_hours': leave_data['half_days'] * (self._get_hours_per_day() / 2),
                'contract_id': self.contract_id.id,
            })

        # Kiểm tra và cập nhật/thêm DISCHARGE110 (Ngày xả ca)
        discharge_exists = False
        for line in res:
            if line.get('code') == 'DISCHARGE110':
                discharge_exists = True
                line.update({
                    'number_of_days': discharge_days,
                    'number_of_hours': discharge_days * self._get_hours_per_day(),
                })
                break

        if not discharge_exists and discharge_days > 0:
            res.append({
                'sequence': 27,
                'name': 'Ngày xả ca',
                'code': 'DISCHARGE110',
                'number_of_days': discharge_days,
                'number_of_hours': discharge_days * self._get_hours_per_day(),
                'contract_id': self.contract_id.id,
            })

        # Loại bỏ các dòng có số ngày = 0
        res = [line for line in res if not (
                line.get('code') in ['LEAVE110_FULLDAY', 'LEAVE110_HALFDAY', 'DISCHARGE110'] and
                line.get('number_of_days', 0) <= 0
        )]

        return res

    def _calculate_discharge_days(self):
        """Tính toán số ngày xả ca từ hr.attendance"""
        if not self.employee_id:
            return 0

        # Lấy múi giờ từ user hoặc company
        user_tz = pytz.timezone(self.env.user.tz or 'Asia/Ho_Chi_Minh')

        # Chuyển đổi date_from và date_to sang UTC để so sánh với check_in
        # Bắt đầu ngày: 00:00:00 theo múi giờ địa phương -> UTC
        date_from_start = user_tz.localize(
            datetime.combine(self.date_from, datetime.min.time())
        ).astimezone(pytz.UTC).replace(tzinfo=None)

        # Kết thúc ngày: 23:59:59 theo múi giờ địa phương -> UTC
        date_to_end = user_tz.localize(
            datetime.combine(self.date_to, datetime.max.time())
        ).astimezone(pytz.UTC).replace(tzinfo=None)

        # Lấy tất cả attendance có đánh dấu xả ca trong khoảng thời gian bảng lương
        discharge_attendances = self.env['hr.attendance'].search([
            ('employee_id', '=', self.employee_id.id),
            ('is_discharge_shift', '=', True),
            ('check_in', '>=', date_from_start),
            ('check_in', '<=', date_to_end),
        ])

        return len(discharge_attendances)

    def _calculate_leave_days(self):
        """Tính toán số ngày nghỉ phép nguyên ngày và nửa ngày từ dữ liệu có sẵn"""
        if not self.employee_id:
            return {'full_days': 0, 'half_days': 0}

        # Lấy tất cả nghỉ phép được duyệt trong khoảng thời gian bảng lương
        leaves = self.env['hr.leave'].search([
            ('employee_id', '=', self.employee_id.id),
            ('state', '=', 'validate'),
            ('request_date_from', '>=', self.date_from),
            ('request_date_to', '<=', self.date_to),
        ])

        # Lấy hours_per_day từ calendar resource của nhân viên
        hours_per_day = self._get_hours_per_day()

        full_days = 0
        half_days = 0

        for leave in leaves:
            # Sử dụng dữ liệu có sẵn trong hr.leave để phân loại
            if leave.request_unit_half:
                # Nghỉ nửa ngày
                half_days += leave.number_of_days
            elif leave.request_unit_hours:
                # Nghỉ theo giờ - tính toán dựa trên số giờ so với hours_per_day của calendar
                if leave.number_of_hours_display <= (hours_per_day / 2):
                    half_days += leave.number_of_days
                else:
                    full_days += leave.number_of_days
            else:
                # Nghỉ nguyên ngày
                full_days += leave.number_of_days

        return {
            'full_days': full_days,
            'half_days': half_days
        }

    def _get_hours_per_day(self):
        """Lấy số giờ làm việc mỗi ngày từ calendar resource"""
        if not self.employee_id:
            return 8  # Giá trị mặc định

        # Thử lấy từ resource_calendar_id của employee trước
        if self.employee_id.resource_calendar_id:
            return self.employee_id.resource_calendar_id.hours_per_day

        # Nếu không có thì lấy từ resource_id.calendar_id
        if self.employee_id.resource_id and self.employee_id.resource_id.calendar_id:
            return self.employee_id.resource_id.calendar_id.hours_per_day

        # Cuối cùng lấy từ company default calendar
        if self.company_id.resource_calendar_id:
            return self.company_id.resource_calendar_id.hours_per_day

        return 8  # Fallback default
        """Tính toán số ngày nghỉ phép nguyên ngày và nửa ngày từ dữ liệu có sẵn"""
        if not self.employee_id:
            return {'full_days': 0, 'half_days': 0}

        # Lấy tất cả nghỉ phép được duyệt trong khoảng thời gian bảng lương
        leaves = self.env['hr.leave'].search([
            ('employee_id', '=', self.employee_id.id),
            ('state', '=', 'validate'),
            ('request_date_from', '>=', self.date_from),
            ('request_date_to', '<=', self.date_to),
        ])

        # Lấy hours_per_day từ calendar resource của nhân viên
        hours_per_day = self._get_hours_per_day()

        full_days = 0
        half_days = 0

        for leave in leaves:
            # Sử dụng dữ liệu có sẵn trong hr.leave để phân loại
            if leave.request_unit_half:
                # Nghỉ nửa ngày
                half_days += leave.number_of_days
            elif leave.request_unit_hours:
                # Nghỉ theo giờ - tính toán dựa trên số giờ so với hours_per_day của calendar
                if leave.number_of_hours_display <= (hours_per_day / 2):
                    half_days += leave.number_of_days
                else:
                    full_days += leave.number_of_days
            else:
                # Nghỉ nguyên ngày
                full_days += leave.number_of_days

        return {
            'full_days': full_days,
            'half_days': half_days
        }