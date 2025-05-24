# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import json
import logging
import socket
import xml.etree.ElementTree as ET
from datetime import datetime

_logger = logging.getLogger(__name__)


class PaxTerminal(models.Model):
    _name = 'pax.terminal'
    _inherit = ['pos.load.mixin']
    _description = 'PAX Terminal Configuration'

    name = fields.Char('Terminal Name', required=True)
    ip_address = fields.Char('IP Address', required=True, default='192.168.1.100')
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
    timeout = fields.Integer('Timeout (seconds)', default=30,
                             help='Timeout for PAX terminal communication')

    # PAX Protocol Settings
    protocol_type = fields.Selection([
        ('tcp', 'TCP/IP'),
        ('http', 'HTTP'),
        ('https', 'HTTPS'),
        ('ssl', 'SSL/TLS'),
    ], string='Protocol Type', default='tcp', required=True,
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
            'timeout', 'demo_mode', 'demo_success_rate',
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
            # Test TCP socket connection first
            test_result = self._test_tcp_connection()
            if test_result['success']:
                # Try to send a simple status command
                status_result = self._send_status_command()
                if status_result['success']:
                    message = _('Successfully connected to PAX terminal %s and received status') % self.name
                else:
                    message = _('Connected to PAX terminal %s but no response to status command') % self.name
            else:
                raise Exception(test_result['error'])

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

    def _test_tcp_connection(self):
        """Test basic TCP connection to terminal"""
        try:
            with socket.create_connection((self.ip_address, self.port), timeout=5) as sock:
                _logger.info("TCP connection to PAX terminal %s successful", self.name)
                return {'success': True}
        except Exception as e:
            _logger.error("TCP connection failed: %s", str(e))
            return {'success': False, 'error': str(e)}

    def _send_status_command(self):
        """Send a simple status command to test PAX terminal communication"""
        try:
            # Create a simple status XML command
            xml_command = '''<?xml version="1.0"?>
<Transaction>
    <Command>A00</Command>
    <Version>1.28</Version>
    <Timeout>5000</Timeout>
</Transaction>'''

            # Send command via TCP socket
            response = self._send_tcp_command(xml_command, timeout=5)

            if response:
                _logger.info("Received response from PAX terminal: %s", response[:100])
                return {'success': True, 'response': response}
            else:
                return {'success': False, 'error': 'No response received'}

        except Exception as e:
            _logger.error("Error sending status command: %s", str(e))
            return {'success': False, 'error': str(e)}

    def _send_tcp_command(self, xml_command, timeout=30):
        """Send XML command to PAX terminal via TCP socket"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(timeout)
                sock.connect((self.ip_address, self.port))

                # Send XML command
                sock.sendall(xml_command.encode('utf-8'))

                # Receive response
                response = sock.recv(4096).decode('utf-8')
                return response

        except socket.timeout:
            raise Exception("Terminal connection timeout")
        except socket.error as e:
            raise Exception(f"Socket error: {str(e)}")
        except Exception as e:
            raise Exception(f"Communication failed: {str(e)}")

    @api.model
    def create_xml_command(self, command_type, **kwargs):
        """Create XML command for PAX terminal"""
        xml_data = {
            'command': command_type,
            'version': '1.28',
            'timeout': str(kwargs.get('timeout', 30000)),
        }

        # Add specific parameters based on command type
        if command_type == 'T00':  # DoCredit
            xml_data.update({
                'amount': kwargs.get('amount', '0'),
                'trantype': kwargs.get('transaction_type', '01'),
                'invnum': kwargs.get('reference', '1'),
                'clerkid': kwargs.get('clerk_id', ''),
            })
        elif command_type == 'T02':  # DoDebit
            xml_data.update({
                'amount': kwargs.get('amount', '0'),
                'trantype': kwargs.get('transaction_type', '01'),
                'invnum': kwargs.get('reference', '1'),
                'clerkid': kwargs.get('clerk_id', ''),
            })

        # Build XML string
        xml_lines = ['<?xml version="1.0"?>', '<Transaction>']

        for key, value in xml_data.items():
            if value:  # Only include non-empty values
                tag_name = key.title().replace('_', '')
                xml_lines.append(f'    <{tag_name}>{value}</{tag_name}>')

        xml_lines.append('</Transaction>')

        return '\n'.join(xml_lines)

    @api.model
    def parse_xml_response(self, xml_response):
        """Parse XML response from PAX terminal"""
        try:
            root = ET.fromstring(xml_response)

            result = {
                'result_code': self._get_xml_text(root, 'ResultCode'),
                'result_txt': self._get_xml_text(root, 'ResultTxt'),
                'auth_code': self._get_xml_text(root, 'AuthCode'),
                'reference_number': self._get_xml_text(root, 'RefNum'),
                'transaction_id': self._get_xml_text(root, 'TransID'),
                'card_type': self._get_xml_text(root, 'CardType'),
                'card_number': self._get_xml_text(root, 'CardNumber'),
                'message': self._get_xml_text(root, 'Message'),
                'receipt': self._get_xml_text(root, 'Receipt'),
            }

            # Determine if transaction was successful
            result['success'] = result['result_code'] == '000000'

            return result

        except ET.ParseError as e:
            _logger.error("XML Parse error: %s", str(e))
            return {
                'success': False,
                'result_code': 'XML_ERROR',
                'result_txt': f'Invalid XML response: {str(e)}',
                'message': 'Failed to parse terminal response'
            }
        except Exception as e:
            _logger.error("Error parsing PAX response: %s", str(e))
            return {
                'success': False,
                'result_code': 'PARSE_ERROR',
                'result_txt': f'Response parsing failed: {str(e)}',
                'message': 'Failed to process terminal response'
            }

    def _get_xml_text(self, root, tag_name):
        """Helper to safely get text from XML element"""
        element = root.find(tag_name)
        return element.text if element is not None else ''