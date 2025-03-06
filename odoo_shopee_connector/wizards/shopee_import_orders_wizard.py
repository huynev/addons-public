from odoo import api, fields, models
from datetime import datetime, timedelta

class ShopeeImportOrdersWizard(models.TransientModel):
    _name = 'shopee.import.orders.wizard'
    _description = 'Import Orders from Shopee'

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
    status = fields.Selection([
        ('UNPAID', 'Unpaid'),
        ('READY_TO_SHIP', 'Ready to Ship'),
        ('SHIPPED', 'Shipped'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
        ('INVOICE_PENDING', 'Invoice Pending'),
        ('ALL', 'All Statuses'),
    ], string='Order Status', default='ALL')

    def import_orders(self):
        """Import orders from Shopee"""
        self.ensure_one()
        self.backend_id.import_orders_batch(self.from_date)
        # Update last import date on backend
        self.backend_id.write({'import_orders_from_date': self.to_date})
        return {'type': 'ir.actions.act_window_close'}