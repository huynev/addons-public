# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class BatchSendZaloWizard(models.TransientModel):
    _name = 'zalo.batch.send.wizard'
    _description = 'Batch Send Zalo Messages'

    template_id = fields.Many2one('zalo.zns.template', string='Template', required=True)
    model = fields.Char(string='Model', required=True)
    record_ids = fields.Char(string='Record IDs', required=True)

    @api.model
    def default_get(self, fields):
        res = super(BatchSendZaloWizard, self).default_get(fields)
        active_model = self._context.get('active_model')
        active_ids = self._context.get('active_ids')
        if active_model and active_ids:
            res.update({
                'model': active_model,
                'record_ids': ','.join(map(str, active_ids))
            })
        return res

    def action_send_batch_messages(self):
        self.ensure_one()
        record_ids = [int(id) for id in self.record_ids.split(',')]
        records = self.env[self.model].browse(record_ids)

        batch = self.env['zalo.zns.batch'].create({
            'name': f"Batch {fields.Datetime.now()}",
            'template_id': self.template_id.id,
            'model_id': self.env['ir.model'].search([('model', '=', self.model)], limit=1).id,
        })

        for record in records:
            partner = record.partner_id if hasattr(record, 'partner_id') else False
            if not partner or not partner.phone:
                raise UserError(_("Partner or phone number missing for record: %s") % record.display_name)

            message_vals = {
                'batch_id': batch.id,
                'template_id': self.template_id.id,
                'name': partner.name,
                'phone': partner.phone,
                'record_id': record.id,
            }

            message = self.env['zalo.zns.message'].create(message_vals)

        batch.action_confirm()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Zalo ZNS Batch'),
            'res_model': 'zalo.zns.batch',
            'res_id': batch.id,
            'view_mode': 'form',
            'target': 'current',
        }