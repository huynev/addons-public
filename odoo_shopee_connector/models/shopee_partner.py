# -*- coding: utf-8 -*-
from odoo import api, fields, models

class ShopeeResPartner(models.Model):
    _name = 'shopee.res.partner'
    _inherit = 'shopee.binding'
    _inherits = {'res.partner': 'odoo_id'}
    _description = 'Shopee Partner'

    odoo_id = fields.Many2one(
        'res.partner',
        string='Partner',
        required=True,
        ondelete='cascade'
    )
    shopee_user_id = fields.Char('Shopee User ID')
    shopee_username = fields.Char('Shopee Username')

    @api.model
    def import_batch(self, backend, since_date=None):
        """Import batch from Shopee"""
        with backend.work_on(self._name) as work:
            importer = work.component(usage='batch.importer')
            return importer.run(since_date=since_date)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    shopee_bind_ids = fields.One2many(
        'shopee.res.partner',
        'odoo_id',
        string='Shopee Bindings'
    )