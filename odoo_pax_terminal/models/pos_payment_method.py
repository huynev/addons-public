# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging
import socket
import json
import time
import random
import xml.etree.ElementTree as ET

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

            # Convert amount to cents (PAX expects amount in cents)
            amount_cents = int(amount * 100)

            # Prepare command data
            command_data = {
                'command': 'T00',  # DoCredit command
                'amount': str(amount_cents).zfill(8),  # Amount in cents, zero-padded
                'transaction_type': data.get('transaction_type', payment_method.pax_transaction_type or '01'),
                'reference': data.get('reference', self._generate_reference()),
                'clerk_id': (data.get('clerk_id') or
                             payment_method.pax_clerk_id or
                             terminal.default_clerk_id or 'CASHIER01'),
                'timeout': data.get('timeout', terminal.timeout * 1000),  # Convert to milliseconds
            }

            # Process payment
            if terminal.demo_mode:
                _logger.info("Processing PAX payment in DEMO mode")
                result = self._simulate_pax_payment(terminal, amount, command_data)
            else:
                _logger.info("Processing PAX payment with REAL terminal")
                result = self._process_real_pax_payment(terminal, command_data)

            # Create transaction log
            log_vals = {
                'terminal_id': terminal.id,
                'transaction_type': command_data['transaction_type'],
                'amount': amount,
                'raw_request': json.dumps(command_data, indent=2),
                'raw_response': json.dumps(result, indent=2),
                'state': 'pending',
                'transaction_date': fields.Datetime.now(),
            }

            if result.get('success'):
                log_vals.update({
                    'response_code': result.get('result_code', ''),
                    'response_message': result.get('result_txt', ''),
                    'reference_number': result.get('reference_number', ''),
                    'auth_code': result.get('auth_code', ''),
                    'card_type': result.get('card_type', ''),
                    'card_number': result.get('card_number', ''),
                    'state': 'approved'
                })

                # Create transaction log
                transaction_log = self.env['pax.transaction.log'].create(log_vals)

                response_data = {
                    'payment_status': 'success',
                    'transaction_id': result.get('reference_number') or result.get('transaction_id', ''),
                    'card_type': result.get('card_type', ''),
                    'auth_code': result.get('auth_code', ''),
                    'pax_transaction_log_id': transaction_log.id,
                    'demo_mode': terminal.demo_mode,
                }

                # Add receipt data if available
                if result.get('receipt'):
                    response_data['ticket'] = result.get('receipt', '')

                _logger.info("PAX payment successful: %s", response_data)
                return response_data
            else:
                log_vals.update({
                    'response_message': result.get('result_txt', 'Unknown error'),
                    'response_code': result.get('result_code', 'ERROR'),
                    'state': 'declined'
                })

                # Create transaction log
                self.env['pax.transaction.log'].create(log_vals)

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

    def _process_real_pax_payment(self, terminal, command_data):
        """Process payment with real PAX terminal using XML protocol"""
        try:
            # Create XML command using terminal's method
            xml_command = terminal.create_xml_command(
                command_type=command_data['command'],
                amount=command_data['amount'],
                transaction_type=command_data['transaction_type'],
                reference=command_data['reference'],
                clerk_id=command_data['clerk_id'],
                timeout=command_data['timeout']
            )

            _logger.info("Sending XML command to PAX terminal: %s", xml_command)

            # Send command to terminal
            xml_response = terminal._send_tcp_command(xml_command, timeout=command_data['timeout'] / 1000)

            _logger.info("Received XML response from PAX terminal: %s", xml_response)

            # Parse response
            result = terminal.parse_xml_response(xml_response)

            return result

        except Exception as e:
            _logger.error("Error in real PAX payment processing: %s", str(e))
            return {
                'success': False,
                'result_code': 'COMM_ERROR',
                'result_txt': f'Communication error: {str(e)}',
                'message': 'Failed to communicate with terminal'
            }

    def _simulate_pax_payment(self, terminal, amount, command_data):
        """Simulate PAX payment for demo mode"""
        _logger.info("Simulating PAX payment in demo mode for amount: %s", amount)

        # Simulate processing time (1-3 seconds)
        time.sleep(random.uniform(1, 3))

        # Determine success based on success rate
        success_chance = random.uniform(0, 100)
        is_success = success_chance <= terminal.demo_success_rate

        if is_success:
            # Generate fake card data
            card_types = ['VISA', 'MASTERCARD', 'AMEX', 'DISCOVER', 'DEBIT']
            card_type = random.choice(card_types)

            # Generate fake transaction data
            transaction_id = f"DEMO{random.randint(100000, 999999)}"
            auth_code = f"{random.randint(100000, 999999)}"
            reference_number = command_data['reference']
            masked_card = f"****-****-****-{random.randint(1000, 9999)}"

            # Generate fake receipt
            receipt_lines = [
                f"*** DEMO TRANSACTION ***",
                f"Card Type: {card_type}",
                f"Amount: ${amount:.2f}",
                f"Card: {masked_card}",
                f"Auth: {auth_code}",
                f"Ref: {reference_number}",
                f"Date: {fields.Datetime.now().strftime('%m/%d/%Y %H:%M')}",
                "",
                "DEMO MODE - NOT A REAL TRANSACTION",
                "Thank you!"
            ]

            return {
                'success': True,
                'result_code': '000000',
                'result_txt': 'APPROVED - DEMO MODE',
                'transaction_id': transaction_id,
                'auth_code': auth_code,
                'reference_number': reference_number,
                'card_type': card_type,
                'card_number': masked_card,
                'receipt': '\n'.join(receipt_lines),
                'message': 'APPROVED - DEMO MODE',
            }
        else:
            # Simulate different types of failures
            failure_reasons = [
                ('100001', 'DECLINED - INSUFFICIENT FUNDS'),
                ('100002', 'DECLINED - CARD EXPIRED'),
                ('100003', 'DECLINED - INVALID CARD'),
                ('100004', 'DECLINED - CARD BLOCKED'),
                ('100005', 'ERROR - COMMUNICATION TIMEOUT'),
                ('100006', 'DECLINED - PIN REQUIRED'),
                ('100007', 'DECLINED - CALL BANK'),
            ]

            error_code, error_message = random.choice(failure_reasons)

            return {
                'success': False,
                'result_code': error_code,
                'result_txt': error_message + ' - DEMO MODE',
                'message': error_message + ' - DEMO MODE'
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

            terminal = transaction_log.terminal_id

            # Prepare void command
            command_data = {
                'command': 'T04',  # DoVoid command
                'transaction_type': '16',  # Void transaction type
                'reference': transaction_log.reference_number,
                'auth_code': transaction_log.auth_code,
                'timeout': terminal.timeout * 1000,
            }

            if terminal.demo_mode:
                # Demo void always succeeds
                result = {
                    'success': True,
                    'result_code': '000000',
                    'result_txt': 'VOIDED - DEMO MODE',
                    'message': 'VOIDED - DEMO MODE'
                }
            else:
                # Real terminal void
                xml_command = terminal.create_xml_command(
                    command_type=command_data['command'],
                    transaction_type=command_data['transaction_type'],
                    reference=command_data['reference'],
                    timeout=command_data['timeout']
                )

                xml_response = terminal._send_tcp_command(xml_command)
                result = terminal.parse_xml_response(xml_response)

            if result.get('success'):
                # Update transaction log status
                transaction_log.write({
                    'state': 'voided',
                    'response_message': result.get('result_txt', 'Voided'),
                })

                return {
                    'payment_status': 'success',
                    'message': 'Transaction voided successfully'
                }
            else:
                return {
                    'payment_status': 'failure',
                    'error_message': result.get('result_txt', 'Void failed')
                }

        except Exception as e:
            _logger.error("Error voiding PAX payment: %s", str(e))
            return {
                'payment_status': 'error',
                'error_message': f'Void processing error: {str(e)}'
            }