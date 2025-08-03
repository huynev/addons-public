from odoo import models, fields, api


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    def get_bank_info(self):
        """Get employee bank information from payslip"""
        self.ensure_one()
        bank_account = False
        if self.employee_id.bank_account_id:
            bank_account = self.employee_id.bank_account_id
        return bank_account

    def get_net_amount(self, rule_code='NET'):
        """Get net amount (thực lãnh) from payslip

        Args:
            rule_code: Salary rule code to look for (default: 'NET')

        Returns:
            float: Net amount from payslip
        """
        self.ensure_one()
        # Đầu tiên tìm theo mã được chỉ định
        net_amount = self.get_salary_line_total(rule_code)

        # Nếu không tìm thấy, thử tìm một số mã thông dụng khác
        if not net_amount:
            common_net_codes = ['NET', 'NETLP', 'NETL', 'NETPAY', 'TAKE_HOME', 'LUONG_THUC_LANH']
            # Loại bỏ mã đã tìm khỏi danh sách
            if rule_code in common_net_codes:
                common_net_codes.remove(rule_code)

            for code in common_net_codes:
                net_amount = self.get_salary_line_total(code)
                if net_amount:
                    break

        # Nếu vẫn không tìm thấy, thử tìm line thuộc category NET
        if not net_amount:
            net_lines = self.line_ids.filtered(lambda line: line.category_id.code == 'NET')
            if net_lines:
                net_amount = sum(net_lines.mapped('total'))

        return net_amount