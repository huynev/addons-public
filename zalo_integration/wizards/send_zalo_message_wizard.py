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
            if hasattr(record, 'partner_id'):
                phone = record.partner_id.phone
            elif hasattr(record, 'phone_zalo'):
                phone = record.phone_zalo
            elif hasattr(record, 'phone'):
                phone = record.phone
            else:
                phone = None

            if not phone:
                raise UserError(_("No phone number provided for sending the message."))

            message_vals = {
                'template_id': self.template_id.id,
                'name': record.name,
                'phone': phone,
                'record_id': self._context.get('active_id'),
                'batch_id': self.batch_id.id if self.batch_id else False,
                'model_id': self.env['ir.model'].search([('model', '=', active_model)], limit=1).id,
            }

            try:
                message = self.env['zalo.zns.message'].create(message_vals)
                message.action_send_message_zalo_zns()

                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'message': _("Đã gửi đến hệ thống gửi tin ZNS"),
                        'type': 'success',
                        'sticky': False,
                        'next': {'type': 'ir.actions.act_window_close'},
                    }
                }
            except Exception as e:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'message': _("Error sending message: %s") % str(e),
                        'type': 'danger',
                        'sticky': True,
                        'next': {'type': 'ir.actions.act_window_close'},
                    }
                }

        return {'type': 'ir.actions.act_window_close'}