from odoo import api, fields, models


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    track_vendor_by_lot = fields.Boolean(related="product_id.track_vendor_by_lot")

