# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    track_vendor_by_lot = fields.Boolean(
        string='Track Vendor by Lot',
        help='If checked, vendor information will be tracked in lot/serial numbers',
    )

    @api.onchange('tracking')
    def _onchange_tracking(self):
        """Reset track_vendor_by_lot if tracking is not 'lot' or 'serial'"""
        if self.tracking not in ['lot', 'serial']:
            self.track_vendor_by_lot = False
