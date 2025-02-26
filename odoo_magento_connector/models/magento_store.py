from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class MagentoStore(models.Model):
    _name = 'magento.store'
    _description = 'Magento Store'

    name = fields.Char(string='Name', required=True)
    code = fields.Char(string='Code', required=True)
    external_id = fields.Char(string='Magento ID', required=True)
    website_id = fields.Many2one(
        'magento.website',
        string='Magento Website',
        required=True,
        ondelete='cascade'
    )
    backend_id = fields.Many2one(
        'magento.backend',
        string='Magento Backend',
        related='website_id.backend_id',
        store=True,
        readonly=True
    )
    storeview_ids = fields.One2many(
        'magento.storeview',
        'store_id',
        string='Store Views'
    )
    pricelist_id = fields.Many2one(
        'product.pricelist',
        string='Pricelist',
        help='Pricelist used for sales from this store'
    )
    default_category_id = fields.Many2one(
        'product.category',
        string='Default Category',
        help='Default category for products imported from this store'
    )
    team_id = fields.Many2one(
        'crm.team',
        string='Sales Team',
        help='Sales team for orders from this store'
    )
    active = fields.Boolean(
        string='Active',
        default=True
    )

    _sql_constraints = [
        ('magento_uniq', 'unique(website_id, external_id)',
         'A store with the same Magento ID already exists for this website.'),
    ]

    def import_storeviews(self):
        """Import all storeviews for this store from Magento"""
        self.ensure_one()
        try:
            client = self.backend_id._get_magento_client()
            storeviews = client.get_store_views(self.external_id)

            for storeview_data in storeviews:
                storeview_id = storeview_data.get('id')
                storeview_code = storeview_data.get('code')
                storeview_name = storeview_data.get('name')

                # Search for existing storeview
                storeview = self.env['magento.storeview'].search([
                    ('store_id', '=', self.id),
                    ('external_id', '=', storeview_id)
                ], limit=1)

                if storeview:
                    # Update existing storeview
                    storeview.write({
                        'code': storeview_code,
                        'name': storeview_name,
                    })
                else:
                    # Create new storeview
                    self.env['magento.storeview'].create({
                        'store_id': self.id,
                        'external_id': storeview_id,
                        'code': storeview_code,
                        'name': storeview_name,
                    })

            _logger.info(f"Successfully imported {len(storeviews)} storeviews for store {self.name}")
            return True

        except Exception as e:
            _logger.error(f"Failed to import storeviews for store {self.name}: {str(e)}")
            raise UserError(f"Failed to import storeviews: {str(e)}")

    def import_products(self):
        """Import products for this store from Magento"""
        self.ensure_one()
        from_date = self.backend_id.import_products_from_date

        filters = []
        if from_date:
            # Add date filter if specified
            filters.append(('updated_at', 'gt', from_date.isoformat()))

        self.env['magento.product.importer'].with_delay(
            channel='root.magento.product'
        ).run(self.id, filters=filters)

        # Update the last import date
        self.backend_id.import_products_from_date = fields.Datetime.now()

        return True

    def import_orders(self):
        """Import orders for this store from Magento"""
        self.ensure_one()
        from_date = self.backend_id.import_orders_from_date

        filters = []
        if from_date:
            # Add date filter if specified
            filters.append(('created_at', 'gt', from_date.isoformat()))

        self.env['magento.sale.order.importer'].with_delay(
            channel='root.magento.sale'
        ).run(self.id, filters=filters)

        # Update the last import date
        self.backend_id.import_orders_from_date = fields.Datetime.now()

        return True