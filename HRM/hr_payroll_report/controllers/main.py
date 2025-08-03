from odoo import http
from odoo.http import request
import base64


class HrPayrollReportController(http.Controller):
    @http.route('/hr_payroll_report/download/<int:report_id>', type='http', auth='user')
    def download_report(self, report_id, **kwargs):
        report = request.env['hr.payroll.report.minhduc'].browse(report_id)
        if not report.exists() or not report.pdf_report:
            return request.not_found()

        pdf_content = base64.b64decode(report.pdf_report)

        return request.make_response(
            pdf_content,
            headers=[
                ('Content-Type', 'application/pdf'),
                ('Content-Disposition', f'attachment; filename={report.pdf_filename}'),
                ('Content-Length', len(pdf_content)),
            ]
        )