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
    _rec_name = 'reference_number'

    name = fields.Char('Reference', required=True, readonly=True, default='New')
    terminal_id = fields.Many2one('pax.terminal', string='Terminal', required=True, index=True)
    pos_order_id = fields.Many2one('pos.order', string='POS Order', index=True)
    pos_payment_id = fields.Many2one('pos.payment', string='POS Payment', index=True)

    # Transaction Details
    transaction_type = fields.Selection([
        ('01', 'Sale'),
        ('02', 'Return'),
        ('03', 'Auth'),
        ('04', 'Post Auth'),
        ('05', 'Forced'),
        ('16', 'Void'),
        ('23', 'Balance'),
        ('99', 'Reversal'),
    ], string='Transaction Type', required=True, index=True)

    # Amount Information
    amount = fields.Float('Amount', required=True)
    tip_amount = fields.Float('Tip Amount', default=0.0)
    total_amount = fields.Float('Total Amount', compute='_compute_total_amount', store=True)

    # Transaction Timing
    transaction_date = fields.Datetime('Transaction Date', required=True,
                                       default=fields.Datetime.now, index=True)
    processed_date = fields.Datetime('Processed Date')

    # Card Information (masked for security)
    card_type = fields.Char('Card Type', size=20)
    card_number = fields.Char('Card Number (Masked)', size=50)
    cardholder_name = fields.Char('Cardholder Name', size=100)
    entry_method = fields.Selection([
        ('swipe', 'Swipe'),
        ('insert', 'Insert/Chip'),
        ('tap', 'Tap/Contactless'),
        ('manual', 'Manual Entry'),
    ], string='Entry Method')

    # Terminal Response Data
    response_code = fields.Char('Response Code', size=20, index=True)
    response_message = fields.Char('Response Message', size=200)
    auth_code = fields.Char('Authorization Code', size=20)
    reference_number = fields.Char('Reference Number', size=50, index=True)
    host_reference = fields.Char('Host Reference', size=50)

    # Transaction Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('declined', 'Declined'),
        ('error', 'Error'),
        ('voided', 'Voided'),
        ('refunded', 'Refunded'),
    ], string='Status', default='draft', required=True, index=True)

    # Signature and Receipt Data
    signature_data = fields.Binary('Signature Data')
    has_signature = fields.Boolean('Has Signature', compute='_compute_has_signature', store=True)
    receipt_merchant = fields.Text('Merchant Receipt')
    receipt_customer = fields.Text('Customer Receipt')

    # Technical Data (for debugging)
    raw_request = fields.Text('Raw Request', groups='base.group_erp_manager')
    raw_response = fields.Text('Raw Response', groups='base.group_erp_manager')

    # Additional Fields for Reporting
    clerk_id = fields.Char('Clerk ID', size=50)
    station_id = fields.Char('Station ID', size=50)
    batch_number = fields.Char('Batch Number', size=20)

    # Error tracking
    error_code = fields.Char('Error Code', size=20)
    error_message = fields.Text('Error Message')

    # Computed fields
    display_name = fields.Char('Display Name', compute='_compute_display_name', store=True)
    is_successful = fields.Boolean('Is Successful', compute='_compute_is_successful', store=True)

    @api.depends('amount', 'tip_amount')
    def _compute_total_amount(self):
        for record in self:
            record.total_amount = record.amount + (record.tip_amount or 0.0)

    @api.depends('signature_data')
    def _compute_has_signature(self):
        for record in self:
            record.has_signature = bool(record.signature_data)

    @api.depends('reference_number', 'transaction_date', 'amount')
    def _compute_display_name(self):
        for record in self:
            if record.reference_number:
                record.display_name = f"{record.reference_number} - ${record.amount:.2f}"
            else:
                record.display_name = f"{record.name} - ${record.amount:.2f}"

    @api.depends('state', 'response_code')
    def _compute_is_successful(self):
        for record in self:
            record.is_successful = (record.state == 'approved' and
                                    record.response_code in ['000000', '00', 'APPROVED'])

    @api.model_create_multi
    def create(self, vals_list):
        """Override create method for batch creation (Odoo 18 requirement)"""
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                sequence = self.env['ir.sequence'].next_by_code('pax.transaction')
                vals['name'] = sequence or f"PAX-{self._get_next_sequence()}"

            # Set processed date when transaction is created
            if not vals.get('processed_date'):
                vals['processed_date'] = fields.Datetime.now()

        return super(PaxTransactionLog, self).create(vals_list)

    def _get_next_sequence(self):
        """Generate next sequence number if ir.sequence is not available"""
        last_record = self.search([], order='id desc', limit=1)
        if last_record:
            return last_record.id + 1
        return 1

    def get_signature(self):
        """Get signature from the terminal if it exists"""
        self.ensure_one()

        if not self.terminal_id:
            _logger.warning("No terminal configured for transaction log %s", self.name)
            return False

        if self.state not in ['approved', 'pending']:
            _logger.warning("Cannot get signature for transaction %s in state %s", self.name, self.state)
            return False

        try:
            # If terminal is in demo mode, simulate signature
            if self.terminal_id.demo_mode:
                # In demo mode, create a simple signature placeholder
                _logger.info("Demo mode: Signature capture simulated for transaction %s", self.name)

                # Create a simple base64 encoded placeholder
                import base64
                signature_placeholder = "DEMO_SIGNATURE_DATA"
                self.signature_data = base64.b64encode(signature_placeholder.encode()).decode()
                return True
            else:
                # Real terminal signature capture
                return self._get_real_signature()

        except Exception as e:
            _logger.error("Error getting signature from PAX terminal: %s", str(e))
            self.error_message = f"Signature capture failed: {str(e)}"
            return False

    def _get_real_signature(self):
        """Get signature from real PAX terminal"""
        try:
            # Create XML command for signature retrieval
            xml_command = self.terminal_id.create_xml_command(
                command_type='A08',  # GetSignature command
                reference=self.reference_number,
                timeout=30000
            )

            _logger.info("Requesting signature from PAX terminal for transaction %s", self.name)

            # Send command to terminal
            xml_response = self.terminal_id._send_tcp_command(xml_command, timeout=30)

            # Parse response
            result = self.terminal_id.parse_xml_response(xml_response)

            if result.get('success'):
                # Extract signature data from response
                signature_data = result.get('signature_data')
                if signature_data:
                    self.signature_data = signature_data
                    _logger.info("Signature captured successfully for transaction %s", self.name)
                    return True
                else:
                    _logger.warning("No signature data in response for transaction %s", self.name)
                    return False
            else:
                error_msg = result.get('result_txt', 'Signature capture failed')
                _logger.error("Signature capture failed for transaction %s: %s", self.name, error_msg)
                self.error_message = error_msg
                return False

        except Exception as e:
            _logger.error("Error getting signature from real PAX terminal: %s", str(e))
            self.error_message = f"Signature capture error: {str(e)}"
            return False

    def action_void_transaction(self):
        """Void this transaction"""
        self.ensure_one()

        if self.state != 'approved':
            raise UserError(_('Only approved transactions can be voided'))

        if self.terminal_id.demo_mode:
            # Demo void
            self.write({
                'state': 'voided',
                'response_message': 'VOIDED - DEMO MODE'
            })
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
            # Real void
            try:
                xml_command = self.terminal_id.create_xml_command(
                    command_type='T04',  # DoVoid command
                    transaction_type='16',
                    reference=self.reference_number,
                    timeout=30000
                )

                xml_response = self.terminal_id._send_tcp_command(xml_command)
                result = self.terminal_id.parse_xml_response(xml_response)

                if result.get('success'):
                    self.write({
                        'state': 'voided',
                        'response_message': result.get('result_txt', 'Voided'),
                        'processed_date': fields.Datetime.now()
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
                else:
                    error_msg = result.get('result_txt', 'Void failed')
                    self.error_message = error_msg
                    raise UserError(_(f'Void failed: {error_msg}'))

            except Exception as e:
                _logger.error("Error voiding transaction %s: %s", self.name, str(e))
                self.error_message = f"Void error: {str(e)}"
                raise UserError(_(f'Error voiding transaction: {str(e)}'))

    def action_get_signature(self):
        """Action to manually trigger signature capture"""
        self.ensure_one()

        if self.get_signature():
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _('Signature captured successfully'),
                    'type': 'success'
                }
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _('Failed to capture signature: %s') % (self.error_message or 'Unknown error'),
                    'type': 'danger'
                }
            }

    def action_print_receipt(self):
        """Print receipt for this transaction"""
        self.ensure_one()

        if not self.receipt_customer and not self.receipt_merchant:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Warning'),
                    'message': _('No receipt data available for this transaction'),
                    'type': 'warning'
                }
            }

        # Return action to open receipt in new window
        return {
            'type': 'ir.actions.act_window',
            'name': _('Transaction Receipt'),
            'res_model': 'pax.transaction.log',
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': self.env.ref('your_module.pax_transaction_receipt_view').id,
            'target': 'new',
        }

    @api.model
    def cleanup_old_logs(self, days=90):
        """Cleanup old transaction logs (can be called from cron)"""
        cutoff_date = fields.Datetime.now() - timedelta(days=days)
        old_logs = self.search([
            ('transaction_date', '<', cutoff_date),
            ('state', 'in', ['declined', 'error'])
        ])

        count = len(old_logs)
        old_logs.unlink()

        _logger.info("Cleaned up %d old PAX transaction logs older than %d days", count, days)
        return count