# Copyright 2024 Wokwy - quochuy.software@gmail.com
from odoo import models, fields, api
import requests
import json
import re

class ZaloZnsMessage(models.Model):
    _name = 'zalo.zns.message'
    _description = 'Zalo ZNS Message'
    _inherit = ['mail.thread']

    batch_id = fields.Many2one('zalo.zns.batch', string='Batch', ondelete='set null', required=False, readonly=True)
    template_id = fields.Many2one('zalo.zns.template', string='Template', related='batch_id.template_id', readonly=True)
    name = fields.Char(string='Name')
    record_id = fields.Integer(string='Record ID')
    zalo_user_id_zalo = fields.Char(string="User ID zalo")
    zalo_msg_id = fields.Char(string='Zalo Message ID', readonly=True)
    zalo_msg_str = fields.Char(string='Zalo message', readonly=True)
    phone = fields.Char(string='Phone', readonly=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('sent', 'Sent'),
        ('done', 'Done'),
        ('failed', 'Failed')
    ], string='State', default='draft', tracking=True)
    error_message = fields.Text(string='Error Message')
    message_ids = fields.Many2many('mail.message', 'zalo_zns_message_mail_message_rel', 'zalo_message_id', 'mail_message_id', string='Messages')
    message_type = fields.Selection([('dummy', 'Dummy')], default='dummy', string='Message Type')

    def format_phone_number(self, phone):
        phone = re.sub(r'\D', '', phone)
        if phone.startswith('0'):
            phone = '84' + phone[1:]
        if not phone.startswith('84'):
            phone = '84' + phone
        return phone

    def action_send_message_zalo_zns(self):
        config = self.env['zalo.zns.config'].get_config()
        if not config:
            return

        headers = {
            "access_token": config.access_token,
            "Content-Type": "application/json"
        }

        for message in self:
            template = message.template_id
            key_value_pairs = template.key_value_ids

            template_data = {}
            for kv in key_value_pairs:
                if kv.model_id and kv.field_id:
                    related_record = self.env[message.batch_id.model_id.model].browse(message.record_id)
                    value = related_record[kv.field_id.name]

                    # Xử lý trường hợp value là một recordset
                    if isinstance(value, models.BaseModel):
                        if hasattr(value, 'name'):
                            value = value.name
                        elif hasattr(value, 'display_name'):
                            value = value.display_name
                        else:
                            value = str(value)
                    elif isinstance(value, (int, float)):
                        value = str(value)
                    elif value is False:
                        value = ''
                else:
                    value = kv.value

                template_data[kv.key] = value

            payload = {
                'phone': self.format_phone_number(message.phone),
                'template_id': message.template_id.template_id,
                'template_data': template_data
            }

            try:
                response = requests.post(config.api_url, headers=headers, data=json.dumps(payload))
                response.raise_for_status()
                response_data = response.json()

                if response_data.get('error') == 0:
                    message.zalo_msg_id = response_data['data']['msg_id']
                    message.state = 'sent'
                else:
                    message.state = 'failed'
                    message.error_message = response_data.get('message', 'Unknown error')

            except requests.exceptions.RequestException as e:
                message.state = 'failed'
                message.error_message = str(e)

    def action_update_status_send_zns_from_zalo(self):
        config = self.env['zalo.zns.config'].get_config()
        if not config:
            return

        headers = {
            "access_token": config.access_token,
            "Content-Type": "application/json"
        }

        for message in self:
            zalo_api_url = f"https://business.openapi.zalo.me/message/status?message_id={message.zalo_msg_id}&phone={message.phone}"
            try:
                response = requests.get(zalo_api_url, headers=headers)
                response.raise_for_status()
                response_data = response.json()

                if response_data.get('error') == 0:
                    message.state = 'done'
                else:
                    message.state = 'failed'
                    message.error_message = response_data.get('message', 'Unknown error')

            except requests.exceptions.RequestException as e:
                message.state = 'failed'
                message.error_message = str(e)

    @api.model
    def _cron_send_messages_zalo_zns(self):
        messages = self.search([('state', '=', 'draft')])
        messages.action_send_message_zalo_zns()

    @api.model
    def _cron_update_status_send_zns_from_zalo(self):
        messages = self.search([('zalo_msg_id', '!=', '')])
        messages.action_update_status_send_zns_from_zalo()