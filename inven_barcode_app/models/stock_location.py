# -*- coding: utf-8 -*-

from odoo import models

class StockLocation(models.Model):
    _inherit = 'stock.location'
    _barcode_field = 'barcode'
