# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def action_send_zalo_message(self):
        return self.env['zalo.integration'].with_context(active_model=self._name, active_id=self.id).action_send_zalo_message()

    def action_batch_send_zalo_message(self):
        return self.env['zalo.integration'].with_context(active_model=self._name, active_ids=self.ids).action_batch_send_zalo_message()
