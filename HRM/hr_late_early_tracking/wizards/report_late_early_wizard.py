from odoo import models, fields, api
from datetime import datetime, timedelta


class HrLateEarlyReportWizard(models.TransientModel):
    _name = 'hr.late.early.report.wizard'
    _description = 'Late/Early Report Wizard'

    date_from = fields.Date(string='Start Date', required=True, default=lambda self: self._default_date_from())
    date_to = fields.Date(string='End Date', required=True, default=lambda self: self._default_date_to())
    employee_ids = fields.Many2many('hr.employee', string='Employees')
    department_id = fields.Many2one('hr.department', string='Department')
    include_draft = fields.Boolean(string='Include Draft Records', default=True)
    include_approved = fields.Boolean(string='Include Approved Records', default=True)
    include_confirmed = fields.Boolean(string='Include Confirmed Records', default=True)
    include_exception = fields.Boolean(string='Include Exception Records', default=False)
    group_by = fields.Selection([
        ('employee', 'Employee'),
        ('department', 'Department'),
        ('date', 'Date'),
        ('week', 'Week'),
        ('month', 'Month'),
    ], string='Group By', default='employee')

    def _default_date_from(self):
        """Mặc định là đầu tháng hiện tại"""
        today = datetime.today()
        return today.replace(day=1)

    def _default_date_to(self):
        """Mặc định là ngày hiện tại"""
        return datetime.today()

    def _build_domain(self):
        """Xây dựng domain cho báo cáo"""
        domain = [
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to),
        ]

        # Lọc theo trạng thái
        states = []
        if self.include_draft:
            states.append('draft')
        if self.include_confirmed:
            states.append('confirmed')
        if self.include_approved:
            states.append('approved')
        if self.include_exception:
            states.append('exception')

        if states:
            domain.append(('state', 'in', states))

        # Lọc theo nhân viên
        if self.employee_ids:
            domain.append(('employee_id', 'in', self.employee_ids.ids))

        # Lọc theo phòng ban
        if self.department_id:
            employees = self.env['hr.employee'].search([
                ('department_id', '=', self.department_id.id)
            ])
            domain.append(('employee_id', 'in', employees.ids))

        return domain

    def action_generate_report(self):
        """Tạo báo cáo đi trễ/về sớm"""
        domain = self._build_domain()
        records = self.env['hr.late.early.tracking'].search(domain)

        # Nếu không có bản ghi nào, hiển thị thông báo
        if not records:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Thông báo',
                    'message': 'Không tìm thấy dữ liệu đi trễ/về sớm nào trong khoảng thời gian đã chọn.',
                    'type': 'warning',
                    'sticky': False,
                }
            }

        # Nhóm dữ liệu nếu cần
        if self.group_by == 'employee':
            # Nhóm theo nhân viên
            grouped_data = {}
            for record in records:
                employee_id = record.employee_id.id
                if employee_id not in grouped_data:
                    grouped_data[employee_id] = {
                        'employee': record.employee_id.name,
                        'department': record.employee_id.department_id.name if record.employee_id.department_id else '',
                        'total_late_minutes': 0,
                        'total_early_minutes': 0,
                        'total_penalty_minutes': 0,
                        'total_penalty_amount': 0,
                        'records': [],
                    }

                grouped_data[employee_id]['total_late_minutes'] += record.late_minutes
                grouped_data[employee_id]['total_early_minutes'] += record.early_minutes
                grouped_data[employee_id]['total_penalty_minutes'] += record.total_penalty_minutes
                grouped_data[employee_id]['total_penalty_amount'] += record.penalty_amount
                grouped_data[employee_id]['records'].append(record.id)

            # Lưu dữ liệu nhóm vào context
            context = {
                'grouped_data': grouped_data,
                'group_by': self.group_by,
                'date_from': self.date_from,
                'date_to': self.date_to,
            }

            # Trả về action hiển thị báo cáo
            return {
                'name': 'Báo cáo đi trễ/về sớm theo nhân viên',
                'type': 'ir.actions.report',
                'report_name': 'hr_late_early_tracking.report_late_early_tracking',
                'report_type': 'qweb-pdf',
                'data': context,
                'context': context,
                'model': 'hr.late.early.tracking',
                'ids': records.ids,
            }
        else:
            # Trả về báo cáo không phân nhóm
            return {
                'name': 'Báo cáo đi trễ/về sớm',
                'type': 'ir.actions.report',
                'report_name': 'hr_late_early_tracking.report_late_early_tracking',
                'report_type': 'qweb-pdf',
                'data': {},
                'model': 'hr.late.early.tracking',
                'ids': records.ids,
            }