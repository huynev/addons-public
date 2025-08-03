from odoo import api, models
from collections import defaultdict


class PayrollReportPDF(models.AbstractModel):
    _name = 'report.hr_payroll_report.report_payroll'
    _description = 'Payroll Report'

    def _get_report_values(self, docids, data=None):
        if data and 'report_id' in data:
            report = self.env['hr.payroll.report.minhduc'].browse(data['report_id'])
        else:
            report = self.env['hr.payroll.report.minhduc'].browse(docids)[0]

        payslips = report.payslip_ids

        # Organize data by employee
        payslips_by_employee = defaultdict(list)
        for slip in payslips:
            payslips_by_employee[slip.employee_id].append(slip)

        # Calculate totals - sửa phần này
        totals = {
            'gross': 0,
            'net': 0,
            'count': len(payslips),
        }

        # Tính tổng gross và net
        for slip in payslips:
            # Kiểm tra có line GROSS không
            gross_lines = slip.line_ids.filtered(lambda l: l.code == 'GROSS')
            if gross_lines:
                totals['gross'] += sum(gross_lines.mapped('total'))

            # Kiểm tra có line NET không
            net_lines = slip.line_ids.filtered(lambda l: l.code == 'NET')
            if net_lines:
                totals['net'] += sum(net_lines.mapped('total'))

        # Employee summary data - sửa phần này
        employee_data = []
        for employee, slips in payslips_by_employee.items():
            employee_gross = 0
            employee_net = 0

            for slip in slips:
                # Tính gross
                gross_lines = slip.line_ids.filtered(lambda l: l.code == 'GROSS')
                if gross_lines:
                    employee_gross += sum(gross_lines.mapped('total'))

                # Tính net
                net_lines = slip.line_ids.filtered(lambda l: l.code == 'NET')
                if net_lines:
                    employee_net += sum(net_lines.mapped('total'))

            employee_data.append({
                'employee': employee,
                'slips': slips,
                'total_gross': employee_gross,
                'total_net': employee_net,
                'departments': employee.department_id.name if employee.department_id else '',
            })

        # Get all used salary rule categories for detailed report
        all_categories = self.env['hr.salary.rule.category'].search([])
        used_categories = self.env['hr.salary.rule.category']
        for slip in payslips:
            used_categories |= slip.line_ids.mapped('category_id')

        return {
            'doc_ids': docids,
            'doc_model': 'hr.payroll.report.minhduc',
            'docs': report,
            'payslips': payslips,
            'employee_data': employee_data,
            'totals': totals,
            'company': self.env.company,
            'categories': used_categories,
            'is_detailed': report.report_type == 'detailed',
        }