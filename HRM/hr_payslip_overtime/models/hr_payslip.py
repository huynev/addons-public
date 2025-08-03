from odoo import models, fields, api
from datetime import datetime, timedelta, time
from pytz import UTC
import pytz


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    overtime_plan_line_ids = fields.One2many('hr.overtime.plan', 'payslip_id', string='Overtime Plans')
    overtime_hours = fields.Float(string='Overtime Hours', compute='_compute_overtime_summary')
    overtime_standard_pay = fields.Float(string='Standard Pay', compute='_compute_overtime_summary')
    overtime_actual_pay = fields.Float(string='Actual Overtime Pay', compute='_compute_overtime_summary')

    @api.depends('overtime_plan_line_ids', 'overtime_plan_line_ids.standard_pay',
                 'overtime_plan_line_ids.actual_overtime_pay')
    def _compute_overtime_summary(self):
        for payslip in self:
            payslip.overtime_hours = sum(payslip.overtime_plan_line_ids.mapped('overtime_hours'))
            payslip.overtime_standard_pay = sum(payslip.overtime_plan_line_ids.mapped('standard_pay'))
            payslip.overtime_actual_pay = sum(payslip.overtime_plan_line_ids.mapped('actual_overtime_pay'))

    # Hook into the create method to automatically calculate overtime
    @api.model
    def create(self, vals):
        payslip = super(HrPayslip, self).create(vals)
        # Automatically calculate overtime when a payslip is created
        payslip.action_get_overtime_data
        return payslip

    # Hook into the compute_sheet method which is called when calculating the payslip
    def compute_sheet(self):
        # First calculate overtime data
        self.action_get_overtime_data()
        # Then continue with original compute_sheet logic
        return super(HrPayslip, self).compute_sheet()

    def action_get_overtime_data(self):
        """Tự động lấy dữ liệu tăng ca từ dữ liệu chấm công đã tính sẵn"""
        for payslip in self:
            # Xóa dữ liệu tăng ca cũ
            payslip.overtime_plan_line_ids.unlink()

            # Kiểm tra xem có hợp đồng và nhân viên không
            if not payslip.employee_id or not payslip.contract_id:
                continue

            # Những nhân viên thuộc nhóm văn phòng hoặc bảo vệ không tính tăng ca
            if (payslip.employee_id.department_id.parent_id.name == "Văn phòng" or
                    payslip.employee_id.department_id.name == "Bảo vệ"):
                continue

            # Chuyển đổi date_from và date_to sang UTC để search đúng
            # Vì check_in và check_out trong hr.attendance được lưu ở múi giờ UTC
            vn_tz = pytz.timezone('Asia/Ho_Chi_Minh')

            # Tạo datetime ở múi giờ Việt Nam rồi chuyển sang UTC
            date_from_vn = vn_tz.localize(datetime.combine(payslip.date_from, datetime.min.time()))
            date_to_vn = vn_tz.localize(datetime.combine(payslip.date_to, datetime.max.time()))

            date_from_utc = date_from_vn.astimezone(pytz.UTC).replace(tzinfo=None)
            date_to_utc = date_to_vn.astimezone(pytz.UTC).replace(tzinfo=None)
            # Lấy dữ liệu chấm công trong khoảng thời gian của phiếu lương

            attendances = self.env['hr.attendance'].search([
                ('employee_id', '=', payslip.employee_id.id),
                ('check_in', '>=', date_from_utc),
                ('check_out', '<=', date_to_utc),
                ('check_out', '!=', False),  # Chỉ lấy những bản ghi đã check-out
                ('overtime_hours', '>', 0)  # Chỉ lấy những bản ghi có tăng ca
            ])

            # Xử lý từng bản ghi attendance
            for attendance in attendances:
                # Lấy ngày chấm công (chuyển từ UTC về múi giờ local để lấy ngày)
                check_in_local = attendance.check_in
                check_out_local = attendance.check_out
                if attendance.check_in.tzinfo:
                    # Nếu có timezone info, chuyển về múi giờ Việt Nam
                    check_in_local = attendance.check_in.astimezone(vn_tz)
                if attendance.check_out.tzinfo:
                    # Nếu có timezone info, chuyển về múi giờ Việt Nam
                    check_out_local = attendance.check_out.astimezone(vn_tz)

                attendance_date = check_in_local.date()

                # Tạo overtime plan cho tăng ca trước giờ làm việc (early overtime)
                if attendance.overtime_early > 0:
                    self.env['hr.overtime.plan'].create({
                        'name': f'Tăng ca sớm (trước ca làm việc) ngày {attendance_date}',
                        'date_from': check_in_local.date(),
                        'date_to': check_out_local.date(),
                        'overtime_hours': attendance.overtime_early,
                        'payment_percentage': 150.0,  # 150% lương cho tăng ca sớm
                        'payslip_id': payslip.id,
                    })

                # Điều kiện đặc biệt: Tăng ca từ 17-18h chỉ tính khi không có tăng ca từ 18h trở đi
                if (attendance.overtime_regular > 0 and
                        attendance.overtime_evening <= 0 and
                        attendance.overtime_night <= 0):
                    self.env['hr.overtime.plan'].create({
                        'name': f'Tăng ca thường (trước 18h) ngày {attendance_date}',
                        'date_from': check_in_local.date(),
                        'date_to': check_out_local.date(),
                        'overtime_hours': attendance.overtime_regular,
                        'payment_percentage': 150.0,  # 150% lương cho tăng ca thường
                        'payslip_id': payslip.id,
                    })

                # Tạo overtime plan cho tăng ca buổi tối (18h-21h)
                if attendance.overtime_evening > 0:
                    self.env['hr.overtime.plan'].create({
                        'name': f'Tăng ca tối (18h-21h) ngày {attendance_date}',
                        'date_from': check_in_local.date(),
                        'date_to': check_out_local.date(),
                        'overtime_hours': attendance.overtime_evening,
                        'payment_percentage': 150.0,  # 150% lương cho tăng ca buổi tối
                        'payslip_id': payslip.id,
                    })

                # Tạo overtime plan cho tăng ca đêm (sau 21h)
                if attendance.overtime_night > 0:
                    self.env['hr.overtime.plan'].create({
                        'name': f'Tăng ca đêm (sau 21h) ngày {attendance_date}',
                        'date_from': check_in_local.date(),
                        'date_to': check_out_local.date(),
                        'overtime_hours': attendance.overtime_night,
                        'payment_percentage': 200.0,  # 200% lương cho tăng ca đêm
                        'payslip_id': payslip.id,
                    })

                # Tạo overtime plan cho tăng ca ngày nghỉ
                if attendance.overtime_holiday > 0:
                    self.env['hr.overtime.plan'].create({
                        'name': f'Tăng ca ngày nghỉ {attendance_date}',
                        'date_from': check_in_local.date(),
                        'date_to': check_out_local.date(),
                        'overtime_hours': attendance.overtime_holiday,
                        'payment_percentage': self._get_overtime_rate(attendance_date),
                        'payslip_id': payslip.id,
                    })

            return True

