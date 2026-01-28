# -*- coding: utf-8 -*-
from odoo import models, fields


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    driver_id = fields.Many2one('hr.employee', string='Driver', tracking=True)
