# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import re


class BatchSendZaloWizard(models.TransientModel):
    _name = 'zalo.batch.send.wizard'
    _description = 'Batch Send Zalo Messages'

    template_id = fields.Many2one('zalo.zns.template', string='Template', required=True)
    model = fields.Char(string='Model', required=True, readonly=True)
    field_id = fields.Many2one('ir.model.fields', string='Phone Field', domain="[('model_id.model', '=', model)]")
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

    @api.onchange('model')
    def _onchange_model(self):
        self.field_id = False
        if self.model:
            model_id = self.env['ir.model'].search([('model', '=', self.model)], limit=1)
            return {'domain': {'field_id': [
                ('model_id', '=', model_id.id),
                '|',
                ('name', 'ilike', '%phone%'),
                ('ttype', '=', 'phone')
            ]}}
        return {'domain': {'field_id': []}}

    def action_send_batch_messages(self):
        def is_valid_phone_number(phone):
            """
            Kiểm tra xem một chuỗi có phải là số điện thoại hợp lệ hay không.
            Số điện thoại hợp lệ:
            - Bắt đầu bằng '+' hoặc '0'
            - Chứa từ 9 đến 15 chữ số
            - Có thể chứa dấu '-', '.', hoặc khoảng trắng giữa các số
            """
            pattern = r'^(?:\+|0)(?:\d[ -.]?){8,14}\d$'
            return bool(re.match(pattern, phone))

        self.ensure_one()
        record_ids = [int(id) for id in self.record_ids.split(',')]
        records = self.env[self.model].browse(record_ids)

        batch = self.env['zalo.zns.batch'].create({
            'template_id': self.template_id.id,
            'origin_model': self._context.get('active_model'),
        })

        invalid_records = []
        for record in records:
            partner = record.partner_id if hasattr(record, 'partner_id') else False

            if self.field_id:
                phone = record[self.field_id.name]
                if isinstance(phone, models.BaseModel):
                    if hasattr(phone, 'phone'):
                        phone = phone.phone
                    else:
                        phone = str(phone)
            elif partner and partner.phone:
                phone = partner.phone
            elif hasattr(record, 'phone_zalo'):
                phone = record.phone_zalo
            elif hasattr(record, 'phone'):
                phone = record.phone
            else:
                phone = None

            if not phone or not is_valid_phone_number(phone):
                if hasattr(record, 'display_name'):
                    invalid_records.append(record.display_name)
                else:
                    invalid_records.append(record.name)
                continue
            elif phone:
                message_vals = {
                    'batch_id': batch.id,
                    'template_id': self.template_id.id,
                    'name': record.name,
                    'phone': phone,
                    'record_id': record.id,
                    'model_id': self.env['ir.model'].search([('model', '=', self.model)], limit=1).id,
                }
                message = self.env['zalo.zns.message'].create(message_vals)

        if invalid_records:
            invalid_records = [str(r) for r in invalid_records if r]
            # raise UserError(_("The following records do not have valid phone numbers: %s") % ", ".join(invalid_records))

        batch.action_confirm()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': _("Sent to the ZNS messaging system"),
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }