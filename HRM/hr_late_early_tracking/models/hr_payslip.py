from odoo import models, fields, api
from datetime import datetime, timedelta, time
from pytz import UTC
import pytz


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    # Thêm các trường liên quan đến đi trễ/về sớm
    late_early_tracking_ids = fields.One2many('hr.late.early.tracking', 'payslip_id',
                                              string='Late/Early Tracking Records')
    total_late_minutes = fields.Integer(string='Total Late Minutes',
                                        compute='_compute_late_early_summary', store=True)
    total_early_minutes = fields.Integer(string='Total Early Minutes',
                                         compute='_compute_late_early_summary', store=True)
    total_penalty_minutes = fields.Integer(string='Total Penalty Minutes',
                                           compute='_compute_late_early_summary', store=True)
    total_penalty_amount = fields.Float(string='Total Penalty Amount',
                                        compute='_compute_late_early_summary', store=True)

    @api.depends('late_early_tracking_ids', 'late_early_tracking_ids.late_minutes',
                 'late_early_tracking_ids.early_minutes', 'late_early_tracking_ids.penalty_amount')
    def _compute_late_early_summary(self):
        for payslip in self:
            payslip.total_late_minutes = sum(payslip.late_early_tracking_ids.mapped('late_minutes'))
            payslip.total_early_minutes = sum(payslip.late_early_tracking_ids.mapped('early_minutes'))
            payslip.total_penalty_minutes = sum(payslip.late_early_tracking_ids.mapped('total_penalty_minutes'))
            payslip.total_penalty_amount = sum(payslip.late_early_tracking_ids.mapped('penalty_amount'))

    # Hook vào phương thức tạo mới
    @api.model
    def create(self, vals):
        payslip = super(HrPayslip, self).create(vals)
        # Tự động tính toán dữ liệu đi trễ/về sớm khi tạo phiếu lương
        payslip.action_get_late_early_data()
        return payslip

    # Hook vào phương thức tính phiếu lương
    def compute_sheet(self):
        # Trước tiên tính toán dữ liệu đi trễ/về sớm
        self.action_get_late_early_data()
        # Sau đó tiếp tục với logic tính phiếu lương gốc
        return super(HrPayslip, self).compute_sheet()

    def action_get_late_early_data(self):
        """Lấy dữ liệu đi trễ/về sớm từ hr.attendance đã được tính sẵn"""
        for payslip in self:
            # Xóa dữ liệu đi trễ/về sớm cũ
            payslip.late_early_tracking_ids.unlink()

            # Kiểm tra xem có hợp đồng và nhân viên không
            if not payslip.employee_id or not payslip.contract_id:
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
                ('check_in', '<=', date_to_utc),
                ('check_out', '!=', False),  # Chỉ lấy những bản ghi đã check-out
                '|',  # OR condition
                ('late_minutes', '>', 0),  # Có đi trễ
                ('early_minutes', '>', 0)  # Hoặc có về sớm
            ])

            # Tạo bản ghi tracking cho từng attendance có đi trễ/về sớm
            for attendance in attendances:
                # Lấy ngày chấm công (chuyển từ UTC về múi giờ local để lấy ngày)
                check_in_local = attendance.check_in
                if attendance.check_in.tzinfo:
                    # Nếu có timezone info, chuyển về múi giờ Việt Nam
                    check_in_local = attendance.check_in.astimezone(vn_tz)

                attendance_date = check_in_local.date()

                # Kiểm tra xem ngày có nằm trong khoảng phiếu lương không
                if payslip.date_from <= attendance_date <= payslip.date_to:
                    self.env['hr.late.early.tracking'].create({
                        'employee_id': payslip.employee_id.id,
                        'date': attendance_date,
                        'scheduled_check_in': attendance.scheduled_check_in,
                        'scheduled_check_out': attendance.scheduled_check_out,
                        'actual_check_in': attendance.check_in,
                        'actual_check_out': attendance.check_out,
                        'late_minutes': attendance.late_minutes,
                        'early_minutes': attendance.early_minutes,
                        'payslip_id': payslip.id,
                        'state': 'draft',
                    })

            return True