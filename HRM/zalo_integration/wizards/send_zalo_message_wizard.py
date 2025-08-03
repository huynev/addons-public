# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import re

class SendZaloMessageWizard(models.TransientModel):
    _name = 'zalo.send.message.wizard'
    _description = 'Send Zalo Message Wizard'

    template_id = fields.Many2one('zalo.zns.template', string='Template', required=True)
    batch_id = fields.Many2one('zalo.zns.batch', string='Batch')
    model = fields.Char(string='Model', required=True, readonly=True)
    field_id = fields.Many2one('ir.model.fields', string='Phone Field', domain="[('model_id.model', '=', model)]")

    @api.model
    def default_get(self, fields_list):
        res = super(SendZaloMessageWizard, self).default_get(fields_list)
        active_model = self._context.get('active_model')
        if active_model:
            res['model'] = active_model
        return res

    def action_send_message(self):
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
        active_model = self._context.get('active_model')
        active_id = self._context.get('active_id')
        if active_model and active_id:
            record = self.env[active_model].browse(active_id)

            if self.field_id:
                phone = record[self.field_id.name]
                if isinstance(phone, models.BaseModel):
                    if hasattr(phone, 'phone'):
                        phone = phone.phone
                    else:
                        phone = str(phone)
            elif hasattr(record, 'partner_id'):
                phone = record.partner_id.phone
            elif hasattr(record, 'phone_zalo'):
                phone = record.phone_zalo
            elif hasattr(record, 'phone'):
                phone = record.phone
            else:
                phone = None

            if not phone:
                raise UserError(_("No phone number provided for sending the message."))
            elif not is_valid_phone_number(phone):
                raise UserError(_("The provided phone number is not valid."))

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
                        'message': _("Sent to the ZNS messaging system"),
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