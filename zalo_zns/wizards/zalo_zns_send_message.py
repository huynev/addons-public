# Copyright 2024 Wokwy - quochuy.software@gmail.com
import requests
import json
import re
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class ZaloZnsSendMessageWizard(models.TransientModel):
    _name = 'zalo.zns.send.message.wizard'
    _description = 'Send Zalo ZNS Message Wizard'

    template_id = fields.Many2one('zalo.zns.template', string='Template', required=True)
    recipient_phone = fields.Char(string='Recipient Phone Number', required=True)
    key_value_ids = fields.One2many('zalo.zns.send.message.key.value', 'wizard_id', string='Key-Value Pairs')
    model_id = fields.Many2one('ir.model', string='Model', required=True)
    record_id = fields.Integer(string='Record ID', required=True)

    @api.onchange('template_id')
    def _onchange_template_id(self):
        self.key_value_ids = [(5, 0, 0)]
        for kv in self.template_id.key_value_ids:
            self.key_value_ids = [(0, 0, {
                'key': kv.key,
                'model_id': kv.model_id.id,
                'field_id': kv.field_id.id,
            })]

    @api.onchange('model_id', 'record_id')
    def _onchange_model_record(self):
        if self.model_id and self.record_id:
            record = self.env[self.model_id.model].browse(self.record_id)
            for kv in self.key_value_ids:
                if kv.field_id:
                    kv.value = record[kv.field_id.name]

    def format_phone_number(self, phone):
        phone = re.sub(r'\D', '', phone)
        if phone.startswith('0'):
            phone = '84' + phone[1:]
        if not phone.startswith('84'):
            phone = '84' + phone
        return phone

    def action_send_message(self):
        config = self.env['zalo.zns.config'].get_config()
        headers = {
            'Content-Type': 'application/json',
            'access_token': config.access_token
        }

        formatted_phone = self.format_phone_number(self.recipient_phone)

        payload = {
            'phone': formatted_phone,
            'template_id': self.template_id.template_id,
            'template_data': {kv.key: kv.value for kv in self.key_value_ids}
        }

        try:
            response = requests.post(config.api_url, headers=headers, data=json.dumps(payload))
            response.raise_for_status()
            response_data = response.json()
            if response.status_code == 200 and response_data.get('error') == 0:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'message': _("Message sent successfully"),
                        'type': 'success',
                        'sticky': False,
                    }
                }
            else:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'message': response_data.get('message'),
                        'type': 'error',
                        'sticky': False,
                    }
                }
        except requests.exceptions.RequestException as e:
            raise UserError(_("Failed to send message: %s") % str(e))

class ZaloZnsSendMessageKeyValue(models.TransientModel):
    _name = 'zalo.zns.send.message.key.value'
    _description = 'Zalo ZNS Send Message Key-Value Pair'

    wizard_id = fields.Many2one('zalo.zns.send.message.wizard', string='Wizard')
    key = fields.Char(string='Key', required=True)
    model_id = fields.Many2one('ir.model', string='Model', required=True)
    field_id = fields.Many2one('ir.model.fields', string='Field', required=True)
    value = fields.Char(string='Value', compute='_compute_value', store=True)

    @api.depends('wizard_id.model_id', 'wizard_id.record_id', 'field_id')
    def _compute_value(self):
        for record in self:
            if record.wizard_id.model_id and record.wizard_id.record_id and record.field_id:
                model_record = self.env[record.wizard_id.model_id.model].browse(record.wizard_id.record_id)
                record.value = model_record[record.field_id.name]
            else:
                record.value = False