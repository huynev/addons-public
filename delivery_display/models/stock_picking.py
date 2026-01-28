# -*- coding: utf-8 -*-
from odoo import models, fields, _
from odoo.exceptions import UserError


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    driver_id = fields.Many2one('hr.employee', string='Driver', tracking=True)