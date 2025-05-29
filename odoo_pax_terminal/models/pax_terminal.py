# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import json
import logging
import base64
import binascii
from datetime import datetime
import urllib.parse
import urllib.request
import random

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

    # PAX Protocol Constants (matching JS version)
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

    def _hex_to_base64(self, hex_str):
        """Convert hex string to base64 (matching JS hexToBase64 function)"""
        try:
            # Remove spaces and convert hex to bytes
            hex_clean = hex_str.replace(" ", "").replace("\r", "").replace("\n", "")

            # Split into pairs and convert to characters
            chars = []
            i = 0
            while i < len(hex_clean):
                if i + 1 < len(hex_clean):
                    hex_pair = hex_clean[i:i + 2]
                    try:
                        chars.append(chr(int(hex_pair, 16)))
                    except ValueError:
                        chars.append(chr(0))
                    i += 2
                else:
                    chars.append(chr(int(hex_clean[i], 16)))
                    i += 1

            # Join characters and encode to base64
            char_string = ''.join(chars)
            return base64.b64encode(char_string.encode('latin-1')).decode('ascii')

        except Exception as e:
            _logger.error("Error in _hex_to_base64: %s", str(e))
            return ""

    def _base64_to_hex(self, b64_str):
        """Convert base64 to hex (matching JS base64ToHex function)"""
        try:
            decoded = base64.b64decode(b64_str).decode('latin-1')
            hex_parts = []
            for char in decoded:
                hex_val = format(ord(char), 'x')
                if len(hex_val) == 1:
                    hex_val = "0" + hex_val
                hex_parts.append(hex_val)
            return " ".join(hex_parts)
        except Exception as e:
            _logger.error("Error in _base64_to_hex: %s", str(e))
            return ""

    def _string_to_hex(self, text):
        """Convert string to hex (matching JS StringToHex function)"""
        if not text:
            return ""

        hex_parts = []
        for char in text:
            hex_val = format(ord(char), 'x')
            if len(hex_val) == 1:
                hex_val = "0" + hex_val
            hex_parts.append(hex_val)
        return " ".join(hex_parts)

    def _hex_to_string(self, hex_text):
        """Convert hex to string (matching JS HexToString function)"""
        if not hex_text:
            return ""

        result = ""
        hex_parts = hex_text.split(" ")
        for hex_part in hex_parts:
            if hex_part:
                try:
                    result += chr(int(hex_part, 16))
                except ValueError:
                    continue
        return result

    def _get_lrc(self, params):
        lrc = 0
        for i in range(1, len(params)):
            if isinstance(params[i], str):
                # Iterate through each character in the string
                for char in params[i]:
                    lrc ^= ord(char)
            else:
                lrc ^= params[i]

        return chr(lrc) if lrc > 0 else 0

    def _send_http_command(self, command_type, url, timeout_ms=30000):
        """Send HTTP command to PAX terminal"""
        try:
            timeout_sec = timeout_ms / 1000.0

            _logger.info("Sending PAX %s command to: %s", command_type, url)

            request = urllib.request.Request(url, method='GET')
            with urllib.request.urlopen(request, timeout=timeout_sec) as response:
                response_text = response.read().decode('utf-8')
                _logger.info("Raw PAX response: %s", response_text)

                return self._parse_pax_response(response_text, command_type)

        except Exception as e:
            _logger.error("Error in HTTP communication: %s", str(e))
            return {
                'success': False,
                'error': str(e),
                'message': f'Communication error: {str(e)}'
            }

    def _parse_pax_response(self, response_text, command_type):
        """Parse PAX response exactly like JS version"""
        try:
            # Convert response to hex
            response_hex = self._string_to_hex(response_text)

            # Verify LRC (basic check)
            hex_parts = response_hex.split(" ")
            if len(hex_parts) < 2:
                return {
                    'success': False,
                    'error': 'Invalid response format',
                    'raw_response': response_text
                }

            # Parse packet info
            packet_info = []

            # Find ETX position
            etx_pos = response_hex.find("03")
            if etx_pos == -1:
                return {
                    'success': False,
                    'error': 'ETX not found in response',
                    'raw_response': response_text
                }

            # Get hex data before ETX
            hex_data = response_hex[:etx_pos - 1] if etx_pos > 0 else response_hex

            # Split by STX (02) and FS (1c) like JS version
            import re
            hex_parts = re.split(r'02|1c', hex_data)

            for hex_part in hex_parts:
                hex_part = hex_part.strip()
                if hex_part:
                    # Check for US (1f) separators for DoCredit
                    if command_type == "DoCredit" and "1f" in hex_part:
                        sub_parts = hex_part.split("1f")
                        sub_packet_info = []
                        for sub_part in sub_parts:
                            if sub_part.strip():
                                converted = self._hex_to_string(sub_part.strip())
                                if converted:
                                    sub_packet_info.append(converted)
                        if sub_packet_info:
                            packet_info.append(sub_packet_info)
                    else:
                        converted = self._hex_to_string(hex_part)
                        if converted:
                            packet_info.append(converted)

            _logger.info("Parsed PAX packet info: %s", packet_info)

            return {
                'success': True,
                'packet_info': packet_info,
                'raw_response': response_text
            }

        except Exception as e:
            _logger.error("Error parsing PAX response: %s", str(e))
            return {
                'success': False,
                'error': f'Parse error: {str(e)}',
                'raw_response': response_text
            }

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
            result = self.initialize_terminal()
            if result['success']:
                message = _('Successfully connected to PAX terminal %s') % self.name
                notification_type = 'success'
            else:
                message = _('Failed to connect: %s') % result.get('message', 'Unknown error')
                notification_type = 'danger'

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Connection Test'),
                    'message': message,
                    'sticky': notification_type == 'danger',
                    'type': notification_type
                }
            }
        except Exception as e:
            _logger.error("Error testing PAX connection: %s", str(e))
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Connection Error'),
                    'message': _('Failed to test connection: %s') % str(e),
                    'sticky': True,
                    'type': 'danger'
                }
            }

    def initialize_terminal(self, version="1.28"):
        """Initialize PAX terminal exactly like JS Initialize function"""
        try:
            if self.demo_mode:
                return {
                    'success': True,
                    'message': 'Terminal initialized successfully (Demo Mode)',
                    'demo_mode': True
                }

            command = "A08"  # Initialize command like JS

            # Build params for LRC calculation exactly like JS
            params = [self.STX, command, self.FS, version, self.ETX]
            lrc = self._get_lrc(params)

            # Encode to base64 hex exactly like JS
            command_b64 = base64.b64encode(command.encode()).decode()
            command_hex = self._base64_to_hex(command_b64)

            version_b64 = base64.b64encode(version.encode()).decode()
            version_hex = self._base64_to_hex(version_b64)

            lrc_b64 = base64.b64encode(lrc.encode()).decode()
            lrc_hex = self._base64_to_hex(lrc_b64)

            # Build elements array exactly like JS
            elements = [
                format(self.STX, '02x'),  # "02"
                command_hex,
                format(self.FS, '02x'),  # "1c"
                version_hex,
                format(self.ETX, '02x'),  # "03"
                lrc_hex
            ]

            final_string = " ".join(elements)
            final_b64 = self._hex_to_base64(final_string)

            # Build URL
            url = f"http://{self.ip_address}:{self.port}?{final_b64}"

            _logger.info("PAX Initialize - LRC: %s", repr(lrc))
            _logger.info("PAX Initialize - Base64: %s", final_b64)
            _logger.info("PAX Initialize - URL: %s", url)

            result = self._send_http_command('Initialize', url, self.timeout_initialize)

            if result.get('success') and result.get('packet_info'):
                packet_info = result['packet_info']
                return {
                    'success': True,
                    'message': 'Terminal initialized successfully',
                    'packet_info': packet_info,
                    'demo_mode': False
                }
            else:
                return {
                    'success': False,
                    'message': result.get('error', 'Initialize failed'),
                    'demo_mode': False
                }

        except Exception as e:
            _logger.error("Error in initialize_terminal: %s", str(e))
            return {
                'success': False,
                'error': str(e),
                'message': 'Failed to initialize PAX terminal'
            }

    def do_credit_transaction(self, amount, transaction_type="01", reference="", **kwargs):
        """Perform credit transaction exactly like JS DoCredit function"""
        try:
            if self.demo_mode:
                result = self._simulate_transaction(amount, transaction_type, reference)
                self._log_transaction('credit', amount, result, reference)
                return result

            command = "T00"  # DoCredit command like JS
            version = "1.28"

            # Convert amount to cents
            amount_cents = str(int(float(amount) * 100))

            # Prepare information objects exactly like JS
            amount_information = {
                'TransactionAmount': amount_cents,
                'TipAmount': '',
                'CashBackAmount': '',
                'MerchantFee': '',
                'TaxAmount': '',
                'FuelAmount': ''
            }

            account_information = {
                'Account': '',
                'EXPD': '',
                'CVVCode': '',
                'EBTtype': '',
                'VoucherNumber': '',
                'Force': '',
                'FirstName': '',
                'LastName': '',
                'CountryCode': '',
                'State_ProvinceCode': '',
                'CityName': '',
                'EmailAddress': ''
            }

            trace_information = {
                'ReferenceNumber': reference or '1',
                'InvoiceNumber': '',
                'AuthCode': '',
                'TransactionNumber': '',
                'TimeStamp': '',
                'ECRTransID': ''
            }

            avs_information = {
                'ZipCode': '',
                'Address': '',
                'Address2': ''
            }

            cashier_information = {
                'ClerkID': kwargs.get('clerk_id', self.default_clerk_id or ''),
                'ShiftID': ''
            }

            commercial_information = {
                'PONumber': '',
                'CustomerCode': '',
                'TaxExempt': '',
                'TaxExemptID': '',
                'MerchantTaxID': '',
                'DestinationZipCode': '',
                'ProductDescription': ''
            }

            moto_ecommerce = {
                'MOTO_E_CommerceMode': '',
                'TransactionType': '',
                'SecureType': '',
                'OrderNumber': '',
                'Installments': '',
                'CurrentInstallment': ''
            }

            additional_information = {
                'TABLE': '',
                'GUEST': '',
                'SIGN': '',
                'TICKET': '',
                'HREF': '',
                'TIPREQ': '',
                'SIGNUPLOAD': '',
                'REPORTSTATUS': '',
                'TOKENREQUEST': '',
                'TOKEN': '',
                'CARDTYPE': '',
                'CARDTYPEBITMAP': '',
                'PASSTHRUDATA': '',
                'RETURNREASON': '',
                'ORIGTRANSDATE': '',
                'ORIGPAN': '',
                'ORIGEXPIRYDATE': '',
                'ORIGTRANSTIME': '',
                'DISPROGPROMPTS': '',
                'GATEWAYID': '',
                'GETSIGN': '',
                'ENTRYMODEBITMAP': '',
                'RECEIPTPRINT': '',
                'CPMODE': '',
                'ODOMETER': '',
                'VEHICLENO': '',
                'JOBNO': '',
                'DRIVERID': '',
                'EMPLOYEENO': '',
                'LICENSENO': '',
                'JOBID': '',
                'DEPARTMENTNO': '',
                'CUSTOMERDATA': '',
                'USERID': '',
                'VEHICLEID': ''
            }

            # Build params for LRC calculation exactly like JS DoCredit
            params = [self.STX, command, self.FS, version]
            params.append(self.FS)

            if transaction_type:
                params.append(transaction_type)

            # Add amount information using PushParams logic
            params.append(self.FS)
            params = self._push_params(params, "amountInformation", amount_information)

            params.append(self.FS)
            params = self._push_params(params, "accountInformation", account_information)

            params.append(self.FS)
            params = self._push_params(params, "traceInformation", trace_information)

            params.append(self.FS)
            params = self._push_params(params, "avsInformation", avs_information)

            params.append(self.FS)
            params = self._push_params(params, "cashierInformation", cashier_information)

            params.append(self.FS)
            params = self._push_params(params, "commercialInformation", commercial_information)

            params.append(self.FS)
            params = self._push_params(params, "motoEcommerce", moto_ecommerce)

            params.append(self.FS)
            params = self._push_params(params, "additionalInformation", additional_information)

            params.append(self.ETX)

            lrc = self._get_lrc(params)

            # Build elements exactly like JS
            command_b64 = base64.b64encode(command.encode()).decode()
            command_hex = self._base64_to_hex(command_b64)

            version_b64 = base64.b64encode(version.encode()).decode()
            version_hex = self._base64_to_hex(version_b64)

            trans_type_hex = ""
            if transaction_type:
                trans_type_b64 = base64.b64encode(transaction_type.encode()).decode()
                trans_type_hex = self._base64_to_hex(trans_type_b64)

            elements = [format(self.STX, '02x')]
            elements.append(command_hex)
            elements.append(format(self.FS, '02x'))
            elements.append(version_hex)
            elements.append(format(self.FS, '02x'))

            if trans_type_hex:
                elements.append(trans_type_hex)
            elements.append(format(self.FS, '02x'))

            # Add base64 encoded information sections
            elements = self._add_base64_section(elements, "amountInformation", amount_information)
            elements.append(format(self.FS, '02x'))

            elements = self._add_base64_section(elements, "accountInformation", account_information)
            elements.append(format(self.FS, '02x'))

            elements = self._add_base64_section(elements, "traceInformation", trace_information)
            elements.append(format(self.FS, '02x'))

            elements = self._add_base64_section(elements, "avsInformation", avs_information)
            elements.append(format(self.FS, '02x'))

            elements = self._add_base64_section(elements, "cashierInformation", cashier_information)
            elements.append(format(self.FS, '02x'))

            elements = self._add_base64_section(elements, "commercialInformation", commercial_information)
            elements.append(format(self.FS, '02x'))

            elements = self._add_base64_section(elements, "motoEcommerce", moto_ecommerce)
            elements.append(format(self.FS, '02x'))

            elements = self._add_base64_section(elements, "additionalInformation", additional_information)

            elements.append(format(self.ETX, '02x'))

            lrc_b64 = base64.b64encode(lrc.encode()).decode()
            lrc_hex = self._base64_to_hex(lrc_b64)
            elements.append(lrc_hex)

            final_string = " ".join(elements)
            final_b64 = self._hex_to_base64(final_string)

            # Build URL
            url = f"http://{self.ip_address}:{self.port}?{final_b64}"

            _logger.info("PAX DoCredit - LRC: %s", repr(lrc))
            _logger.info("PAX DoCredit - Base64: %s", final_b64)
            _logger.info("PAX DoCredit - URL: %s", url)

            result = self._send_http_command('DoCredit', url, self.timeout_credit)

            # Parse the result and convert to expected format
            if result.get('success'):
                parsed_result = self._parse_credit_response(result.get('packet_info', []))
                self._log_transaction('credit', amount, parsed_result, reference)
                return parsed_result
            else:
                error_result = {
                    'success': False,
                    'message': result.get('error', 'Transaction failed')
                }
                self._log_transaction('credit', amount, error_result, reference)
                return error_result

        except Exception as e:
            _logger.error("Error in do_credit_transaction: %s", str(e))
            error_result = {
                'success': False,
                'error': str(e),
                'message': 'Credit transaction failed'
            }
            self._log_transaction('credit', amount, error_result, reference)
            return error_result

    def _push_params(self, params, param_type, object_info):
        """Push parameters exactly like JS PushParams function"""
        empty = 0
        arr = params.copy()

        for name, value in object_info.items():
            if not value and param_type != "additionalInformation":
                arr.append(self.US)
                continue

            if param_type == "additionalInformation":
                if not value:
                    continue
                empty += 1
                arr.append(f"{name}={str(value)}")
            else:
                empty += 1
                arr.append(str(value))
            arr.append(self.US)

        arr.pop()  # Remove last US

        if empty == 0 and param_type != "additionalInformation":
            arr = params
        if empty == 0 and param_type == "additionalInformation":
            arr.append(self.FS)

        return arr

    def _add_base64_section(self, elements, section_type, object_info):
        """Add base64 encoded section exactly like JS AddBase64 function"""
        empty = 0
        arr = elements.copy()

        for name, value in object_info.items():
            if not value and section_type != "additionalInformation":
                arr.append(format(self.US, '02x'))
                continue

            if section_type == "additionalInformation":
                if not value:
                    continue
                empty += 1
                data_str = f"{name}={str(value)}"
                data_b64 = base64.b64encode(data_str.encode()).decode()
                data_hex = self._base64_to_hex(data_b64)
                arr.append(data_hex)
            else:
                empty += 1
                data_b64 = base64.b64encode(str(value).encode()).decode()
                data_hex = self._base64_to_hex(data_b64)
                arr.append(data_hex)
            arr.append(format(self.US, '02x'))

        arr.pop()  # Remove last US

        if empty == 0 and section_type != "additionalInformation":
            arr = elements
        if empty == 0 and section_type == "additionalInformation":
            arr.append(format(self.FS, '02x'))

        return arr

    def _parse_credit_response(self, packet_info):
        """Parse DoCredit response to standard format"""
        try:
            if not packet_info or len(packet_info) < 5:
                return {
                    'success': False,
                    'message': 'Invalid response format'
                }

            # Basic response structure: Status, Command, Version, ResponseCode, ResponseMessage
            status = packet_info[0] if len(packet_info) > 0 else ''
            command = packet_info[1] if len(packet_info) > 1 else ''
            version = packet_info[2] if len(packet_info) > 2 else ''
            response_code = packet_info[3] if len(packet_info) > 3 else ''
            response_message = packet_info[4] if len(packet_info) > 4 else ''

            # Check if transaction was successful
            success = response_code == '000000' or response_code == '00' or status == '01'

            result = {
                'success': success,
                'result_code': response_code,
                'result_txt': response_message,
                'message': response_message,
                'status': status,
                'command': command,
                'version': version
            }

            if success:
                # Extract additional info from remaining packet_info
                if len(packet_info) > 5:
                    # Host information might be in packet_info[5]
                    host_info = packet_info[5] if len(packet_info) > 5 else []
                    if isinstance(host_info, list) and len(host_info) > 3:
                        result['auth_code'] = host_info[2] if len(host_info) > 2 else ''
                        result['reference_number'] = host_info[3] if len(host_info) > 3 else ''

                # Account information might contain card type
                if len(packet_info) > 8:
                    account_info = packet_info[8] if len(packet_info) > 8 else []
                    if isinstance(account_info, list) and len(account_info) > 6:
                        result['card_type'] = account_info[6] if len(account_info) > 6 else 'UNKNOWN'

            return result

        except Exception as e:
            _logger.error("Error parsing credit response: %s", str(e))
            return {
                'success': False,
                'message': f'Response parsing error: {str(e)}'
            }

    def _simulate_transaction(self, amount, transaction_type, reference):
        """Simulate transaction for demo mode"""
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
                'message': 'Transaction Approved - Demo Mode',
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
                'reference': reference or 'N/A',
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
            'demo_mode': terminal.demo_mode,
            'timeout_credit': terminal.timeout_credit,
            'timeout_initialize': terminal.timeout_initialize,
            'timeout_signature': terminal.timeout_signature,
        } for terminal in terminals]