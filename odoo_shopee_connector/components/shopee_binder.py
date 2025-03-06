# -*- coding: utf-8 -*-
from odoo.addons.component.core import Component
from odoo import fields


class ShopeeModelBinder(Component):
    _name = 'shopee.binder'
    _inherit = ['base.binder']
    _external_field = 'external_id'
    _apply_on = [
        'shopee.product.template',
        'shopee.sale.order',
        'shopee.sale.order.line',
        'shopee.res.partner',
    ]

    def bind(self, external_id, binding):
        """Bind a binding record with an external ID"""
        binding.write({
            'external_id': str(external_id),  # Ensure string format
            'sync_date': fields.Datetime.now(),
        })