from odoo.addons.component.core import Component
from odoo import fields
import logging

_logger = logging.getLogger(__name__)


class MagentoProductImporter(Component):
    _name = 'magento.product.importer'
    _inherit = ['magento.importer']
    _apply_on = ['magento.product.template', 'magento.product.product']

    def _get_magento_data(self, store_id, filters=None):
        """Get product data from Magento for a specific store"""
        store = self.env['magento.store'].browse(store_id)
        client = store.backend_id._get_magento_client()

        # Default page and limit
        page = 1
        limit = 100

        all_products = []

        while True:
            products = client.get_products(filters, page, limit)
            items = products.get('items', [])

            if not items:
                break

            all_products.extend(items)

            # Check if we've reached the end
            total_count = products.get('total_count', 0)
            if len(all_products) >= total_count:
                break

            # Move to next page
            page += 1

        return all_products

    def run(self, store_id, filters=None):
        """Run the synchronization for a specific store"""
        store = self.env['magento.store'].browse(store_id)

        products = self._get_magento_data(store_id, filters)

        if not products:
            _logger.info(f"No products found for store {store.name}")
            return

        _logger.info(f"Found {len(products)} products for store {store.name}")

        for product_data in products:
            self.env['magento.product.importer.record'].with_delay(
                channel='root.magento.product'
            ).run(store_id, product_data)

        return True


class MagentoProductImporterRecord(Component):
    _name = 'magento.product.importer.record'
    _inherit = ['magento.importer']
    _apply_on = ['magento.product.template', 'magento.product.product']

    def run(self, store_id, product_data):
        """Import a single product from Magento data"""
        store = self.env['magento.store'].browse(store_id)
        backend = store.backend_id

        sku = product_data.get('sku')
        if not sku:
            _logger.warning("Skipping product import: No SKU found in product data")
            return

        # Check if product exists in Odoo
        binding = self.env['magento.product.template'].search([
            ('backend_id', '=', backend.id),
            ('magento_sku', '=', sku)
        ], limit=1)

        values = self._map_product_data(store, product_data)

        if binding:
            # Update existing product
            binding.write(values)
            _logger.info(f"Updated product {sku} in Odoo")
        else:
            # Create new product
            odoo_product = self._create_product_in_odoo(store, product_data)

            if odoo_product:
                values.update({
                    'odoo_id': odoo_product.id,
                    'backend_id': backend.id,
                    'magento_sku': sku,
                    'external_id': product_data.get('id'),
                })
                binding = self.env['magento.product.template'].create(values)
                _logger.info(f"Created product {sku} in Odoo")

        # Add product to store's website
        if binding and store.website_id:
            binding.magento_website_ids = [(4, store.website_id.id)]

        return binding

    def _map_product_data(self, store, product_data):
        """Map Magento product data to Odoo product values"""
        return {
            'sync_date': fields.Datetime.now(),
            'sync_status': 'synced',
            'url_key': product_data.get('custom_attributes', {}).get('url_key', ''),
        }

    def _create_product_in_odoo(self, store, product_data):
        """Create a new product in Odoo from Magento data"""
        # Extract data
        name = product_data.get('name', '')
        sku = product_data.get('sku', '')
        price = float(product_data.get('price', 0.0))

        # Handle custom attributes
        custom_attributes = {}
        for attribute in product_data.get('custom_attributes', []):
            custom_attributes[attribute.get('attribute_code')] = attribute.get('value')

        # Extract description and short description
        description = custom_attributes.get('description', '')
        short_description = custom_attributes.get('short_description', '')

        # Create product
        values = {
            'name': name,
            'default_code': sku,
            'list_price': price,
            'description': description,
            'description_sale': short_description,
            'type': 'product',  # Storable product
            'categ_id': store.default_category_id.id if store.default_category_id else 1,  # Default category
        }

        try:
            product = self.env['product.template'].create(values)
            return product
        except Exception as e:
            _logger.error(f"Error creating product {sku}: {str(e)}")
            return None