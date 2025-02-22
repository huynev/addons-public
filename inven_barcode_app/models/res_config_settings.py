# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    stock_confirm_image = fields.Boolean(
        related='company_id.stock_confirm_image',
        string='Take image when done stock picking', readonly=False)
    stock_confirm_image_count = fields.Integer(
        related='company_id.stock_confirm_image_count',
        string='Number of image need taken when done stock picking', readonly=False)
