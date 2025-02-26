from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class MagentoWebsite(models.Model):
    _name = 'magento.website'
    _description = 'Magento Website'

    name = fields.Char(string='Name', required=True)
    code = fields.Char(string='Code', required=True)
    external_id = fields.Char(string='Magento ID', required=True)
    backend_id = fields.Many2one(
        'magento.backend',
        string='Magento Backend',
        required=True,
        ondelete='cascade'
    )
    store_ids = fields.One2many(
        'magento.store',
        'website_id',
        string='Stores'
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency'
    )
    warehouse_id = fields.Many2one(
        'stock.warehouse',
        string='Warehouse',
        help='Products will be imported in this warehouse'
    )
    active = fields.Boolean(
        string='Active',
        default=True
    )

    _sql_constraints = [
        ('magento_uniq', 'unique(backend_id, external_id)',
         'A website with the same Magento ID already exists for this backend.'),
    ]

    def import_stores(self):
        """Import all stores for this website from Magento"""
        self.ensure_one()
        try:
            client = self.backend_id._get_magento_client()
            stores = client.get_stores(self.external_id)

            for store_data in stores:
                store_id = store_data.get('id')
                store_code = store_data.get('code')
                store_name = store_data.get('name')

                # Search for existing store
                store = self.env['magento.store'].search([
                    ('website_id', '=', self.id),
                    ('external_id', '=', store_id)
                ], limit=1)

                if store:
                    # Update existing store
                    store.write({
                        'code': store_code,
                        'name': store_name,
                    })
                else:
                    # Create new store
                    self.env['magento.store'].create({
                        'website_id': self.id,
                        'external_id': store_id,
                        'code': store_code,
                        'name': store_name,
                    })

            # Import storeviews for each store
            for store in self.store_ids:
                store.import_storeviews()

            _logger.info(f"Successfully imported {len(stores)} stores for website {self.name}")
            return True

        except Exception as e:
            _logger.error(f"Failed to import stores for website {self.name}: {str(e)}")
            raise UserError(f"Failed to import stores: {str(e)}")