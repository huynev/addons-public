# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class CustomerPaymentReportWizard(models.TransientModel):
    _name = 'customer.payment.report.wizard'
    _description = 'Báo cáo thanh toán theo khách hàng'

    date_from = fields.Date(
        string='Từ ngày', required=True,
        default=lambda self: fields.Date.context_today(self).replace(day=1))
    date_to = fields.Date(
        string='Đến ngày', required=True,
        default=lambda self: fields.Date.context_today(self))
    partner_ids = fields.Many2many(
        'res.partner', string='Khách hàng (bỏ trống = tất cả)')
    line_ids = fields.One2many(
        'customer.payment.report.line', 'wizard_id', string='Kết quả')
    currency_id = fields.Many2one(
        'res.currency', default=lambda self: self.env.company.currency_id, readonly=True)

    def action_generate_report(self):
        self.ensure_one()
        self.line_ids.unlink()

        partners = self.partner_ids or self._get_relevant_partners()

        Payment = self.env['account.payment']
        MoveLine = self.env['account.move.line']
        lines_vals = []

        for partner in partners:
            paid_payments = Payment.search([
                ('partner_id', '=', partner.id),
                ('payment_type', '=', 'inbound'),
                ('state', '=', 'posted'),
                ('date', '>=', self.date_from),
                ('date', '<=', self.date_to),
            ])
            paid_amount = sum(paid_payments.mapped('amount'))

            residual_lines = MoveLine.search([
                ('partner_id', '=', partner.id),
                ('move_id.move_type', 'in', ('out_invoice', 'out_refund')),
                ('move_id.state', '=', 'posted'),
                ('account_id.account_type', '=', 'asset_receivable'),
                ('reconciled', '=', False),
            ])
            remaining_amount = sum(residual_lines.mapped('amount_residual'))

            # Tiền khách đã chuyển (payment đã posted) nhưng vẫn CHƯA được
            # đối soát/phân bổ vào bất kỳ hoá đơn nào — tức công ty đang
            # "giữ hộ" khoản này (ví dụ khách trả dư, hoặc trả trước khi
            # có hoá đơn). Tính theo hiện tại, không giới hạn theo khoảng
            # ngày lọc, vì đây là số dư tồn đọng thực tế tại thời điểm chạy
            # báo cáo.
            all_posted_payments = Payment.search([
                ('partner_id', '=', partner.id),
                ('payment_type', '=', 'inbound'),
                ('state', '=', 'posted'),
            ])
            held_amount = sum(all_posted_payments.mapped('unallocated_amount'))

            lines_vals.append((0, 0, {
                'partner_id': partner.id,
                'paid_amount': paid_amount,
                'remaining_amount': remaining_amount,
                'held_amount': held_amount,
            }))

        self.line_ids = lines_vals

        return {
            'type': 'ir.actions.act_window',
            'name': _('Báo cáo thanh toán theo khách hàng'),
            'res_model': 'customer.payment.report.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def _get_relevant_partners(self):
        payments = self.env['account.payment'].search([
            ('payment_type', '=', 'inbound'),
            ('state', '=', 'posted'),
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to),
        ])
        invoices = self.env['account.move'].search([
            ('move_type', 'in', ('out_invoice', 'out_refund')),
            ('state', '=', 'posted'),
        ])
        return payments.mapped('partner_id') | invoices.mapped('partner_id')


class CustomerPaymentReportLine(models.TransientModel):
    _name = 'customer.payment.report.line'
    _description = 'Dòng báo cáo thanh toán theo khách hàng'

    wizard_id = fields.Many2one(
        'customer.payment.report.wizard', required=True, ondelete='cascade')
    partner_id = fields.Many2one('res.partner', string='Khách hàng', readonly=True)
    currency_id = fields.Many2one(
        related='wizard_id.currency_id', string='Tiền tệ')
    paid_amount = fields.Monetary(
        string='Đã thanh toán (trong khoảng thời gian)', readonly=True)
    remaining_amount = fields.Monetary(
        string='Còn phải thu (hiện tại)', readonly=True)
    held_amount = fields.Monetary(
        string='Chưa phân bổ / Công ty đang giữ (hiện tại)', readonly=True,
        help='Tiền khách đã chuyển (payment đã Posted) nhưng chưa được '
             'đối soát/phân bổ vào hoá đơn nào — ví dụ khách trả dư hoặc '
             'trả trước khi có hoá đơn.')
