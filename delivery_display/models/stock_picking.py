# -*- coding: utf-8 -*-
from odoo import models, fields, api


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    driver_id = fields.Many2one('res.partner', string='Driver', tracking=True)
    delivery_route_id = fields.Many2one('stock.route', string='Delivery Route', tracking=True)
    shipping_weight = fields.Float('Shipping Weight', compute='_compute_shipping_weight', store=True)

    @api.depends('move_ids.product_id', 'move_ids.product_uom_qty')
    def _compute_shipping_weight(self):
        for picking in self:
            total_weight = 0
            for move in picking.move_ids:
                if move.product_id.weight:
                    total_weight += move.product_id.weight * move.product_uom_qty
            picking.shipping_weight = total_weight
