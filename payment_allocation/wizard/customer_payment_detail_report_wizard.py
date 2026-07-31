# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class CustomerPaymentDetailReportWizard(models.TransientModel):
    _name = 'customer.payment.detail.report.wizard'
    _description = 'Báo cáo chi tiết thanh toán theo khách hàng'

    date_from = fields.Date(
        string='Từ ngày', required=True,
        default=lambda self: fields.Date.context_today(self).replace(day=1))
    date_to = fields.Date(
        string='Đến ngày', required=True,
        default=lambda self: fields.Date.context_today(self))
    partner_ids = fields.Many2many(
        'res.partner', string='Khách hàng (bỏ trống = tất cả)')
    line_ids = fields.One2many(
        'customer.payment.detail.report.line', 'wizard_id', string='Kết quả')
    currency_id = fields.Many2one(
        'res.currency', default=lambda self: self.env.company.currency_id, readonly=True)

    def action_generate_report(self):
        self.ensure_one()
        self.line_ids.unlink()

        domain = [
            ('payment_type', '=', 'inbound'),
            ('state', '=', 'posted'),
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to),
        ]
        if self.partner_ids:
            domain.append(('partner_id', 'in', self.partner_ids.ids))

        payments = self.env['account.payment'].search(domain, order='date asc, id asc')
        invoice_move_types = ('out_invoice', 'out_refund', 'in_invoice', 'in_refund')

        lines_vals = []
        for payment in payments:
            outstanding_lines = payment.move_id.line_ids.filtered(
                lambda l: l.account_id == payment.destination_account_id
            )
            seen = self.env['account.partial.reconcile']
            for out_line in outstanding_lines:
                reconciles = out_line.matched_debit_ids | out_line.matched_credit_ids
                for pr in reconciles:
                    if pr in seen:
                        continue
                    seen |= pr
                    other_line = (pr.debit_move_id if pr.credit_move_id.id == out_line.id
                                  else pr.credit_move_id)
                    invoice = other_line.move_id
                    is_invoice = invoice and invoice.move_type in invoice_move_types
                    lines_vals.append((0, 0, {
                        'payment_id': payment.id,
                        'invoice_id': invoice.id if is_invoice else False,
                        'allocated_amount': pr.amount,
                        'payment_amount': payment.amount,
                        'is_unallocated': False,
                    }))

            # Nếu payment này đã có ít nhất 1 dòng ĐÃ phân bổ (seen != rỗng)
            # thì dòng "chưa phân bổ" hiện 0 ở cột Tổng tiền thanh toán (để
            # tránh cộng dồn trùng). Nếu payment CHƯA phân bổ đồng nào thì
            # dòng chưa phân bổ là dòng DUY NHẤT — phải hiện đúng số tiền gốc.
            has_allocated_rows = bool(seen)

            # Phần còn lại của payment CHƯA được đối soát vào đâu cả.
            if payment.unallocated_amount:
                lines_vals.append((0, 0, {
                    'payment_id': payment.id,
                    'invoice_id': False,
                    'allocated_amount': payment.unallocated_amount,
                    'payment_amount': 0.0 if has_allocated_rows else payment.amount,
                    'is_unallocated': True,
                }))

            # Payment chưa đối soát gì cả (không có reconcile nào, không có
            # phần unallocated tính được) — vẫn hiện 1 dòng để không mất
            # dấu khoản thanh toán này trong báo cáo. Ở nhánh này chắc chắn
            # has_allocated_rows = False nên luôn hiện đúng số tiền gốc.
            if not outstanding_lines and not payment.unallocated_amount:
                lines_vals.append((0, 0, {
                    'payment_id': payment.id,
                    'invoice_id': False,
                    'allocated_amount': payment.amount,
                    'payment_amount': payment.amount,
                    'is_unallocated': True,
                }))

        self.line_ids = lines_vals

        return {
            'type': 'ir.actions.act_window',
            'name': _('Báo cáo chi tiết thanh toán'),
            'res_model': 'customer.payment.detail.report.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }


class CustomerPaymentDetailReportLine(models.TransientModel):
    _name = 'customer.payment.detail.report.line'
    _description = 'Dòng báo cáo chi tiết thanh toán'
    _order = 'payment_date asc, payment_id asc'

    wizard_id = fields.Many2one(
        'customer.payment.detail.report.wizard', required=True, ondelete='cascade')
    payment_id = fields.Many2one(
        'account.payment', string='Thanh toán', readonly=True, required=True,
        ondelete='cascade')
    payment_date = fields.Date(
        related='payment_id.date', string='Ngày nhận tiền', readonly=True, store=True)
    partner_id = fields.Many2one(
        related='payment_id.partner_id', string='Khách hàng', readonly=True, store=True)
    payment_amount = fields.Monetary(
        string='Tổng tiền thanh toán', readonly=True,
        help='Hiện đúng số tiền gốc trên dòng ĐÃ phân bổ, hoặc trên dòng '
             '"Chưa phân bổ" nếu payment đó chưa phân bổ đồng nào. Nếu '
             'payment đã có dòng phân bổ khác thì dòng "Chưa phân bổ" còn '
             'lại sẽ hiện 0 ở cột này để tránh cộng dồn (sum) trùng lặp.')
    payment_memo = fields.Char(
        related='payment_id.ref', string='Diễn giải/Nội dung TT', readonly=True)
    invoice_id = fields.Many2one(
        'account.move', string='Hoá đơn được trả', readonly=True)
    invoice_date = fields.Date(
        related='invoice_id.invoice_date', string='Ngày hoá đơn', readonly=True)
    allocated_amount = fields.Monetary(
        string='Số tiền phân bổ', readonly=True)
    is_unallocated = fields.Boolean(
        string='Chưa phân bổ', readonly=True)
    currency_id = fields.Many2one(
        related='wizard_id.currency_id', string='Tiền tệ')
