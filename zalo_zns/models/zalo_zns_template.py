# Copyright 2024 Wokwy - quochuy.software@gmail.com
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class ZaloZnsTemplate(models.Model):
    _name = 'zalo.zns.template'
    _description = 'Zalo ZNS Template'

    name = fields.Char(string='Template Name', required=True)
    template_id = fields.Char(string='Template ID', required=True)
    description = fields.Text(string='Description')
    key_value_ids = fields.One2many('zalo.zns.template.key.value', 'template_id', string='Key-Value Pairs')

    def action_send_message(self):
        return {
            'name': _('Send Zalo ZNS Message'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'zalo.zns.send.message.wizard',
            'target': 'new',
            'context': {'default_template_id': self.id},
        }

class ZaloZnsTemplateKeyValue(models.Model):
    _name = 'zalo.zns.template.key.value'
    _description = 'Zalo ZNS Template Key-Value Pair'

    template_id = fields.Many2one('zalo.zns.template', string='Template', required=True, ondelete='cascade')
    key = fields.Char(string='Key', required=True)
    value = fields.Char(string='Value')
    model_id = fields.Many2one('ir.model', string='Model')
    field_id = fields.Many2one('ir.model.fields', string='Field')

    @api.onchange('model_id')
    def _onchange_model_id(self):
        self.field_id = False

    @api.onchange('field_id')
    def _onchange_field_id(self):
        if self.field_id:
            model = self.env[self.field_id.model]
            record = model.search([], limit=1)
            if record:
                self.value = record[self.field_id.name]