# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class ZaloIntegration(models.AbstractModel):
    _name = 'zalo.integration'
    _description = 'Zalo Integration'

    def action_send_zalo_message(self):
        return {
            'name': _('Send Zalo ZNS Message'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'zalo.send.message.wizard',
            'target': 'new',
            'context': {
                'default_model': self._name,
                'default_res_id': self.id if self else False,
                'default_partner_id': self.partner_id.id if self and hasattr(self, 'partner_id') else False,
            },
        }

    def action_batch_send_zalo_message(self):
        return {
            'name': _('Batch Send Zalo Messages'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'zalo.batch.send.wizard',
            'target': 'new',
            'context': {'active_model': self._name, 'active_ids': self.ids},
        }
