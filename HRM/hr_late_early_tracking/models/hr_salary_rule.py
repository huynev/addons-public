from odoo import models, fields, api


class HrSalaryRule(models.Model):
    _inherit = 'hr.salary.rule'

    # Thêm các mẫu rule code cho phần đi trễ/về sớm

    @api.model
    def _get_late_early_penalty_code(self):
        """Mẫu code tính phạt đi trễ/về sớm"""
        return """# Mẫu code để tính phạt đi trễ/về sớm
# Code này có thể được sử dụng trong quy tắc lương
# Kết quả là giá trị âm (số tiền bị trừ)

# Tính tổng số tiền bị trừ do đi trễ/về sớm
result = 0
if payslip.late_early_tracking_ids:
    result = -sum(payslip.late_early_tracking_ids.mapped('penalty_amount'))
"""

    @api.model
    def _get_late_penalty_code(self):
        """Mẫu code tính phạt đi trễ"""
        return """# Mẫu code để tính phạt đi trễ
# Code này có thể được sử dụng trong quy tắc lương
# Kết quả là giá trị âm (số tiền bị trừ)

# Tính số tiền bị trừ cho riêng đi trễ
result = 0
if payslip.late_early_tracking_ids:
    late_minutes = sum(payslip.late_early_tracking_ids.mapped('late_minutes'))
    hourly_rate = contract.wage / (30 * 8 * 60)  # Lương phút
    result = -late_minutes * hourly_rate
"""

    @api.model
    def _get_early_penalty_code(self):
        """Mẫu code tính phạt về sớm"""
        return """# Mẫu code để tính phạt về sớm
# Code này có thể được sử dụng trong quy tắc lương
# Kết quả là giá trị âm (số tiền bị trừ)

# Tính số tiền bị trừ cho riêng về sớm
result = 0
if payslip.late_early_tracking_ids:
    early_minutes = sum(payslip.late_early_tracking_ids.mapped('early_minutes'))
    hourly_rate = contract.wage / (30 * 8 * 60)  # Lương phút
    result = -early_minutes * hourly_rate
"""

    # Chức năng trợ giúp tạo rule mới
    def action_create_late_early_penalty_rule(self):
        """Action tạo quy tắc lương mới cho phạt đi trễ/về sớm"""
        self.env['hr.salary.rule'].create({
            'name': 'Phạt đi trễ/về sớm',
            'code': 'LATE_EARLY',
            'category_id': self.env.ref('payroll.DED').id,  # Loại khấu trừ
            'sequence': 190,
            'condition_select': 'python',
            'condition_python': """
# Chỉ áp dụng nếu có dữ liệu đi trễ/về sớm
result = bool(payslip.late_early_tracking_ids)
            """,
            'amount_select': 'code',
            'amount_python_compute': self._get_late_early_penalty_code(),
            'appears_on_payslip': True,
            'note': 'Khấu trừ cho việc đi trễ và về sớm dựa trên dữ liệu chấm công.'
        })
        return True