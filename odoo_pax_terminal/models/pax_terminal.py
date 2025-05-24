# -------- models/pax_terminal.py (Fixed inheritance issue) --------

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import requests
import json
import logging
import base64
import socket
from datetime import datetime

_logger = logging.getLogger(__name__)


class PaxTerminal(models.Model):
    _name = 'pax.terminal'
    _inherit = ['pos.load.mixin']
    _description = 'PAX Terminal Configuration'

    name = fields.Char('Terminal Name', required=True)
    ip_address = fields.Char('IP Address', required=True, default='127.0.0.1')
    port = fields.Integer('Port', required=True, default=10009)
    active = fields.Boolean('Active', default=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    payment_method_ids = fields.One2many('pos.payment.method', 'pax_terminal_id', string='Payment Methods')
    transaction_log_ids = fields.One2many('pax.transaction.log', 'terminal_id', string='Transaction Logs')

    # Add pos_config_ids to link terminals to specific POS configurations
    pos_config_ids = fields.Many2many('pos.config', string='Point of Sale Configurations',
                                      help='POS configurations that can use this terminal')

    timeout = fields.Integer('Timeout (seconds)', default=120,
                             help='Timeout for PAX terminal communication')

    # Demo Mode
    demo_mode = fields.Boolean('Demo Mode', default=False,
                               help='Enable demo mode for testing without real PAX terminal')
    demo_success_rate = fields.Float('Demo Success Rate (%)', default=90.0,
                                     help='Success rate for demo transactions (0-100%)')

    # Optional settings for default values
    default_clerk_id = fields.Char('Default Clerk ID', help='Default clerk ID for transactions')
    default_reference_prefix = fields.Char('Default Reference Prefix',
                                           help='Prefix for reference numbers')

    @api.model
    def _load_pos_data_domain(self, data):
        """Define which PAX terminals should be loaded for this POS session"""
        config_id = self.env['pos.config'].browse(data['pos.config']['data'][0]['id'])

        # Load terminals that are:
        # 1. Active
        # 2. Belong to the same company as the POS config
        # 3. Either have no specific POS config assigned (available to all) or are assigned to this POS config
        domain = [
            ('active', '=', True),
            ('company_id', '=', config_id.company_id.id),
            '|',
            ('pos_config_ids', '=', False),  # No specific POS config (available to all)
            ('pos_config_ids', 'in', [config_id.id])  # Assigned to this POS config
        ]
        return domain

    @api.model
    def _load_pos_data_fields(self, config_id):
        """Define which fields should be loaded in POS"""
        return [
            'name', 'ip_address', 'port', 'active', 'company_id',
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
            with socket.create_connection((self.ip_address, self.port), timeout=5) as sock:
                pass

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _('Successfully connected to PAX terminal %s') % self.name,
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
                    'title': _('Error'),
                    'message': _('Failed to connect to PAX terminal: %s\n\nTip: Enable Demo Mode for testing') % str(e),
                    'sticky': True,
                    'type': 'danger'
                }
            }