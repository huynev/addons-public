from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class MagentoImportOrdersWizard(models.TransientModel):
    _name = 'magento.import.orders.wizard'
    _description = 'Import Orders from Magento'

    backend_id = fields.Many2one(
        'magento.backend',
        string='Magento Backend',
        required=True,
    )
    website_id = fields.Many2one(
        'magento.website',
        string='Website',
        domain="[('backend_id', '=', backend_id)]"
    )
    store_id = fields.Many2one(
        'magento.store',
        string='Store',
        domain="[('website_id', '=', website_id)]"
    )
    from_date = fields.Datetime(
        string='From Date',
        help='Import orders created after this date',
    )

    @api.onchange('backend_id')
    def onchange_backend_id(self):
        if self.backend_id:
            self.from_date = self.backend_id.import_orders_from_date
            self.website_id = False
            self.store_id = False

    @api.onchange('website_id')
    def onchange_website_id(self):
        if self.website_id:
            self.store_id = False

    def import_orders(self):
        """Launch the order import"""
        self.ensure_one()

        filters = []
        if self.from_date:
            # Add date filter
            filters.append(('created_at', 'gt', self.from_date.isoformat()))

        if self.store_id:
            # Import orders from a specific store
            self.store_id.with_delay(
                channel='root.magento.sale'
            ).import_orders()
        elif self.website_id:
            # Import orders from all stores in a website
            for store in self.website_id.store_ids:
                store.with_delay(
                    channel='root.magento.sale'
                ).import_orders()
        else:
            # Import orders from all stores
            self.backend_id.import_orders()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Orders Import'),
                'message': _('Orders import started. You will be notified when it is done.'),
                'sticky': False,
            }
        }