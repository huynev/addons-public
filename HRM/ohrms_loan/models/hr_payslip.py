# -*- coding: utf-8 -*-
#############################################################################
#    A part of Open HRMS Project <https://www.openhrms.com>
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2023-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
#    Author: Cybrosys Techno Solutions(<https://www.cybrosys.com>)
#
#    You can modify it under the terms of the GNU LESSER
#    GENERAL PUBLIC LICENSE (LGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU LESSER GENERAL PUBLIC LICENSE (LGPL v3) for more details.
#
#    You should have received a copy of the GNU LESSER GENERAL PUBLIC LICENSE
#    (LGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
#############################################################################
from odoo import models


class HrPayslip(models.Model):
    """ Extends the 'hr.payslip' model to include
    additional functionality related to employee loans."""
    _inherit = 'hr.payslip'

    def get_inputs(self, contract_ids, date_from, date_to):
        """Compute additional inputs for the employee payslip,
        considering active loans."""
        res = super(HrPayslip, self).get_inputs(contract_ids, date_from, date_to)

        employee_id = self.env['hr.contract'].browse(
            contract_ids[0].id).employee_id if contract_ids else self.employee_id

        # Tìm tất cả loan_lines thỏa mãn điều kiện
        loan_lines = self.env['hr.loan.line'].search([
            ('loan_id.employee_id', '=', employee_id.id),
            ('loan_id.state', '=', 'approve'),
            ('date', '>=', date_from),
            ('date', '<=', date_to),
            ('paid', '=', False)
        ])

        if loan_lines:
            # Tính tổng amount
            total_loan_amount = sum(loan_lines.mapped('amount'))

            # Tìm input có code 'LO' để cập nhật
            loan_input_found = False
            for result in res:
                if result.get('code') == 'LO':
                    result['amount'] = total_loan_amount
                    result['loan_line_ids'] = [(6, 0, loan_lines.ids)]
                    result['date_from'] = date_from
                    result['date_to'] = date_to
                    loan_input_found = True
                    break

            # Nếu không tìm thấy input có code 'LO', tạo mới
            if not loan_input_found:
                loan_input = {
                    'name': "Total Loan Installments",
                    'code': 'LO',
                    'amount': total_loan_amount,
                    'loan_line_ids': [(6, 0, loan_lines.ids)],
                    'date_from': date_from,
                    'date_to': date_to,
                }
                res.append(loan_input)

        return res

    def action_payslip_done(self):
        """ Compute the loan amount and remaining amount while confirming
            the payslip"""
        for line in self.input_line_ids:
            # Xử lý trường hợp có loan_line_ids (nhiều loan lines gộp)
            if line.loan_line_ids:
                for loan_line in line.loan_line_ids:
                    loan_line.paid = True
                    loan_line.payslip_id = self.id
                    loan_line.loan_id._compute_total_amount()
            # Xử lý trường hợp có loan_line_id (single loan line)
            elif line.loan_line_id:
                line.loan_line_id.paid = True
                line.loan_line_id.payslip_id = self.id
                line.loan_line_id.loan_id._compute_total_amount()

        return super(HrPayslip, self).action_payslip_done()