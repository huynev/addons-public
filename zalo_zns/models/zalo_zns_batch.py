# Copyright 2024 Wokwy - quochuy.software@gmail.com
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class ZaloZnsBatch(models.Model):
    _name = 'zalo.zns.batch'
    _description = 'Zalo ZNS Batch'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Batch Name', required=True, copy=False, readonly=True,
                       default=lambda self: _('New'))
    template_id = fields.Many2one('zalo.zns.template', string='Template', required=True)
    model_id = fields.Many2one('ir.model', string='Model')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('in_progress', 'In Progress'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', tracking=True)
    recipient_ids = fields.Many2many('res.partner', 'batch_id', string='Recipient')
    message_ids = fields.One2many('zalo.zns.message', 'batch_id', string='Messages')
    message_count = fields.Integer(string='Message Count', compute='_compute_message_count')

    @api.depends('message_ids')
    def _compute_message_count(self):
        for batch in self:
            batch.message_count = len(batch.message_ids)

    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('zalo.zns.batch') or _('New')
        batch = super(ZaloZnsBatch, self).create(vals)
        batch._create_messages()
        return batch

    def write(self, vals):
        result = super(ZaloZnsBatch, self).write(vals)
        self._create_messages()
        return result

    def _create_messages(self):
        for batch in self:
            # Delete existing messages
            # batch.message_ids.unlink()

            # Create new messages
            messages = []
            for record in batch.recipient_ids:
                if record.phone:
                    messages.append({
                        'batch_id': batch.id,
                        'template_id': batch.template_id.id,
                        'record_id': record.id,
                        'name': record.name,
                        'phone': record.phone,
                    })
            self.env['zalo.zns.message'].create(messages)

    def action_confirm(self):
        self.write({'state': 'in_progress'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_draft(self):
        self.write({'state': 'draft'})

    def action_done(self):
        if any(message.state != 'sent' for message in self.message_ids):
            raise UserError(_("Cannot mark as done. There are unsent messages in this batch."))
        self.write({'state': 'done'})

    def action_view_messages(self):
        self.ensure_one()
        return {
            'name': _('Messages'),
            'view_mode': 'tree,form',
            'res_model': 'zalo.zns.message',
            'domain': [('batch_id', '=', self.id)],
            'type': 'ir.actions.act_window',
            'context': {'default_batch_id': self.id}
        }