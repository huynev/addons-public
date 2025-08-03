# -*- coding: utf-8 -*-
import logging
from datetime import datetime, time, timedelta
from pytz import timezone

from odoo import models, _

_logger = logging.getLogger(__name__)


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    def _compute_worked_days(self, contract, day_from, day_to):
        """
        Override method to calculate worked days with logic:
        - Count days with complete attendance records (check-in + check-out)
        - Subtract leave days from worked days
        - Use resource calendar to determine full day vs half day

        Logic:
        - Day with attendance but no leave = 1.0 day
        - Day with attendance and 0.5 leave = 0.5 day
        - Day with attendance and 1.0 leave = 0.0 day
        - No attendance = 0.0 day

        Note: hr.attendance stores times in UTC, so we need to convert to employee timezone
        for proper date comparison
        """

        # Get employee timezone for proper date calculation
        employee_tz = self._get_employee_timezone(contract.employee_id)

        # Convert payslip period to employee timezone for accurate date range
        day_from_local = day_from
        day_to_local = day_to

        # If day_from/day_to are naive datetime, localize them to employee timezone
        if day_from.tzinfo is None:
            day_from_local = employee_tz.localize(day_from)
        if day_to.tzinfo is None:
            day_to_local = employee_tz.localize(day_to)

        # Convert to UTC for database query (since attendance times are stored in UTC)
        day_from_utc = day_from_local.astimezone(timezone('UTC'))
        day_to_utc = day_to_local.astimezone(timezone('UTC'))

        # Get attendance records for the period with both check-in and check-out
        attendances = self.env['hr.attendance'].search([
            ('employee_id', '=', contract.employee_id.id),
            ('check_in', '>=', day_from_utc),
            ('check_in', '<=', day_to_utc),
            ('check_out', '!=', False)  # Only count completed attendance records
        ])

        if not attendances:
            return {
                "name": "Ngày làm việc bình thường được trả lương 100% (từ chấm công)",
                "sequence": 1,
                "code": "WORK100",
                "number_of_days": 0.0,
                "number_of_hours": 0.0,
                "contract_id": contract.id,
            }

        work_calendar = contract.resource_calendar_id
        if not work_calendar:
            return {
                "name": "Ngày làm việc bình thường được trả lương 100% (từ chấm công)",
                "sequence": 1,
                "code": "WORK100",
                "number_of_days": 0.0,
                "number_of_hours": 0.0,
                "contract_id": contract.id,
            }

        # Get leave allocations for the period
        leaves = self.env['hr.leave'].search([
            ('employee_id', '=', contract.employee_id.id),
            ('date_from', '<=', day_to_local),
            ('date_to', '>=', day_from_local),
            ('state', '=', 'validate')
        ])

        # Calculate worked days considering attendance and leaves
        attendance_days = {}  # {date: worked_hours}
        leave_days = {}  # {date: leave_amount}
        total_worked_days = 0.0
        total_worked_hours = 0.0

        # Process attendance records
        for attendance in attendances:
            # Convert UTC check_in time to employee local time for date calculation
            check_in_local = attendance.check_in.replace(tzinfo=timezone('UTC')).astimezone(employee_tz)
            check_out_local = attendance.check_out.replace(tzinfo=timezone('UTC')).astimezone(employee_tz)

            # Get the date of attendance
            attendance_date = check_in_local.date()

            # Calculate worked hours for this attendance
            worked_hours = attendance.worked_hours

            # Add to attendance_days dict
            if attendance_date not in attendance_days:
                attendance_days[attendance_date] = 0.0
            attendance_days[attendance_date] += worked_hours

        # Process leave records
        for leave in leaves:
            leave_start = leave.date_from.astimezone(employee_tz).date()
            leave_end = leave.date_to.astimezone(employee_tz).date()

            # Calculate days between leave start and end
            current_date = leave_start
            while current_date <= leave_end:
                if current_date not in leave_days:
                    leave_days[current_date] = 0.0

                # Calculate leave amount for this day
                if leave.request_unit_half:
                    leave_days[current_date] += 0.5
                else:
                    leave_days[current_date] += 1.0

                current_date += timedelta(days=1)

        # Calculate final worked days
        for attendance_date, worked_hours in attendance_days.items():
            # Get work calendar intervals for this date
            day_start = employee_tz.localize(datetime.combine(attendance_date, datetime.min.time()))
            day_end = employee_tz.localize(datetime.combine(attendance_date, datetime.max.time()))

            # Get work intervals from calendar
            intervals = work_calendar._work_intervals_batch(day_start, day_end, contract.employee_id.resource_id)[
                contract.employee_id.resource_id.id]

            if not intervals:
                continue  # Skip non-working days

            # Calculate total scheduled hours for this day
            scheduled_hours = 0.0
            work_intervals = [(start, stop) for start, stop, meta in intervals]

            for start, stop in work_intervals:
                scheduled_hours += (stop - start).total_seconds() / 3600.0

            if scheduled_hours == 0:
                continue

            # Determine if it's full day or half day based on worked hours vs scheduled hours
            worked_day_ratio = min(worked_hours / scheduled_hours, 1.0)

            # Apply threshold logic to determine full/half day
            if worked_day_ratio >= 0.70:  # 75% threshold for full day
                worked_day_amount = 1.0
            elif worked_day_ratio >= 0.375:  # 37.5% threshold for half day
                worked_day_amount = 0.5
            else:
                worked_day_amount = 0.0

            # Subtract leave days
            leave_amount = leave_days.get(attendance_date, 0.0)
            final_worked_days = max(0.0, worked_day_amount - leave_amount)

            total_worked_days += final_worked_days
            total_worked_hours += worked_hours
        return {
            "name": "Ngày làm việc bình thường được trả lương 100% (từ chấm công)",
            "sequence": 1,
            "code": "WORK100",
            "number_of_days": round(total_worked_days, 2),
            "number_of_hours": round(total_worked_hours, 2),
            "contract_id": contract.id,
        }

    def _get_employee_timezone(self, employee):
        """
        Get employee timezone for proper date/time calculations

        Args:
            employee: hr.employee record

        Returns:
            pytz.timezone: Employee timezone object
        """
        # Try to get timezone from employee resource calendar
        if employee.resource_calendar_id and employee.resource_calendar_id.tz:
            try:
                return timezone(employee.resource_calendar_id.tz)
            except:
                pass

        # Try to get timezone from company
        if employee.company_id and hasattr(employee.company_id, 'resource_calendar_id'):
            if employee.company_id.resource_calendar_id and employee.company_id.resource_calendar_id.tz:
                try:
                    return timezone(employee.company_id.resource_calendar_id.tz)
                except:
                    pass

        # Fallback to UTC if no timezone found
        return timezone('UTC')