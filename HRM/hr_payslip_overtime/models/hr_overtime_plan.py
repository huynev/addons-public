from odoo import models, fields, api
from datetime import datetime, timedelta


class HrOvertimePlan(models.Model):
    _name = 'hr.overtime.plan'
    _description = 'Overtime Plan'

    name = fields.Char(string='Name', required=True)
    date_from = fields.Date(string='Start Date', required=True)
    date_to = fields.Date(string='End Date', required=True)
    overtime_hours = fields.Float(string='Overtime Hours', required=True)
    payment_percentage = fields.Float(string='Payment Rate (%)', default=150.0, required=True)
    standard_pay = fields.Float(string='Standard Pay', compute='_compute_pays')
    actual_overtime_pay = fields.Float(string='Actual Overtime Pay', compute='_compute_pays')
    payslip_id = fields.Many2one('hr.payslip', string='Payslip')
    employee_id = fields.Many2one('hr.employee', string='Employee', related='payslip_id.employee_id', store=True)
    overtime_type = fields.Selection([
        ('regular', 'Regular Day'),
        ('weekend', 'Weekend'),
        ('holiday', 'Holiday')
    ], string='Overtime Type', compute='_compute_overtime_type', store=True)

    @api.depends('date_from')
    def _compute_overtime_type(self):
        for record in self:
            day = record.date_from
            if not day:
                record.overtime_type = 'regular'
                continue

            # Kiểm tra ngày lễ
            is_holiday = self.env['resource.calendar.leaves'].search_count([
                ('date_from', '<=', datetime.combine(day, datetime.max.time())),
                ('date_to', '>=', datetime.combine(day, datetime.min.time())),
                ('resource_id', '=', False),  # Ngày lễ chung
            ]) > 0

            if is_holiday:
                record.overtime_type = 'holiday'
            elif day.weekday() >= 5:  # Thứ 7 hoặc Chủ nhật
                record.overtime_type = 'weekend'
            else:
                record.overtime_type = 'regular'

    @api.depends('overtime_hours', 'payment_percentage', 'payslip_id.contract_id.wage')
    def _compute_pays(self):
        for record in self:
            wage = 0
            if record.payslip_id and record.payslip_id.contract_id:
                # Giả sử lương tháng chia cho 30 ngày và 8 giờ/ngày để có mức lương giờ
                wage = record.payslip_id.contract_id.wage / (30 * 8)

            record.standard_pay = wage * record.overtime_hours
            record.actual_overtime_pay = record.standard_pay * (record.payment_percentage / 100)