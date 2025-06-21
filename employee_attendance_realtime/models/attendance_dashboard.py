from odoo import models, fields, api
from datetime import datetime, date, timedelta
import pytz


class AttendanceDashboard(models.Model):
    _name = 'attendance.dashboard'
    _description = 'Attendance Realtime Helper'

    @api.model
    def get_attendance_data(self):
        """Get real-time attendance data for all employees"""
        # Get Vietnam timezone
        vietnam_tz = pytz.timezone('Asia/Ho_Chi_Minh')
        utc_tz = pytz.UTC

        # Get today in Vietnam timezone
        now_vietnam = datetime.now(vietnam_tz)
        today_vietnam = now_vietnam.date()

        # Convert to UTC for database query
        today_start_utc = vietnam_tz.localize(datetime.combine(today_vietnam, datetime.min.time())).astimezone(utc_tz)
        today_end_utc = today_start_utc + timedelta(days=1)

        employees = self.env['hr.employee'].search([('active', '=', True)])

        attendance_data = {
            'checked_in': [],
            'not_checked_in': [],
            'checked_out': [],
            'total_employees': len(employees),
            'last_update': now_vietnam.strftime('%H:%M:%S')
        }

        for employee in employees:
            # Get today's attendance records
            today_attendances = self.env['hr.attendance'].search([
                ('employee_id', '=', employee.id),
                ('check_in', '>=', today_start_utc),
                ('check_in', '<', today_end_utc)
            ], order='check_in desc')

            employee_data = {
                'id': employee.id,
                'name': employee.name,
                'department': employee.department_id.name if employee.department_id else 'No Department',
                'job_title': employee.job_title or 'No Job Title',
                'image_url': f'/web/image/hr.employee/{employee.id}/image_1920/50x50' if employee.image_1920 else '/hr/static/src/img/default_image.png'
            }

            if not today_attendances:
                # Employee hasn't checked in today
                attendance_data['not_checked_in'].append(employee_data)
            else:
                latest_attendance = today_attendances[0]

                # Convert check_in time to Vietnam timezone
                check_in_vietnam = latest_attendance.check_in.replace(tzinfo=utc_tz).astimezone(vietnam_tz)

                if latest_attendance.check_out:
                    # Employee has checked out
                    check_out_vietnam = latest_attendance.check_out.replace(tzinfo=utc_tz).astimezone(vietnam_tz)
                    employee_data.update({
                        'check_in_time': check_in_vietnam.strftime('%H:%M'),
                        'check_out_time': check_out_vietnam.strftime('%H:%M'),
                        'worked_hours': self._calculate_worked_hours(check_in_vietnam, check_out_vietnam)
                    })
                    attendance_data['checked_out'].append(employee_data)
                else:
                    # Employee is currently checked in
                    employee_data.update({
                        'check_in_time': check_in_vietnam.strftime('%H:%M'),
                        'working_hours': self._calculate_working_hours(check_in_vietnam, now_vietnam)
                    })
                    attendance_data['checked_in'].append(employee_data)

        return attendance_data

    def _calculate_worked_hours(self, check_in, check_out):
        """Calculate worked hours between check in and check out"""
        if check_in and check_out:
            duration = check_out - check_in
            hours = duration.total_seconds() / 3600
            return f"{hours:.1f}h"
        return "0h"

    def _calculate_working_hours(self, check_in, current_time):
        """Calculate current working hours since check in"""
        if check_in and current_time:
            duration = current_time - check_in
            hours = duration.total_seconds() / 3600
            return f"{hours:.1f}h"
        return "0h"