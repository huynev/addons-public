# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_compare, float_is_zero


class PaymentAllocationWizard(models.TransientModel):
    _name = 'payment.allocation.wizard'
    _description = 'Phân bổ thanh toán cho hoá đơn'

    payment_id = fields.Many2one(
        'account.payment', string='Thanh toán', required=True, readonly=True,
        ondelete='cascade')
    partner_id = fields.Many2one(
        related='payment_id.partner_id', string='Khách hàng', readonly=True)
    currency_id = fields.Many2one(
        related='payment_id.currency_id', string='Tiền tệ', readonly=True)
    amount_total = fields.Monetary(
        related='payment_id.amount', string='Tổng số tiền thanh toán (gốc)', readonly=True)
    amount_unallocated = fields.Monetary(
        string='Chưa phân bổ (tại thời điểm mở form)', readonly=True,
        help='Số tiền thực tế của khoản thanh toán này còn chưa được đối soát '
             'với bất kỳ hoá đơn nào, tính tại thời điểm mở wizard này — đã '
             'trừ đi mọi lần phân bổ trước đó.')
    amount_allocated = fields.Monetary(
        string='Đã phân bổ (trong phiên này)', compute='_compute_amounts')
    amount_available = fields.Monetary(
        string='Còn lại chưa phân bổ', compute='_compute_amounts')
    line_ids = fields.One2many(
        'payment.allocation.wizard.line', 'wizard_id', string='Hoá đơn còn nợ')

    # ------------------------------------------------------------------
    # Default get: nạp sẵn danh sách hoá đơn chưa thanh toán hết của
    # khách hàng gắn với payment đang mở wizard.
    # ------------------------------------------------------------------
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_model = self.env.context.get('active_model')
        active_id = self.env.context.get('active_id')
        if active_model == 'account.payment' and active_id:
            payment = self.env['account.payment'].browse(active_id)
            if payment.state != 'posted':
                raise UserError(_('Chỉ có thể phân bổ cho thanh toán đã vào sổ (Posted).'))
            if not payment.partner_id:
                raise UserError(_('Thanh toán chưa gắn khách hàng.'))
            res['payment_id'] = payment.id
            res['amount_unallocated'] = sum(
                abs(l.amount_residual) for l in self._get_payment_outstanding_lines(payment))
            open_lines = self._get_open_invoice_lines(payment)
            res['line_ids'] = [
                (0, 0, {
                    'move_line_id': line.id,
                    'amount_residual': abs(line.amount_residual),
                    'amount_to_allocate': 0.0,
                }) for line in open_lines
            ]
        return res

    def _get_payment_outstanding_lines(self, payment):
        """Các bút toán của payment trên tài khoản trung gian (outstanding)
        mà vẫn còn số dư chưa đối soát hết — đây là phần thực sự còn có thể
        đem đi phân bổ, KHÔNG phải là số tiền gốc của payment."""
        return payment.move_id.line_ids.filtered(
            lambda l: l.account_id == payment.destination_account_id
            and not l.reconciled
        )

    def _get_open_invoice_lines(self, payment):
        """Các dòng công nợ (receivable/payable) chưa đối soát hết, cùng
        khách hàng và cùng loại (khách hàng phải thu / nhà cung cấp phải trả)
        với payment."""
        move_type = ('out_invoice', 'out_refund') if payment.payment_type == 'inbound' \
            else ('in_invoice', 'in_refund')
        account_type = 'asset_receivable' if payment.payment_type == 'inbound' \
            else 'liability_payable'
        return self.env['account.move.line'].search([
            ('partner_id', '=', payment.partner_id.id),
            ('account_id.account_type', '=', account_type),
            ('move_id.state', '=', 'posted'),
            ('move_id.move_type', 'in', move_type),
            ('reconciled', '=', False),
        ], order='date_maturity asc, date asc')

    @api.depends('line_ids.amount_to_allocate', 'amount_unallocated')
    def _compute_amounts(self):
        for wizard in self:
            allocated = sum(wizard.line_ids.mapped('amount_to_allocate'))
            wizard.amount_allocated = allocated
            wizard.amount_available = wizard.amount_unallocated - allocated

    # ------------------------------------------------------------------
    # Xác nhận phân bổ: tạo account.partial.reconcile thủ công cho từng
    # cặp (dòng thanh toán, dòng hoá đơn) theo đúng số tiền người dùng nhập.
    # ------------------------------------------------------------------
    def action_allocate(self):
        self.ensure_one()
        precision = self.currency_id.decimal_places or 2
        lines = self.line_ids.filtered(
            lambda l: not float_is_zero(l.amount_to_allocate, precision_digits=precision))
        if not lines:
            raise UserError(_('Vui lòng nhập số tiền phân bổ cho ít nhất một hoá đơn.'))

        for line in lines:
            if line.amount_to_allocate < 0:
                raise UserError(_('Số tiền phân bổ không được âm.'))
            if float_compare(line.amount_to_allocate, line.amount_residual,
                              precision_digits=precision) > 0:
                raise UserError(_(
                    'Số tiền phân bổ cho hoá đơn %(name)s (%(amount).2f) vượt quá '
                    'số tiền còn nợ (%(residual).2f).'
                ) % {
                    'name': line.move_id.name,
                    'amount': line.amount_to_allocate,
                    'residual': line.amount_residual,
                })

        payment = self.payment_id
        # Lấy lại các dòng outstanding CÒN SỐ DƯ ngay tại thời điểm bấm xác
        # nhận (không dùng self.amount_unallocated, vì giá trị đó chỉ là
        # ảnh chụp lúc mở form — có thể đã bị thay đổi bởi thao tác khác).
        payment_lines = self._get_payment_outstanding_lines(payment)
        current_available = sum(abs(l.amount_residual) for l in payment_lines)

        total_allocated = sum(lines.mapped('amount_to_allocate'))
        if float_compare(total_allocated, current_available,
                          precision_digits=precision) > 0:
            raise UserError(_(
                'Tổng số tiền phân bổ (%(total).2f) vượt quá số tiền thanh toán '
                'còn chưa phân bổ hiện tại (%(available).2f). Có thể khoản '
                'thanh toán này vừa được phân bổ ở nơi khác — vui lòng đóng '
                'và mở lại wizard để lấy số liệu mới nhất.'
            ) % {'total': total_allocated, 'available': current_available})

        if not payment_lines:
            raise UserError(_(
                'Không tìm thấy bút toán thanh toán còn có thể đối soát trên '
                'tài khoản trung gian (Outstanding).'
            ))

        PartialReconcile = self.env['account.partial.reconcile']
        for line in lines:
            invoice_line = line.move_line_id
            remaining = line.amount_to_allocate
            for p_line in payment_lines:
                if float_is_zero(remaining, precision_digits=precision):
                    break
                p_line_available = abs(p_line.amount_residual)
                if float_is_zero(p_line_available, precision_digits=precision):
                    continue
                take = min(p_line_available, remaining)

                # Xác định dòng Nợ / dòng Có theo balance thực tế để tạo
                # partial reconcile đúng chiều.
                if p_line.balance < 0:
                    debit_line, credit_line = invoice_line, p_line
                else:
                    debit_line, credit_line = p_line, invoice_line

                PartialReconcile.create({
                    'debit_move_id': debit_line.id,
                    'credit_move_id': credit_line.id,
                    'amount': take,
                    'debit_amount_currency': take,
                    'credit_amount_currency': take,
                })
                remaining -= take

        return {'type': 'ir.actions.act_window_close'}


class PaymentAllocationWizardLine(models.TransientModel):
    _name = 'payment.allocation.wizard.line'
    _description = 'Dòng phân bổ thanh toán'

    wizard_id = fields.Many2one(
        'payment.allocation.wizard', required=True, ondelete='cascade')
    move_line_id = fields.Many2one(
        'account.move.line', string='Dòng công nợ', required=True,
        readonly=True, ondelete='cascade')
    move_id = fields.Many2one(
        related='move_line_id.move_id', string='Hoá đơn', readonly=True)
    invoice_date_due = fields.Date(
        related='move_line_id.move_id.invoice_date_due', string='Hạn thanh toán', readonly=True)
    currency_id = fields.Many2one(
        related='wizard_id.currency_id', string='Tiền tệ')
    amount_residual = fields.Monetary(
        string='Còn nợ', readonly=True)
    amount_to_allocate = fields.Monetary(
        string='Số tiền phân bổ')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('move_line_id'):
                raise UserError(_(
                    'Không thể tạo dòng phân bổ mới theo cách thủ công trong '
                    'wizard này. Danh sách hoá đơn phải được nạp tự động khi '
                    'mở wizard từ đúng một khoản thanh toán — vui lòng đóng '
                    'wizard, mở lại từ nút trên form Payment, không dùng '
                    '"Thêm 1 dòng".'
                ))
        return super().create(vals_list)
