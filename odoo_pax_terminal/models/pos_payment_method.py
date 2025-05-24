# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging
import socket
import json
import base64
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
        params += ['pax_terminal_ip', 'pax_terminal_id']
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
        """Method called by the JavaScript to process payment

        Args:
            data (dict): Payment data from JavaScript

        Returns:
            dict: Payment result
        """
        _logger.debug("pax_send_payment called with data: %s", data)

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

            # Prepare PAX command
            amount_cents = int(amount * 100)  # Convert to cents

            # Create PAX command structure
            command_data = {
                'command': 'T00',  # DoCredit command
                'version': '1.28',
                'transactionType': data.get('transaction_type', '01'),
                'amount': str(amount_cents),
                'reference': data.get('reference', '1'),
                'clerk_id': data.get('clerk_id') or payment_method.pax_clerk_id or terminal.default_clerk_id or '',
                'timeout': data.get('timeout', terminal.timeout * 1000),
                'capture_signature': data.get('capture_signature', payment_method.pax_capture_signature),
            }

            # Process payment
            if terminal.demo_mode:
                result = self._simulate_pax_payment(terminal, amount, command_data)
            else:
                # Real PAX terminal processing
                encoded_command = self._encode_pax_command(command_data)
                response = self._send_to_pax_terminal(terminal, encoded_command, data.get('timeout', 120))
                result = self._parse_pax_response(response)

            # Create transaction log
            log_vals = {
                'terminal_id': terminal.id,
                'transaction_type': command_data['transactionType'],
                'amount': amount,
                'raw_request': json.dumps(command_data, indent=2),
                'raw_response': json.dumps(result, indent=2),
                'state': 'pending',
                'transaction_date': fields.Datetime.now(),
            }

            if result.get('success'):
                log_vals.update({
                    'response_code': result.get('response_code', ''),
                    'response_message': result.get('response_message', ''),
                    'reference_number': result.get('reference_number', ''),
                    'auth_code': result.get('auth_code', ''),
                    'card_type': result.get('card_type', ''),
                    'card_number': result.get('masked_card_number', ''),
                    'cardholder_name': result.get('cardholder_name', ''),
                    'state': 'approved'
                })

                # Create transaction log
                transaction_log = self.env['pax.transaction.log'].create(log_vals)

                response_data = {
                    'payment_status': 'success',
                    'transaction_id': result.get('reference_number') or result.get('transaction_id', ''),
                    'card_type': result.get('card_type', ''),
                    'pax_transaction_log_id': transaction_log.id,
                    'demo_mode': terminal.demo_mode,
                }

                # Add receipt data if available
                if result.get('receipt_merchant') or result.get('receipt_customer'):
                    response_data['ticket'] = result.get('receipt_customer', '')
                    response_data['receipt_data'] = {
                        'merchant_receipt': result.get('receipt_merchant', ''),
                        'customer_receipt': result.get('receipt_customer', ''),
                    }

                return response_data
            else:
                log_vals.update({
                    'response_message': result.get('error_message', 'Unknown error'),
                    'response_code': result.get('response_code', 'ERROR'),
                    'state': 'declined'
                })

                # Create transaction log
                self.env['pax.transaction.log'].create(log_vals)

                return {
                    'payment_status': 'failure',
                    'error_message': result.get('error_message', 'Transaction declined'),
                    'demo_mode': terminal.demo_mode,
                }

        except Exception as e:
            _logger.error("Error processing PAX payment: %s", str(e), exc_info=True)
            return {
                'payment_status': 'error',
                'error_message': f'Payment processing error: {str(e)}'
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
            reference_number = f"REF{random.randint(1000, 9999)}"
            masked_card = f"****-****-****-{random.randint(1000, 9999)}"

            # Generate fake receipt
            receipt_lines = [
                f"DEMO TRANSACTION - {card_type}",
                f"Amount: ${amount:.2f}",
                f"Card: {masked_card}",
                f"Auth: {auth_code}",
                f"Ref: {reference_number}",
                f"Date: {fields.Datetime.now().strftime('%m/%d/%Y %H:%M')}",
                "",
                "*** DEMO MODE ***",
                "Thank you!"
            ]

            return {
                'success': True,
                'response_code': '000000',
                'response_message': 'APPROVED - DEMO MODE',
                'transaction_id': transaction_id,
                'auth_code': auth_code,
                'reference_number': reference_number,
                'card_type': card_type,
                'masked_card_number': masked_card,
                'receipt_customer': '\n'.join(receipt_lines),
                'receipt_merchant': '\n'.join(receipt_lines + ["MERCHANT COPY"]),
            }
        else:
            # Simulate different types of failures
            failure_reasons = [
                ('001', 'DECLINED - INSUFFICIENT FUNDS'),
                ('002', 'DECLINED - CARD EXPIRED'),
                ('003', 'DECLINED - INVALID CARD'),
                ('004', 'DECLINED - CARD BLOCKED'),
                ('005', 'ERROR - COMMUNICATION TIMEOUT'),
                ('006', 'DECLINED - PIN REQUIRED'),
                ('007', 'DECLINED - CALL BANK'),
            ]

            error_code, error_message = random.choice(failure_reasons)

            return {
                'success': False,
                'response_code': error_code,
                'error_message': error_message + ' - DEMO MODE'
            }

    def _encode_pax_command(self, command_data):
        """Encode PAX command for transmission"""
        # In real implementation, this would format according to PAX protocol
        # For now, we'll use JSON encoding
        command_str = json.dumps(command_data)
        return base64.b64encode(command_str.encode('utf-8')).decode('utf-8')

    def _send_to_pax_terminal(self, terminal, encoded_command, timeout):
        """Send command to PAX terminal via HTTP/TCP"""
        try:
            # Example HTTP implementation
            # In real implementation, you'd use PAX-specific protocol
            url = f"http://{terminal.ip_address}:{terminal.port}/process"
            headers = {'Content-Type': 'application/json'}
            data = {'command': encoded_command}

            import requests
            response = requests.post(url, json=data, headers=headers, timeout=timeout)

            if response.status_code == 200:
                return response.text
            else:
                raise Exception(f"HTTP {response.status_code}: {response.text}")

        except Exception as e:
            _logger.error("Error communicating with PAX terminal: %s", str(e))
            raise Exception(f"Terminal communication failed: {str(e)}")

    def _parse_pax_response(self, response_text):
        """Parse response from PAX terminal"""
        try:
            # In real implementation, this would parse PAX protocol response
            # For now, we'll assume JSON response
            response_data = json.loads(response_text)

            # Map PAX response to our format
            if response_data.get('status') == 'approved':
                return {
                    'success': True,
                    'response_code': response_data.get('response_code', '000000'),
                    'response_message': response_data.get('message', 'Approved'),
                    'transaction_id': response_data.get('transaction_id', ''),
                    'auth_code': response_data.get('auth_code', ''),
                    'reference_number': response_data.get('reference', ''),
                    'card_type': response_data.get('card_type', ''),
                    'masked_card_number': response_data.get('masked_pan', ''),
                    'receipt_customer': response_data.get('customer_receipt', ''),
                    'receipt_merchant': response_data.get('merchant_receipt', ''),
                }
            else:
                return {
                    'success': False,
                    'response_code': response_data.get('response_code', 'ERROR'),
                    'error_message': response_data.get('message', 'Transaction failed')
                }

        except Exception as e:
            _logger.error("Error parsing PAX response: %s", str(e))
            return {
                'success': False,
                'response_code': 'PARSE_ERROR',
                'error_message': f'Failed to parse terminal response: {str(e)}'
            }