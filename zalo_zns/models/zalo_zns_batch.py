# Copyright 2024 Wokwy - quochuy.software@gmail.com
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import date

class ZaloZnsBatch(models.Model):
    _name = 'zalo.zns.batch'
    _description = 'Zalo ZNS Batch'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Batch Number', required=True, copy=False, readonly=True, default='/')
    template_id = fields.Many2one('zalo.zns.template', string='Template', required=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('in_progress', 'In Progress'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', tracking=True)
    recipient_ids = fields.Many2many('res.partner', 'batch_id', string='Recipient')
    message_ids = fields.One2many('zalo.zns.message', 'batch_id', string='Messages')
    message_count = fields.Integer(string='Message Count', compute='_compute_message_count')
    origin_model = fields.Char(string='Origin Model', readonly=True)

    @api.depends('message_ids')
    def _compute_message_count(self):
        for batch in self:
            batch.message_count = len(batch.message_ids)

    @api.model
    def create(self, vals):
        if vals.get('name', '/') == '/':
            today = date.today()
            origin_model = vals.get('origin_model') or self._name
            vals['name'] = self._generate_unique_name(today, origin_model)
        return super(ZaloZnsBatch, self).create(vals)

    def _generate_unique_name(self, date, model_name):
        sequence = self.env['ir.sequence'].with_context(ir_sequence_date=date)
        model_short_name = model_name.split('.')[-1].upper()
        prefix = f"ZNS/{model_short_name}/"
        year = date.strftime('%Y')
        month = date.strftime('%m')
        day = date.strftime('%d')
        suffix = sequence.next_by_code('zalo.zns.batch')[-4:]  # Lấy 4 số cuối của sequence
        return f"{prefix}{year}/{month}/{day}/{suffix}"

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