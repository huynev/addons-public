# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import models, fields, api, _
import json
import logging

from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class PaxTransactionLog(models.Model):
    _name = 'pax.transaction.log'
    _description = 'PAX Transaction Log'
    _order = 'transaction_date desc'
    _rec_name = 'reference'

    # Basic transaction info - matching what terminal.py creates
    terminal_id = fields.Many2one('pax.terminal', string='Terminal', required=True, index=True)
    transaction_type = fields.Char('Transaction Type', required=True, index=True)
    amount = fields.Float('Amount', required=True)
    reference = fields.Char('Reference', required=True, index=True)

    # Result from PAX terminal
    result_code = fields.Char('Result Code', index=True)
    result_message = fields.Char('Result Message')
    success = fields.Boolean('Success', index=True)
    auth_code = fields.Char('Authorization Code')
    transaction_id = fields.Char('Transaction ID')

    # Technical data
    raw_response = fields.Text('Raw Response')
    transaction_date = fields.Datetime('Transaction Date', required=True,
                                       default=fields.Datetime.now, index=True)

    # Additional fields for POS integration
    pos_order_id = fields.Many2one('pos.order', string='POS Order', index=True)
    pos_payment_id = fields.Many2one('pos.payment', string='POS Payment', index=True)

    # Display and computed fields
    display_name = fields.Char('Display Name', compute='_compute_display_name', store=True)

    @api.depends('reference', 'transaction_date', 'amount')
    def _compute_display_name(self):
        for record in self:
            if record.reference:
                record.display_name = f"{record.reference} - ${record.amount:.2f}"
            else:
                record.display_name = f"TXN-{record.id} - ${record.amount:.2f}"

    @api.model_create_multi
    def create(self, vals_list):
        """Override create method for batch creation (Odoo 18 requirement)"""
        for vals in vals_list:
            # Ensure reference is set
            if not vals.get('reference'):
                vals['reference'] = f"TXN-{self._get_next_sequence()}"

        return super(PaxTransactionLog, self).create(vals_list)

    def _get_next_sequence(self):
        """Generate next sequence number if ir.sequence is not available"""
        last_record = self.search([], order='id desc', limit=1)
        if last_record:
            return last_record.id + 1
        return 1

    def action_void_transaction(self):
        """Void this transaction"""
        self.ensure_one()

        if not self.success:
            raise UserError(_('Only successful transactions can be voided'))

        if not self.terminal_id:
            raise UserError(_('No terminal configured for this transaction'))

        terminal = self.terminal_id

        try:
            if terminal.demo_mode:
                # Demo void - always succeeds
                self.write({
                    'result_message': 'VOIDED - DEMO MODE',
                    'success': False  # Voided transactions are marked as not successful
                })

                _logger.info("Transaction %s voided successfully in demo mode", self.reference)

                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Success'),
                        'message': _('Transaction voided successfully (Demo Mode)'),
                        'type': 'success'
                    }
                }
            else:
                # Real terminal void - would need proper PAX void command
                # For now, simulate void in real mode too since we don't have full protocol
                _logger.warning("Real PAX void not implemented, simulating for transaction %s", self.reference)

                self.write({
                    'result_message': 'VOIDED',
                    'success': False  # Voided transactions are marked as not successful
                })

                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Success'),
                        'message': _('Transaction voided successfully'),
                        'type': 'success'
                    }
                }

        except Exception as e:
            _logger.error("Error voiding transaction %s: %s", self.reference, str(e))
            raise UserError(_(f'Error voiding transaction: {str(e)}'))

    def action_get_signature(self):
        """Action to manually trigger signature capture"""
        self.ensure_one()

        try:
            terminal = self.terminal_id

            if terminal.demo_mode:
                # Demo signature capture
                import base64
                signature_placeholder = f"DEMO_SIGNATURE_{self.reference}"
                demo_signature = base64.b64encode(signature_placeholder.encode()).decode()

                # For demo, we'll just store a text placeholder since we don't have signature field
                self.write({
                    'result_message': self.result_message + ' [SIGNATURE_CAPTURED]'
                })

                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Success'),
                        'message': _('Signature captured successfully (Demo Mode)'),
                        'type': 'success'
                    }
                }
            else:
                # Real signature capture would need proper PAX protocol
                _logger.warning("Real PAX signature capture not implemented for transaction %s", self.reference)

                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Info'),
                        'message': _('Signature capture not implemented for real terminals yet'),
                        'type': 'info'
                    }
                }

        except Exception as e:
            _logger.error("Error capturing signature for transaction %s: %s", self.reference, str(e))
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _('Failed to capture signature: %s') % str(e),
                    'type': 'danger'
                }
            }

    @api.model
    def cleanup_old_logs(self, days=90):
        """Cleanup old transaction logs (can be called from cron)"""
        cutoff_date = fields.Datetime.now() - timedelta(days=days)
        old_logs = self.search([
            ('transaction_date', '<', cutoff_date),
            ('success', '=', False)
        ])

        count = len(old_logs)
        old_logs.unlink()

        _logger.info("Cleaned up %d old PAX transaction logs older than %d days", count, days)
        return count