# -*- coding: utf-8 -*-
from odoo import fields, models, tools


class PaymentAllocationReport(models.Model):
    """Báo cáo dạng SQL view: mỗi dòng là 1 lần phân bổ (hoặc phần còn
    chưa phân bổ) của 1 khoản thanh toán khách hàng. Model này chỉ để ĐỌC
    (_auto=False), dữ liệu luôn phản ánh đúng thời gian thực — không cần
    wizard hay bước 'Generate' nào, mở menu lên là có filter + group by
    + click để xổ chi tiết như report của Enterprise.
    """
    _name = 'payment.allocation.report'
    _description = 'Báo cáo phân bổ thanh toán (dạng Enterprise)'
    _auto = False
    _order = 'payment_date desc, payment_id desc'

    payment_id = fields.Many2one('account.payment', string='Thanh toán', readonly=True)
    payment_date = fields.Date(string='Ngày nhận tiền', readonly=True)
    partner_id = fields.Many2one('res.partner', string='Khách hàng', readonly=True)
    payment_memo = fields.Char(related='payment_id.ref', string='Diễn giải', readonly=True)
    invoice_id = fields.Many2one('account.move', string='Hoá đơn', readonly=True)
    invoice_date = fields.Date(related='invoice_id.invoice_date', string='Ngày hoá đơn', readonly=True)
    allocated_amount = fields.Monetary(string='Số tiền phân bổ', readonly=True)
    is_unallocated = fields.Boolean(string='Chưa phân bổ', readonly=True)
    currency_id = fields.Many2one('res.currency', string='Tiền tệ', readonly=True)
    company_id = fields.Many2one('res.company', string='Công ty', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(f"""
            CREATE OR REPLACE VIEW {self._table} AS (

                -- 1) Các dòng ĐÃ phân bổ: mỗi account.partial.reconcile
                --    nối 1 khoản thanh toán với 1 hoá đơn là 1 dòng.
                --    Lấy partner_id/currency_id/company_id/date từ chính
                --    account_move_line (out_line) — đây LUÔN LÀ CỘT THẬT
                --    trên bảng đó, tránh phụ thuộc vào việc account.payment
                --    có uỷ quyền field sang account.move hay không.
                SELECT
                    pr.id AS id,
                    pay.id AS payment_id,
                    out_line.date AS payment_date,
                    out_line.partner_id AS partner_id,
                    out_line.currency_id AS currency_id,
                    out_line.company_id AS company_id,
                    inv.id AS invoice_id,
                    pr.amount AS allocated_amount,
                    FALSE AS is_unallocated
                FROM account_partial_reconcile pr
                JOIN account_move_line out_line
                    ON out_line.id = pr.debit_move_id OR out_line.id = pr.credit_move_id
                JOIN account_payment pay
                    ON pay.move_id = out_line.move_id
                   AND out_line.account_id = pay.destination_account_id
                JOIN account_move pay_move
                    ON pay_move.id = pay.move_id
                   AND pay_move.state = 'posted'
                JOIN account_move_line other_line
                    ON other_line.id = (
                        CASE WHEN pr.debit_move_id = out_line.id
                             THEN pr.credit_move_id
                             ELSE pr.debit_move_id
                        END
                    )
                JOIN account_move inv
                    ON inv.id = other_line.move_id
                   AND inv.move_type IN ('out_invoice', 'out_refund', 'in_invoice', 'in_refund')
                WHERE pay.payment_type = 'inbound'

                UNION ALL

                -- 2) Phần CÒN LẠI của mỗi payment chưa được đối soát vào
                --    hoá đơn nào — 1 dòng giả (id âm) đại diện phần tiền
                --    đang bị 'giữ' chưa phân bổ.
                SELECT
                    -pay.id AS id,
                    pay.id AS payment_id,
                    out_line.date AS payment_date,
                    out_line.partner_id AS partner_id,
                    out_line.currency_id AS currency_id,
                    out_line.company_id AS company_id,
                    NULL::integer AS invoice_id,
                    (pay.amount - COALESCE(alloc.total_allocated, 0)) AS allocated_amount,
                    TRUE AS is_unallocated
                FROM account_payment pay
                JOIN account_move pay_move
                    ON pay_move.id = pay.move_id
                   AND pay_move.state = 'posted'
                JOIN account_move_line out_line
                    ON out_line.move_id = pay.move_id
                   AND out_line.account_id = pay.destination_account_id
                LEFT JOIN (
                    SELECT out_line2.move_id AS move_id, SUM(pr.amount) AS total_allocated
                    FROM account_partial_reconcile pr
                    JOIN account_move_line out_line2
                        ON out_line2.id = pr.debit_move_id OR out_line2.id = pr.credit_move_id
                    JOIN account_payment p2
                        ON p2.move_id = out_line2.move_id
                       AND out_line2.account_id = p2.destination_account_id
                    GROUP BY out_line2.move_id
                ) alloc ON alloc.move_id = pay.move_id
                WHERE pay.payment_type = 'inbound'
                  AND (pay.amount - COALESCE(alloc.total_allocated, 0)) > 0.005
            )
        """)
