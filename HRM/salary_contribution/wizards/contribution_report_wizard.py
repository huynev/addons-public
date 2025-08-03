from odoo import models, fields, api


class SalaryContributionReportWizard(models.TransientModel):
    _name = 'salary.contribution.report.wizard'
    _description = 'Salary Contribution Report Wizard'

    date_from = fields.Date(string='Từ ngày', required=True)
    date_to = fields.Date(string='Đến ngày', required=True)
    contribution_type = fields.Selection([
        ('labor_union', 'Công đoàn'),
        ('health_insurance', 'Bảo hiểm y tế'),
        ('social_insurance', 'Bảo hiểm xã hội'),
    ], string='Loại đóng góp')

    def generate_report(self):
        """
        Tạo báo cáo đóng góp
        """
        self.ensure_one()

        domain = [
            ('state', '=', 'confirmed'),
            ('start_date', '>=', self.date_from),
            ('start_date', '<=', self.date_to)
        ]

        if self.contribution_type:
            domain.append(('contribution_type', '=', self.contribution_type))

        contributions = self.env['salary.contribution'].search(domain)

        # In báo cáo hoặc xuất file
        return self.env.ref('salary_contribution.action_salary_contribution_report').report_action(contributions)
