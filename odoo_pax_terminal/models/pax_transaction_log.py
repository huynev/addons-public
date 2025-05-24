from odoo import models, fields, api, _
import json
import logging

_logger = logging.getLogger(__name__)


class PaxTransactionLog(models.Model):
    _name = 'pax.transaction.log'
    _description = 'PAX Transaction Log'
    _order = 'transaction_date desc'

    name = fields.Char('Reference', required=True, readonly=True, default='New')
    terminal_id = fields.Many2one('pax.terminal', string='Terminal', required=True)
    pos_order_id = fields.Many2one('pos.order', string='POS Order')
    pos_payment_id = fields.Many2one('pos.payment', string='POS Payment')

    transaction_type = fields.Selection([
        ('01', 'Sale'),
        ('02', 'Return'),
        ('03', 'Auth'),
        ('04', 'Post Auth'),
        ('05', 'Forced'),
        ('16', 'Void'),
        ('23', 'Balance'),
        ('99', 'Reversal'),
    ], string='Transaction Type', required=True)

    amount = fields.Float('Amount', required=True)
    tip_amount = fields.Float('Tip Amount')
    total_amount = fields.Float('Total Amount', compute='_compute_total_amount', store=True)

    transaction_date = fields.Datetime('Transaction Date', required=True, default=fields.Datetime.now)

    # Card information (masked for security)
    card_type = fields.Char('Card Type')
    card_number = fields.Char('Card Number (Masked)')
    cardholder_name = fields.Char('Cardholder Name')

    # Response from terminal
    response_code = fields.Char('Response Code')
    response_message = fields.Char('Response Message')
    auth_code = fields.Char('Authorization Code')
    reference_number = fields.Char('Reference Number')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('declined', 'Declined'),
        ('error', 'Error'),
        ('voided', 'Voided'),
    ], string='Status', default='draft', required=True)

    signature_data = fields.Binary('Signature Data')
    has_signature = fields.Boolean('Has Signature', compute='_compute_has_signature', store=True)

    raw_request = fields.Text('Raw Request', groups='base.group_erp_manager')
    raw_response = fields.Text('Raw Response', groups='base.group_erp_manager')

    @api.depends('amount', 'tip_amount')
    def _compute_total_amount(self):
        for record in self:
            record.total_amount = record.amount + (record.tip_amount or 0.0)

    @api.depends('signature_data')
    def _compute_has_signature(self):
        for record in self:
            record.has_signature = bool(record.signature_data)

    @api.model_create_multi
    def create(self, vals_list):
        """Override create method for batch creation (Odoo 18 requirement)"""
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('pax.transaction') or 'New'
        return super(PaxTransactionLog, self).create(vals_list)

    def get_signature(self):
        """Get signature from the terminal if it exists"""
        if not self.terminal_id:
            return False

        if self.state != 'approved':
            return False

        try:
            # If terminal is in demo mode, simulate signature
            if self.terminal_id.demo_mode:
                # In demo mode, just mark as having signature without actual image
                _logger.info("Demo mode: Signature capture simulated for transaction %s", self.name)
                return True
            else:
                # Real terminal implementation would go here
                # This would call the actual PAX terminal to get signature
                data = {
                    'command': 'A08',  # GetSignature command
                    'version': '1.28',
                    'offset': '0',
                    'requestlength': '90000'
                }

                # TODO: Implement actual PAX protocol communication
                _logger.info("Getting signature from real PAX terminal not implemented yet")
                return False

        except Exception as e:
            _logger.error("Error getting signature from PAX terminal: %s", str(e))
            return False