from odoo import api, fields, models, _
from odoo.exceptions import UserError
from datetime import datetime
import base64
import io
import calendar
from dateutil.relativedelta import relativedelta


class HrPayrollReport(models.Model):
    _name = 'hr.payroll.report.minhduc'
    _description = 'HR Payroll Report for Minh Duc'
    _order = 'date_from desc, date_to desc'

    name = fields.Char(string='Name', required=True)
    date_from = fields.Date(string='Date From', required=True)
    date_to = fields.Date(string='Date To', required=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    report_type = fields.Selection([
        ('summary', 'Summary'),
        ('detailed', 'Detailed'),
    ], string='Report Type', default='summary', required=True)
    employee_ids = fields.Many2many('hr.employee', string='Employees')
    department_ids = fields.Many2many('hr.department', string='Departments')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('generated', 'Generated'),
    ], string='Status', default='draft', required=True)
    payslip_ids = fields.Many2many('hr.payslip', string='Payslips', compute='_compute_payslips')
    pdf_report = fields.Binary('PDF Report', readonly=True)
    pdf_filename = fields.Char('PDF Filename')

    @api.model
    def default_get(self, fields_list):
        res = super(HrPayrollReport, self).default_get(fields_list)
        today = fields.Date.today()
        first_day = today.replace(day=1)
        # Ngày cuối tháng hiện tại
        last_day = self._get_last_day_of_month(first_day)

        res.update({
            'date_from': first_day,
            'date_to': last_day
        })
        return res

    @api.onchange('date_from')
    def _onchange_date_from(self):
        """Cập nhật date_to là ngày cuối cùng của tháng khi date_from thay đổi"""
        if self.date_from:
            self.date_to = self._get_last_day_of_month(self.date_from)

    def _get_last_day_of_month(self, date):
        """Lấy ngày cuối cùng của tháng"""
        # Cách 1: Sử dụng calendar
        last_day = calendar.monthrange(date.year, date.month)[1]
        return date.replace(day=last_day)

        # Cách 2 (thay thế): Sử dụng dateutil.relativedelta
        # next_month = date + relativedelta(months=1)
        # return (next_month.replace(day=1) - relativedelta(days=1))

    @api.depends('date_from', 'date_to', 'employee_ids', 'department_ids')
    def _compute_payslips(self):
        for report in self:
            domain = [
                ('date_from', '>=', report.date_from),
                ('date_to', '<=', report.date_to),
                ('state', 'in', ['done', 'paid']),
            ]

            if report.employee_ids:
                domain.append(('employee_id', 'in', report.employee_ids.ids))
            elif report.department_ids:
                employees = self.env['hr.employee'].search([('department_id', 'in', report.department_ids.ids)])
                domain.append(('employee_id', 'in', employees.ids))

            report.payslip_ids = self.env['hr.payslip'].search(domain)

    def action_generate_report(self):
        self.ensure_one()
        if not self.payslip_ids:
            raise UserError(_("No payslips found for the selected criteria."))

        # Sử dụng API mới trong Odoo 17
        report = self.env.ref('hr_payroll_report.action_report_hr_payroll')
        pdf_content, _ = self.env['ir.actions.report']._render(
            report.report_name,
            [self.id],
            data={'docids': self.id}
        )

        # Save the PDF
        self.write({
            'pdf_report': base64.b64encode(pdf_content),
            'pdf_filename': f'Payroll_Report_{self.date_from}_{self.date_to}.pdf',
            'state': 'generated'
        })

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'hr.payroll.report.minhduc',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'current',
            'context': {'form_view_initial_mode': 'edit'},
        }

    def action_reset_to_draft(self):
        self.write({'state': 'draft'})

    def action_download_report(self):
        self.ensure_one()
        if not self.pdf_report:
            raise UserError(_("Report hasn't been generated yet."))

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/hr.payroll.report.minhduc/{self.id}/pdf_report/{self.pdf_filename}?download=true',
            'target': 'self',
        }