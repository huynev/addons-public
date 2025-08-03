from odoo import models, fields, api
from datetime import datetime
from dateutil.relativedelta import relativedelta


class HrLateEarlyDashboard(models.TransientModel):
    _name = 'hr.late.early.dashboard'
    _description = 'Dashboard Đi trễ/Về sớm'

    # Định nghĩa các trường hiển thị thông tin tổng quan
    name = fields.Char(string='Tên', default='Dashboard Đi trễ/Về sớm')
    date_from = fields.Date(string='Từ ngày', default=lambda self: self._default_date_from())
    date_to = fields.Date(string='Đến ngày', default=lambda self: self._default_date_to())
    current_month_count = fields.Integer(string=' Số lượng trong tháng hiện tại', compute='_compute_dashboard_data')
    current_month_late_minutes = fields.Integer(string=' Phút đi trễ trong tháng', compute='_compute_dashboard_data')
    current_month_early_minutes = fields.Integer(string=' Phút về sớm trong tháng', compute='_compute_dashboard_data')

    # Trường One2many cho Top nhân viên
    top_late_employees_ids = fields.One2many('hr.late.early.dashboard.employee.stats', 'dashboard_id',
                                             string='Top nhân viên đi trễ', compute='_compute_top_employees')
    top_early_employees_ids = fields.One2many('hr.late.early.dashboard.employee.stats', 'dashboard_id',
                                              string='Top nhân viên về sớm', compute='_compute_top_employees')

    # Thống kê theo phòng ban
    department_stats_ids = fields.One2many('hr.late.early.dashboard.department.stats', 'dashboard_id',
                                           string='Thống kê theo phòng ban', compute='_compute_department_stats')

    def _default_date_from(self):
        """Mặc định là đầu tháng hiện tại"""
        today = datetime.today()
        return today.replace(day=1)

    def _default_date_to(self):
        """Mặc định là ngày hiện tại"""
        return datetime.today()

    @api.depends('date_from', 'date_to')
    def _compute_dashboard_data(self):
        """Tính toán dữ liệu cho dashboard"""
        for record in self:
            first_day = record.date_from or datetime.today().replace(day=1)
            last_day = record.date_to or datetime.today()

            # Tính toán thống kê cho khoảng thời gian
            current_period_records = self.env['hr.late.early.tracking'].search([
                ('date', '>=', first_day),
                ('date', '<=', last_day)
            ])

            record.current_month_count = len(current_period_records)
            record.current_month_late_minutes = sum(current_period_records.mapped('late_minutes'))
            record.current_month_early_minutes = sum(current_period_records.mapped('early_minutes'))

    @api.depends('date_from', 'date_to')
    def _compute_top_employees(self):
        """Tính toán top 5 nhân viên đi trễ/về sớm nhiều nhất"""
        for record in self:
            first_day = record.date_from or datetime.today().replace(day=1)
            last_day = record.date_to or datetime.today()

            # Tính toán top nhân viên đi trễ
            self.env.cr.execute("""
                SELECT employee_id, SUM(late_minutes) as total_late
                FROM hr_late_early_tracking
                WHERE date >= %s AND date <= %s AND employee_id IS NOT NULL
                GROUP BY employee_id
                ORDER BY total_late DESC
                LIMIT 5
            """, (first_day, last_day))
            late_results = self.env.cr.dictfetchall()

            # Tính toán top nhân viên về sớm
            self.env.cr.execute("""
                SELECT employee_id, SUM(early_minutes) as total_early
                FROM hr_late_early_tracking
                WHERE date >= %s AND date <= %s AND employee_id IS NOT NULL
                GROUP BY employee_id
                ORDER BY total_early DESC
                LIMIT 5
            """, (first_day, last_day))
            early_results = self.env.cr.dictfetchall()

            # Tạo dữ liệu thống kê
            top_late_vals = []
            for result in late_results:
                if result['employee_id']:
                    top_late_vals.append((0, 0, {
                        'employee_id': result['employee_id'],
                        'late_minutes': result['total_late'] or 0,
                        'stats_type': 'late'
                    }))

            top_early_vals = []
            for result in early_results:
                if result['employee_id']:
                    top_early_vals.append((0, 0, {
                        'employee_id': result['employee_id'],
                        'early_minutes': result['total_early'] or 0,
                        'stats_type': 'early'
                    }))

            record.top_late_employees_ids = [(5, 0, 0)] + top_late_vals
            record.top_early_employees_ids = [(5, 0, 0)] + top_early_vals

    @api.depends('date_from', 'date_to')
    def _compute_department_stats(self):
        """Tính toán thống kê theo phòng ban"""
        for record in self:
            first_day = record.date_from or datetime.today().replace(day=1)
            last_day = record.date_to or datetime.today()

            # Lấy tất cả phòng ban
            departments = self.env['hr.department'].search([])

            # Kết quả thống kê theo phòng ban
            department_stats = []

            for department in departments:
                # Lấy nhân viên trong phòng ban
                employees = self.env['hr.employee'].search([
                    ('department_id', '=', department.id)
                ])

                # Lấy bản ghi đi trễ/về sớm của phòng ban
                if employees:
                    late_early_records = self.env['hr.late.early.tracking'].search([
                        ('employee_id', 'in', employees.ids),
                        ('date', '>=', first_day),
                        ('date', '<=', last_day)
                    ])

                    if late_early_records:
                        department_stats.append((0, 0, {
                            'department_id': department.id,
                            'employee_count': len(employees),
                            'late_early_count': len(late_early_records),
                            'total_late_minutes': sum(late_early_records.mapped('late_minutes')),
                            'total_early_minutes': sum(late_early_records.mapped('early_minutes')),
                            'total_penalty_amount': sum(late_early_records.mapped('penalty_amount'))
                        }))

            record.department_stats_ids = [(5, 0, 0)] + department_stats

    def action_view_all_records(self):
        """Mở danh sách tất cả bản ghi"""
        # Lấy khoảng thời gian đã chọn
        first_day = self.date_from
        last_day = self.date_to

        try:
            action = self.env.ref('hr_late_early_tracking.action_hr_late_early_tracking').read()[0]
        except ValueError:
            action = {
                'name': 'Tất cả bản ghi đi trễ/về sớm',
                'type': 'ir.actions.act_window',
                'res_model': 'hr.late.early.tracking',
                'view_mode': 'tree,form',
            }

        action.update({
            'domain': [('date', '>=', first_day), ('date', '<=', last_day)],
            'context': {'search_default_group_by_employee': True},
            'target': 'current',
        })

        return action

    def action_generate_full_report(self):
        """Mở wizard tạo báo cáo đầy đủ"""
        context = {
            'default_date_from': self.date_from,
            'default_date_to': self.date_to,
            'default_include_draft': True,
            'default_include_confirmed': True,
            'default_include_approved': True,
        }

        return {
            'name': 'Tạo báo cáo đầy đủ',
            'view_mode': 'form',
            'res_model': 'hr.late.early.report.wizard',
            'type': 'ir.actions.act_window',
            'target': 'new',
            'context': context,
        }

    def action_update_dashboard(self):
        """Cập nhật lại dashboard với khoảng thời gian mới"""
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'hr.late.early.dashboard',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'current',
            'flags': {'mode': 'readonly'},
        }


class HrLateEarlyDashboardEmployeeStats(models.TransientModel):
    _name = 'hr.late.early.dashboard.employee.stats'
    _description = 'Thống kê đi trễ/về sớm theo nhân viên (Dashboard)'

    dashboard_id = fields.Many2one('hr.late.early.dashboard', string='Dashboard', ondelete='cascade')
    employee_id = fields.Many2one('hr.employee', string='Nhân viên', required=True)
    late_minutes = fields.Integer(string='Phút đi trễ')
    early_minutes = fields.Integer(string='Phút về sớm')
    stats_type = fields.Selection([
        ('late', 'Đi trễ'),
        ('early', 'Về sớm')
    ], string='Loại thống kê')


class HrLateEarlyDashboardDepartmentStats(models.TransientModel):
    _name = 'hr.late.early.dashboard.department.stats'
    _description = 'Thống kê đi trễ/về sớm theo phòng ban (Dashboard)'

    dashboard_id = fields.Many2one('hr.late.early.dashboard', string='Dashboard', ondelete='cascade')
    department_id = fields.Many2one('hr.department', string='Phòng ban', required=True)
    employee_count = fields.Integer(string='Số lượng nhân viên')
    late_early_count = fields.Integer(string='Số bản ghi đi trễ/về sớm')
    total_late_minutes = fields.Integer(string='Tổng phút đi trễ')
    total_early_minutes = fields.Integer(string='Tổng phút về sớm')
    total_penalty_amount = fields.Float(string='Tổng tiền phạt')