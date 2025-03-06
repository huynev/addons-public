from odoo import api, fields, models
from datetime import datetime, timedelta

class ShopeeImportProductsWizard(models.TransientModel):
    _name = 'shopee.import.products.wizard'
    _description = 'Import Products from Shopee'

    backend_id = fields.Many2one(
        'shopee.backend',
        'Shopee Backend',
        required=True,
        default=lambda self: self.env['shopee.backend'].search([], limit=1)
    )
    from_date = fields.Datetime(
        string='From Date',
        default=lambda self: datetime.now() - timedelta(days=7),
    )
    to_date = fields.Datetime(
        string='To Date',
        default=lambda self: datetime.now(),
    )

    def import_products(self):
        """Import products from Shopee"""
        self.ensure_one()
        self.backend_id.import_products_since(self.from_date)
        return {'type': 'ir.actions.act_window_close'}