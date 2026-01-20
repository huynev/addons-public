# -*- coding: utf-8 -*-

from odoo import models, fields


class StockLot(models.Model):
    _inherit = 'stock.lot'

    partner_id = fields.Many2one(
        'res.partner',
        string='Vendor',
        help='Vendor associated with this lot/serial number',
        index=True,
    )
