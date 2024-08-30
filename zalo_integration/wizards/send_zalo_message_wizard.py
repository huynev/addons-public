# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class SendZaloMessageWizard(models.TransientModel):
    _name = 'zalo.send.message.wizard'
    _description = 'Send Zalo Message Wizard'

    template_id = fields.Many2one('zalo.zns.template', string='Template', required=True)
    batch_id = fields.Many2one('zalo.zns.batch', string='Batch')

    def action_send_message(self):
        self.ensure_one()
        active_model = self._context.get('active_model')
        active_id = self._context.get('active_id')
        if active_model and active_id:
            record = self.env[active_model].browse(active_id)
            if not hasattr(record, 'partner_id'):
                raise UserError(_("Please provide either a partner"))

            phone = record.partner_id.phone
            if not phone:
                raise UserError(_("No phone number provided for sending the message."))

            message_vals = {
                'template_id': self.template_id.id,
                'name': record.partner_id.name,
                'phone': phone,
                'record_id': self._context.get('active_id'),
                'batch_id': self.batch_id.id if self.batch_id else False,
            }

            message = self.env['zalo.zns.message'].create(message_vals)
            message.action_send_message_zalo_zns()

        return {'type': 'ir.actions.act_window_close'}