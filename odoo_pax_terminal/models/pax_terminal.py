# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import json
import logging
import socket
import base64
import binascii
from datetime import datetime
import urllib.parse
import urllib.request

_logger = logging.getLogger(__name__)


class PaxTerminal(models.Model):
    _name = 'pax.terminal'
    _inherit = ['pos.load.mixin']
    _description = 'PAX Terminal Configuration'

    name = fields.Char('Terminal Name', required=True)
    ip_address = fields.Char('IP Address', required=True, default='127.0.0.1')
    port = fields.Integer('Port', required=True, default=10009)
    active = fields.Boolean('Active', default=True)
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.company)

    # Relationships
    payment_method_ids = fields.One2many('pos.payment.method', 'pax_terminal_id',
                                         string='Payment Methods')
    transaction_log_ids = fields.One2many('pax.transaction.log', 'terminal_id',
                                          string='Transaction Logs')
    pos_config_ids = fields.Many2many('pos.config', string='Point of Sale Configurations',
                                      help='POS configurations that can use this terminal')

    # Communication Settings
    timeout_initialize = fields.Integer('Initialize Timeout (ms)', default=120000,
                                        help='Timeout for Initialize command')
    timeout_signature = fields.Integer('Signature Timeout (ms)', default=120000,
                                       help='Timeout for signature commands')
    timeout_credit = fields.Integer('Credit Timeout (ms)', default=120000,
                                    help='Timeout for credit transactions')

    # PAX Protocol Settings - HTTP based like the JS version
    protocol_type = fields.Selection([
        ('http', 'HTTP'),
        ('https', 'HTTPS'),
    ], string='Protocol Type', default='http', required=True,
        help='Communication protocol to use with PAX terminal')

    # Demo Mode Settings
    demo_mode = fields.Boolean('Demo Mode', default=False,
                               help='Enable demo mode for testing without real PAX terminal')
    demo_success_rate = fields.Float('Demo Success Rate (%)', default=90.0,
                                     help='Success rate for demo transactions (0-100%)')

    # Default Transaction Settings
    default_clerk_id = fields.Char('Default Clerk ID', default='CASHIER01',
                                   help='Default clerk ID for transactions')
    default_reference_prefix = fields.Char('Default Reference Prefix', default='REF',
                                           help='Prefix for reference numbers')

    # PAX Protocol Constants
    STX = 0x02  # Start of Text
    ETX = 0x03  # End of Text
    FS = 0x1C  # Field Separator
    US = 0x1F  # Unit Separator

    @api.model
    def _load_pos_data_domain(self, data):
        """Define which PAX terminals should be loaded for this POS session"""
        config_id = self.env['pos.config'].browse(data['pos.config']['data'][0]['id'])

        domain = [
            ('active', '=', True),
            ('company_id', '=', config_id.company_id.id),
            '|',
            ('pos_config_ids', '=', False),  # Available to all POS configs
            ('pos_config_ids', 'in', [config_id.id])  # Assigned to this POS config
        ]
        return domain

    @api.model
    def _load_pos_data_fields(self, config_id):
        """Define which fields should be loaded in POS"""
        return [
            'name', 'ip_address', 'port', 'active', 'company_id', 'protocol_type',
            'timeout_initialize', 'timeout_signature', 'timeout_credit',
            'demo_mode', 'demo_success_rate',
            'default_clerk_id', 'default_reference_prefix'
        ]

    def test_connection(self):
        """Test the connection to the PAX terminal"""
        if self.demo_mode:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Demo Mode'),
                    'message': _('PAX terminal %s is running in DEMO MODE - no real device needed') % self.name,
                    'sticky': False,
                    'type': 'info'
                }
            }

        try:
            # Test Initialize command
            result = self.initialize_terminal()
            if result['success']:
                message = _('Successfully connected to PAX terminal %s') % self.name
            else:
                raise Exception(result.get('message', 'Unknown error'))

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': message,
                    'sticky': False,
                    'type': 'success'
                }
            }
        except Exception as e:
            _logger.error("Error connecting to PAX terminal: %s", str(e))
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Connection Error'),
                    'message': _(
                        'Failed to connect to PAX terminal: %s\n\nTip: Check IP address, port, and enable Demo Mode for testing') % str(
                        e),
                    'sticky': True,
                    'type': 'danger'
                }
            }

    def _get_lrc(self, params):
        """Calculate LRC (Longitudinal Redundancy Check) like in JS version"""
        lrc = 0
        for i in range(1, len(params)):
            if isinstance(params[i], str):
                for char in params[i]:
                    lrc ^= ord(char)
            else:
                lrc ^= params[i]

        return chr(lrc) if lrc > 0 else chr(0)

    def _string_to_hex(self, text):
        """Convert string to hex representation"""
        hex_parts = []
        for char in text:
            hex_val = format(ord(char), 'x')
            if len(hex_val) == 1:
                hex_val = '0' + hex_val
            hex_parts.append(hex_val)
        return ' '.join(hex_parts)

    def _hex_to_string(self, hex_text):
        """Convert hex to string"""
        result = ""
        hex_parts = hex_text.split(" ")
        for hex_part in hex_parts:
            if hex_part:
                try:
                    result += chr(int(hex_part, 16))
                except ValueError:
                    continue
        return result

    def _encode_base64_from_hex(self, hex_string):
        """Convert hex string to base64"""
        try:
            # Remove spaces and convert to bytes
            hex_clean = hex_string.replace(" ", "")
            byte_data = bytes.fromhex(hex_clean)
            return base64.b64encode(byte_data).decode('ascii')
        except Exception as e:
            _logger.error("Error encoding base64 from hex: %s", str(e))
            return ""

    def _send_http_command(self, command_type, url, timeout_ms=30000):
        """Send HTTP command to PAX terminal like JS version"""
        try:
            timeout_sec = timeout_ms / 1000.0

            _logger.info("Sending PAX command %s to: %s", command_type, url)

            request = urllib.request.Request(url, method='GET')
            with urllib.request.urlopen(request, timeout=timeout_sec) as response:
                response_text = response.read().decode('utf-8')
                _logger.info("Raw PAX response: %s", response_text)

                return self._parse_pax_response(response_text, command_type)

        except urllib.error.URLError as e:
            _logger.error("HTTP error connecting to PAX terminal: %s", str(e))
            return {
                'success': False,
                'error': f'HTTP connection failed: {str(e)}',
                'message': 'Failed to connect to PAX terminal'
            }
        except Exception as e:
            _logger.error("Error in HTTP communication: %s", str(e))
            return {
                'success': False,
                'error': str(e),
                'message': 'Communication error with PAX terminal'
            }

    def _parse_pax_response(self, response_text, command_type):
        """Parse PAX response like JS version"""
        try:
            # Convert response to hex
            response_hex = self._string_to_hex(response_text)
            hex_parts = response_hex.split(" ")

            # Verify LRC
            if len(hex_parts) > 0:
                check_params = hex_parts[-1]
                redundancy_check = hex_parts[-1][1:] if len(hex_parts[-1]) > 1 else ""

                # Parse packet info
                packet_info = []
                etx_index = None

                # Find ETX (03) position
                for i, part in enumerate(hex_parts):
                    if part == "03":
                        etx_index = i
                        break

                if etx_index is not None:
                    # Split by STX (02) and FS (1c)
                    hex_data = " ".join(hex_parts[:etx_index])

                    # Parse based on separators
                    parts = []
                    current_part = ""

                    for part in hex_parts[:etx_index]:
                        if part == "02":  # STX
                            if current_part:
                                parts.append(current_part.strip())
                            current_part = ""
                        elif part == "1c":  # FS
                            if current_part:
                                parts.append(current_part.strip())
                            current_part = ""
                        else:
                            if current_part:
                                current_part += " " + part
                            else:
                                current_part = part

                    if current_part:
                        parts.append(current_part.strip())

                    # Convert hex parts to strings
                    for part in parts:
                        if part:
                            converted = self._hex_to_string(part)
                            if converted:
                                packet_info.append(converted)

                _logger.info("Parsed PAX packet info: %s", packet_info)

                return {
                    'success': True,
                    'packet_info': packet_info,
                    'raw_response': response_text
                }

            return {
                'success': False,
                'error': 'Invalid response format',
                'raw_response': response_text
            }

        except Exception as e:
            _logger.error("Error parsing PAX response: %s", str(e))
            return {
                'success': False,
                'error': f'Parse error: {str(e)}',
                'raw_response': response_text
            }

    def initialize_terminal(self, version="1.28"):
        """Initialize PAX terminal like JS Initialize function"""
        try:
            command = "A08"

            # Build params for LRC calculation
            params = [self.STX, command, self.FS, version, self.ETX]
            lrc = self._get_lrc(params)

            # Encode to base64 hex
            command_hex = self._string_to_hex(base64.b64encode(command.encode()).decode())
            version_hex = self._string_to_hex(base64.b64encode(version.encode()).decode())
            lrc_hex = self._string_to_hex(base64.b64encode(lrc.encode()).decode())

            # Build elements array
            elements = [
                format(self.STX, '02x'),
                command_hex,
                format(self.FS, '02x'),
                version_hex,
                format(self.ETX, '02x'),
                lrc_hex
            ]

            final_string = " ".join(elements)
            final_b64 = self._encode_base64_from_hex(final_string)

            # Build URL
            base_url = f"{self.protocol_type}://{self.ip_address}:{self.port}"
            url = f"{base_url}?{final_b64}"

            _logger.info("PAX Initialize URL: %s", url)

            return self._send_http_command('Initialize', url, self.timeout_initialize)

        except Exception as e:
            _logger.error("Error in initialize_terminal: %s", str(e))
            return {
                'success': False,
                'error': str(e),
                'message': 'Failed to initialize PAX terminal'
            }

    def do_credit_transaction(self, amount, transaction_type="01", reference="", **kwargs):
        """Perform credit transaction like JS DoCredit function"""
        try:
            if self.demo_mode:
                result = self._simulate_transaction(amount, transaction_type, reference)
                # Log demo transaction
                self._log_transaction('credit', amount, result, reference)
                return result

            command = "T00"
            version = "1.28"

            # Prepare transaction data
            amount_info = {
                'amount': str(int(float(amount) * 100)),  # Convert to cents
                'cashback': '',
                'tip': ''
            }

            account_info = {
                'account': '',
                'expiry': '',
                'cvv': ''
            }

            trace_info = {
                'reference': reference or f"{self.default_reference_prefix}{datetime.now().strftime('%Y%m%d%H%M%S')}",
                'invoice': '',
                'auth_code': ''
            }

            # Build params for LRC calculation
            params = [self.STX, command, self.FS, version, self.FS, transaction_type]

            # Add amount information
            params.extend([self.FS])
            for key, value in amount_info.items():
                if value:
                    params.extend([value, self.US])
                else:
                    params.extend([self.US])

            # Add other sections similarly...
            params.extend([self.ETX])

            lrc = self._get_lrc(params)

            # Encode elements
            command_hex = self._string_to_hex(base64.b64encode(command.encode()).decode())
            version_hex = self._string_to_hex(base64.b64encode(version.encode()).decode())
            trans_type_hex = self._string_to_hex(base64.b64encode(transaction_type.encode()).decode())

            elements = [
                format(self.STX, '02x'),
                command_hex,
                format(self.FS, '02x'),
                version_hex,
                format(self.FS, '02x'),
                trans_type_hex,
                format(self.FS, '02x')
            ]

            # Add amount info
            for key, value in amount_info.items():
                if value:
                    value_hex = self._string_to_hex(base64.b64encode(value.encode()).decode())
                    elements.extend([value_hex, format(self.US, '02x')])
                else:
                    elements.append(format(self.US, '02x'))

            elements.extend([
                format(self.ETX, '02x'),
                self._string_to_hex(base64.b64encode(lrc.encode()).decode())
            ])

            final_string = " ".join(elements)
            final_b64 = self._encode_base64_from_hex(final_string)

            # Build URL
            base_url = f"{self.protocol_type}://{self.ip_address}:{self.port}"
            url = f"{base_url}?{final_b64}"

            _logger.info("PAX DoCredit URL: %s", url)

            result = self._send_http_command('DoCredit', url, self.timeout_credit)

            # Log transaction
            self._log_transaction('credit', amount, result, reference)

            return result

        except Exception as e:
            _logger.error("Error in do_credit_transaction: %s", str(e))
            return {
                'success': False,
                'error': str(e),
                'message': 'Credit transaction failed'
            }

    def _simulate_transaction(self, amount, transaction_type, reference):
        """Simulate transaction for demo mode"""
        import random

        success = random.randint(1, 100) <= self.demo_success_rate

        if success:
            return {
                'success': True,
                'result_code': '000000',
                'result_txt': 'APPROVED',
                'auth_code': f'AUTH{random.randint(100000, 999999)}',
                'reference_number': reference or f'REF{random.randint(10000, 99999)}',
                'transaction_id': f'TXN{random.randint(100000, 999999)}',
                'card_type': 'VISA',
                'card_number': '****1234',
                'message': 'Transaction Approved',
                'amount': amount
            }
        else:
            return {
                'success': False,
                'result_code': '100001',
                'result_txt': 'DECLINED',
                'message': 'Transaction Declined - Demo Mode',
                'amount': amount
            }

    def _log_transaction(self, transaction_type, amount, result, reference):
        """Log transaction to database"""
        try:
            self.env['pax.transaction.log'].create({
                'terminal_id': self.id,
                'transaction_type': transaction_type,
                'amount': float(amount),
                'reference': reference,
                'result_code': result.get('result_code', ''),
                'result_message': result.get('result_txt', ''),
                'success': result.get('success', False),
                'auth_code': result.get('auth_code', ''),
                'transaction_id': result.get('transaction_id', ''),
                'raw_response': str(result),
                'transaction_date': datetime.now()
            })
        except Exception as e:
            _logger.error("Error logging PAX transaction: %s", str(e))

    @api.model
    def get_terminal_config_for_pos(self, pos_config_id):
        """Get terminal configuration for POS"""
        terminals = self.search([
            ('active', '=', True),
            '|',
            ('pos_config_ids', '=', False),
            ('pos_config_ids', 'in', [pos_config_id])
        ])

        return [{
            'id': terminal.id,
            'name': terminal.name,
            'ip_address': terminal.ip_address,
            'port': terminal.port,
            'protocol_type': terminal.protocol_type,
            'demo_mode': terminal.demo_mode,
            'timeout_credit': terminal.timeout_credit,
            'timeout_initialize': terminal.timeout_initialize,
            'timeout_signature': terminal.timeout_signature,
        } for terminal in terminals]