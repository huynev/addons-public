# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging
import json
import time
import random

_logger = logging.getLogger(__name__)


class PosPaymentMethod(models.Model):
    _inherit = 'pos.payment.method'

    def _get_payment_terminal_selection(self):
        return super(PosPaymentMethod, self)._get_payment_terminal_selection() + [('pax', 'PAX')]

    pax_terminal_id = fields.Many2one('pax.terminal', string='PAX Terminal',
                                      help='PAX terminal to use for this payment method')

    # PAX specific configurations
    pax_transaction_type = fields.Selection([
        ('01', 'Sale'),
        ('02', 'Return'),
        ('03', 'Auth'),
        ('04', 'Post Auth'),
        ('05', 'Forced'),
        ('16', 'Void'),
        ('23', 'Balance Check'),
        ('99', 'Reversal'),
    ], string='Default Transaction Type', default='01',
        help='Default transaction type to use with PAX terminal')

    pax_capture_signature = fields.Boolean('Capture Signature', default=True,
                                           help='Capture customer signature for this payment method')

    pax_clerk_id = fields.Char('Clerk ID',
                               help='Clerk ID to use for PAX terminal transactions')

    # Add terminal IP for direct access (optional)
    pax_terminal_ip = fields.Char('Terminal IP', related='pax_terminal_id.ip_address', readonly=True)

    @api.model
    def _load_pos_data_fields(self, config_id):
        params = super()._load_pos_data_fields(config_id)
        params += ['pax_terminal_ip', 'pax_terminal_id', 'pax_transaction_type',
                   'pax_capture_signature', 'pax_clerk_id']
        return params

    @api.constrains('use_payment_terminal', 'pax_terminal_id')
    def _check_pax_terminal(self):
        """Validate PAX terminal configuration"""
        for method in self:
            if method.use_payment_terminal == 'pax' and not method.pax_terminal_id:
                raise ValidationError(
                    _('PAX terminal must be selected for payment method %s') % method.name
                )

    @api.model
    def pax_send_payment(self, data):
        """Method called by JavaScript to process payment with real PAX protocol

        Args:
            data (dict): Payment data from JavaScript

        Returns:
            dict: Payment result
        """
        _logger.info("PAX payment request received: %s", data)

        # Get payment method ID from data
        payment_method_id = data.get('payment_method_id')
        if not payment_method_id:
            return {
                'payment_status': 'error',
                'error_message': _('Payment method ID not provided')
            }

        # Get the payment method record
        payment_method = self.browse(payment_method_id)
        if not payment_method.exists():
            return {
                'payment_status': 'error',
                'error_message': _('Payment method not found')
            }

        if not payment_method.pax_terminal_id:
            return {
                'payment_status': 'error',
                'error_message': _('No PAX terminal configured for this payment method')
            }

        terminal = payment_method.pax_terminal_id

        try:
            # Validate amount
            amount = float(data.get('amount', 0.0))
            if amount <= 0:
                return {
                    'payment_status': 'error',
                    'error_message': _('Invalid payment amount')
                }

            # Prepare transaction data
            transaction_data = {
                'amount': amount,
                'transaction_type': data.get('transaction_type', payment_method.pax_transaction_type or '01'),
                'reference': data.get('reference', self._generate_reference()),
                'clerk_id': (data.get('clerk_id') or
                             payment_method.pax_clerk_id or
                             terminal.default_clerk_id or 'CASHIER01'),
            }

            # Process payment using terminal's method
            result = terminal.do_credit_transaction(**transaction_data)

            if result.get('success'):
                response_data = {
                    'payment_status': 'success',
                    'transaction_id': result.get('reference_number') or result.get('transaction_id', ''),
                    'card_type': result.get('card_type', ''),
                    'auth_code': result.get('auth_code', ''),
                    'demo_mode': terminal.demo_mode,
                    'amount': amount,
                }

                # Add receipt data if available
                if result.get('receipt'):
                    response_data['ticket'] = result.get('receipt', '')

                _logger.info("PAX payment successful: %s", response_data)
                return response_data
            else:
                error_message = result.get('result_txt') or result.get('message', 'Transaction declined')
                _logger.warning("PAX payment failed: %s", error_message)

                return {
                    'payment_status': 'failure',
                    'error_message': error_message,
                    'demo_mode': terminal.demo_mode,
                }

        except Exception as e:
            _logger.error("Error processing PAX payment: %s", str(e), exc_info=True)
            return {
                'payment_status': 'error',
                'error_message': f'Payment processing error: {str(e)}'
            }

    def _generate_reference(self):
        """Generate unique reference number"""
        timestamp = int(time.time())
        random_num = random.randint(100, 999)
        return f"REF{timestamp}{random_num}"[-12:]  # Keep last 12 chars

    @api.model
    def pax_void_payment(self, data):
        """Void a PAX payment transaction"""
        try:
            transaction_log_id = data.get('transaction_log_id')
            if not transaction_log_id:
                return {
                    'payment_status': 'error',
                    'error_message': _('Transaction log ID not provided')
                }

            transaction_log = self.env['pax.transaction.log'].browse(transaction_log_id)
            if not transaction_log.exists():
                return {
                    'payment_status': 'error',
                    'error_message': _('Transaction log not found')
                }

            # Use the void method from transaction log
            try:
                transaction_log.action_void_transaction()
                return {
                    'payment_status': 'success',
                    'message': 'Transaction voided successfully'
                }
            except Exception as e:
                return {
                    'payment_status': 'failure',
                    'error_message': str(e)
                }

        except Exception as e:
            _logger.error("Error voiding PAX payment: %s", str(e))
            return {
                'payment_status': 'error',
                'error_message': f'Void processing error: {str(e)}'
            }