from odoo import models, fields, api
from datetime import datetime, timedelta, time
from pytz import UTC
import pytz


class HrLateEarlyTracking(models.Model):
    _name = 'hr.late.early.tracking'
    _description = 'Late/Early Tracking'
    _order = 'date desc, employee_id'

    name = fields.Char(string='Name', compute='_compute_name', store=True)
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True)
    date = fields.Date(string='Date', required=True)

    # Thời gian check-in/check-out theo lịch làm việc
    scheduled_check_in = fields.Datetime(string='Scheduled Check In')
    scheduled_check_out = fields.Datetime(string='Scheduled Check Out')

    # Thời gian check-in/check-out thực tế
    actual_check_in = fields.Datetime(string='Actual Check In')
    actual_check_out = fields.Datetime(string='Actual Check Out')

    # Thời gian đi trễ/về sớm tính bằng phút
    late_minutes = fields.Integer(string='Late Minutes', default=0)
    early_minutes = fields.Integer(string='Early Minutes', default=0)
    total_penalty_minutes = fields.Integer(string='Total Penalty Minutes',
                                           compute='_compute_total_penalty_minutes',
                                           store=True)

    # Tiền phạt
    penalty_amount = fields.Float(string='Penalty Amount', compute='_compute_penalty_amount', store=True)

    # Liên kết với phiếu lương
    payslip_id = fields.Many2one('hr.payslip', string='Payslip')

    # Trạng thái (có thể dùng để xác nhận hoặc xử lý ngoại lệ)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('approved', 'Approved'),
        ('exception', 'Exception'),
    ], string='Status', default='draft')

    # Ghi chú
    note = fields.Text(string='Note')

    @api.depends('employee_id', 'date')
    def _compute_name(self):
        for record in self:
            if record.employee_id and record.date:
                record.name = f"{record.employee_id.name} - {record.date}"
            else:
                record.name = "New Tracking"

    @api.depends('late_minutes', 'early_minutes')
    def _compute_total_penalty_minutes(self):
        for record in self:
            record.total_penalty_minutes = record.late_minutes + record.early_minutes

    @api.depends('total_penalty_minutes', 'payslip_id', 'payslip_id.contract_id.wage')
    def _compute_penalty_amount(self):
        for record in self:
            wage = 0
            if record.payslip_id and record.payslip_id.contract_id:
                # Lương cơ bản / 30 ngày / 8 giờ / 60 phút * số phút
                wage = record.payslip_id.contract_id.wage / (30 * 8 * 60)

            record.penalty_amount = wage * record.total_penalty_minutes

    # Action xác nhận dữ liệu
    def action_confirm(self):
        for record in self:
            record.state = 'confirmed'

    # Action phê duyệt dữ liệu
    def action_approve(self):
        for record in self:
            record.state = 'approved'

    # Action đánh dấu là ngoại lệ
    def action_mark_exception(self):
        for record in self:
            record.state = 'exception'

    # Action đặt về nháp
    def action_reset_to_draft(self):
        for record in self:
            record.state = 'draft'