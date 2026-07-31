# -*- coding: utf-8 -*-
from odoo import api, fields, models


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    unallocated_amount = fields.Monetary(
        string='Chưa phân bổ',
        compute='_compute_unallocated_amount',
        currency_field='currency_id',
        help='Số tiền của khoản thanh toán này chưa được đối soát (phân bổ) '
             'với bất kỳ hoá đơn/bút toán nào, tính đến thời điểm hiện tại.')

    @api.depends('state', 'amount', 'move_id.line_ids.reconciled',
                 'move_id.line_ids.amount_residual')
    def _compute_unallocated_amount(self):
        for payment in self:
            if payment.state != 'posted' or not payment.destination_account_id:
                payment.unallocated_amount = 0.0
                continue
            outstanding_lines = payment.move_id.line_ids.filtered(
                lambda l: l.account_id == payment.destination_account_id
                and not l.reconciled
            )
            payment.unallocated_amount = sum(
                abs(l.amount_residual) for l in outstanding_lines)
