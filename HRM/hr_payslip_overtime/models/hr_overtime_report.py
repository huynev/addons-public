# File: models/hr_overtime_report.py

from odoo import models, fields, tools


class HrPayrollReport(models.Model):
    _name = 'hr.payroll.report'
    _description = 'Payroll Analysis Report'
    _auto = False
    _order = 'date_from desc'

    name = fields.Char(string='Name', readonly=True)
    date_from = fields.Date(string='Date From', readonly=True)
    date_to = fields.Date(string='Date To', readonly=True)
    employee_id = fields.Many2one('hr.employee', string='Employee', readonly=True)
    department_id = fields.Many2one('hr.department', string='Department', readonly=True)
    job_id = fields.Many2one('hr.job', string='Job Position', readonly=True)
    company_id = fields.Many2one('res.company', string='Company', readonly=True)
    contract_id = fields.Many2one('hr.contract', string='Contract', readonly=True)
    struct_id = fields.Many2one('hr.payroll.structure', string='Salary Structure', readonly=True)

    # Tổng lương gộp
    gross_amount = fields.Float(string='Gross Amount', readonly=True)

    # Tổng khấu trừ
    deduction_amount = fields.Float(string='Deductions', readonly=True)

    # Tổng tăng ca
    overtime_amount = fields.Float(string='Overtime', readonly=True)

    # Tổng phụ cấp
    allowance_amount = fields.Float(string='Allowance', readonly=True)

    # Lương thực nhận
    net_amount = fields.Float(string='Net Amount', readonly=True)

    # Tổng số giờ làm việc
    worked_days = fields.Float(string='Worked Days', readonly=True)
    worked_hours = fields.Float(string='Worked Hours', readonly=True)

    # Trạng thái phiếu lương
    state = fields.Selection([
        ('draft', 'Draft'),
        ('verify', 'Waiting'),
        ('done', 'Done'),
        ('cancel', 'Rejected'),
    ], string='Status', readonly=True)

    # Thông tin bổ sung
    number = fields.Char(string='Reference', readonly=True)
    payslip_run_id = fields.Many2one('hr.payslip.run', string='Payslip Batch', readonly=True)
    year = fields.Integer(string='Year', readonly=True)
    month = fields.Integer(string='Month', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        query = """
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    p.id,
                    p.name,
                    p.date_from,
                    p.date_to,
                    p.employee_id,
                    e.department_id,
                    e.job_id,
                    p.company_id,
                    p.contract_id,
                    p.struct_id,
                    p.state,
                    p.number,
                    p.payslip_run_id,
                    EXTRACT(YEAR FROM p.date_from) AS year,
                    EXTRACT(MONTH FROM p.date_from) AS month,

                    -- Tính tổng lương gộp (tìm trong category 'GROSS')
                    COALESCE((SELECT SUM(pl.total)
                     FROM hr_payslip_line pl
                     WHERE pl.slip_id = p.id
                     AND pl.category_id IN (SELECT id FROM hr_salary_rule_category WHERE code = 'GROSS')), 0) AS gross_amount,

                    -- Tính tổng các khoản khấu trừ (tìm trong category 'DED')
                    COALESCE((SELECT SUM(pl.total)
                     FROM hr_payslip_line pl
                     WHERE pl.slip_id = p.id
                     AND pl.category_id IN (SELECT id FROM hr_salary_rule_category WHERE code = 'DED')), 0) AS deduction_amount,

                    -- Tính tổng tiền tăng ca (dựa trên các line có mã bắt đầu bằng 'OT_')
                    COALESCE((SELECT SUM(pl.total)
                     FROM hr_payslip_line pl
                     WHERE pl.slip_id = p.id
                     AND pl.code LIKE 'OT_%%'), 0) AS overtime_amount,

                    -- Tính tổng phụ cấp (dựa vào category có mã ALW hoặc ALLOW)
                    COALESCE((SELECT SUM(pl.total)
                     FROM hr_payslip_line pl
                     WHERE pl.slip_id = p.id
                     AND pl.category_id IN (SELECT id FROM hr_salary_rule_category WHERE code IN ('ALW', 'ALLOW'))), 0) AS allowance_amount,

                    -- Tính lương thực nhận (tìm trong category 'NET')
                    COALESCE((SELECT SUM(pl.total)
                     FROM hr_payslip_line pl
                     WHERE pl.slip_id = p.id
                     AND pl.category_id IN (SELECT id FROM hr_salary_rule_category WHERE code = 'NET')), 0) AS net_amount,

                    -- Tính tổng số ngày làm việc
                    COALESCE((SELECT SUM(wd.number_of_days)
                     FROM hr_payslip_worked_days wd
                     WHERE wd.payslip_id = p.id), 0) AS worked_days,

                    -- Tính tổng số giờ làm việc
                    COALESCE((SELECT SUM(wd.number_of_hours)
                     FROM hr_payslip_worked_days wd
                     WHERE wd.payslip_id = p.id), 0) AS worked_hours
                FROM
                    hr_payslip p
                LEFT JOIN
                    hr_employee e ON p.employee_id = e.id
                WHERE
                    p.state != 'cancel'
            )
        """
        self.env.cr.execute(query % self._table)