from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import datetime, timedelta

class SyncOrdersWizard(models.TransientModel):
    _name = 'tiktok.sync.orders.wizard'
    _description = 'Sync TikTok Orders Wizard'

    start_time = fields.Datetime(string='Start Time', required=True, default=lambda self: fields.Datetime.now() - timedelta(days=7))
    end_time = fields.Datetime(string='End Time', required=True, default=fields.Datetime.now)
    tiktok_shop_id = fields.Many2one('tiktok.shop', string='TikTok Shop', required=True)
    order_status = fields.Selection([
        ('UNPAID', 'Unpaid'),
        ('ON_HOLD', 'On Hold'),
        ('PARTIALLY_SHIPPING', 'Partially Shipping'),
        ('AWAITING_SHIPMENT', 'Awaiting Shipment'),
        ('AWAITING_COLLECTION', 'Awaiting Collection'),
        ('IN_TRANSIT', 'In Transit'),
        ('DELIVERED', 'Delivered'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled')
    ], string='Order Status', required=True)

    @api.model
    def default_get(self, fields):
        res = super(SyncOrdersWizard, self).default_get(fields)
        tiktok_shop = self.env['tiktok.shop'].search([], limit=1, order='id')
        if tiktok_shop:
            res['tiktok_shop_id'] = tiktok_shop.id
            res['order_status'] = tiktok_shop.order_status
        return res

    @api.constrains('start_time', 'end_time')
    def _check_dates(self):
        for wizard in self:
            if wizard.start_time > wizard.end_time:
                raise UserError(_("Start time must be before end time."))

    def action_sync_orders(self):
        self.ensure_one()
        return self.tiktok_shop_id.with_context(
            start_time=int(self.start_time.timestamp()),
            end_time=int(self.end_time.timestamp()),
            order_status=self.order_status
        ).sync_orders()