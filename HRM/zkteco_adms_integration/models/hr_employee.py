from odoo import api, fields, models, _


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    attendance_device_id = fields.Char('Device User ID', help='User ID in attendance device')

    # Statistics from attendance device
    total_attendances = fields.Integer('Total Attendances', compute='_compute_attendance_stats')
    this_month_attendances = fields.Integer('This Month', compute='_compute_attendance_stats')

    @api.depends('attendance_device_id')
    def _compute_attendance_stats(self):
        for employee in self:
            if employee.attendance_device_id:
                # Total count
                total = self.env['hr.attendance'].search_count([
                    ('employee_id', '=', employee.id)
                ])

                # This month count
                today = fields.Date.today()
                month_start = today.replace(day=1)
                month_count = self.env['hr.attendance'].search_count([
                    ('employee_id', '=', employee.id),
                    ('attendance_timestamp', '>=', month_start)
                ])

                employee.total_attendances = total
                employee.this_month_attendances = month_count
            else:
                employee.total_attendances = 0
                employee.this_month_attendances = 0
