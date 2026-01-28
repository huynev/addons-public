# -*- coding: utf-8 -*-
from odoo import models, fields


class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_driver = fields.Boolean(
        string='Is Driver',
        default=False,
        help='Check this if this partner is a delivery driver'
    )
