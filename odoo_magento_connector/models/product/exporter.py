from odoo.addons.component.core import Component
from odoo import fields
import logging

_logger = logging.getLogger(__name__)


class MagentoProductExporter(Component):
    _name = 'magento.product.exporter'
    _inherit = ['magento.exporter']
    _apply_on = ['magento.product.template']

    def _has_to_skip(self):
        """
        Check if the export can be skipped
        """
        if self.binding.sync_status == 'exporting':
            return True
        return False

    def _prepare_product_data(self):
        """Prepare product data for Magento"""
        product = self.binding.odoo_id

        # Basic product data
        data = {
            'sku': self.binding.magento_sku or product.default_code or f'odoo-{product.id}',
            'name': product.name,
            'price': product.list_price,
            'status': 1 if product.active else 0,
            'visibility': 4,  # Catalog, Search
            'type_id': 'simple',  # Simple product
            'attribute_set_id': 4,  # Default attribute set
            'weight': product.weight or 0.0,
            'extension_attributes': {
                'stock_item': {
                    'qty': product.qty_available,
                    'is_in_stock': 1 if product.qty_available > 0 else 0,
                    'manage_stock': 1,
                    'use_config_manage_stock': 0,
                }
            },
            'custom_attributes': [
                {
                    'attribute_code': 'description',
                    'value': product.description or ''
                },
                {
                    'attribute_code': 'short_description',
                    'value': product.description_sale or ''
                },
                {
                    'attribute_code': 'url_key',
                    'value': self.binding.url_key or self._generate_url_key(product.name)
                }
            ]
        }

        return data

    def _generate_url_key(self, name):
        """Generate URL key from product name"""
        if not name:
            return ''
        # Replace spaces with hyphens and make lowercase
        url_key = name.lower().replace(' ', '-')
        # Remove special characters
        url_key = ''.join(c for c in url_key if c.isalnum() or c == '-')
        # Remove duplicate hyphens
        while '--' in url_key:
            url_key = url_key.replace('--', '-')
        # Trim hyphens from beginning and end
        url_key = url_key.strip('-')
        return url_key

    def _create(self, data):
        """Create product in Magento"""
        client = self.backend_record._get_magento_client()

        try:
            result = client.create_product(data)
            product_id = result.get('id')

            # Update websites availability
            if self.binding.magento_website_ids:
                website_ids = self.binding.magento_website_ids.mapped('external_id')
                for website_id in website_ids:
                    client._make_request(
                        f'products/{data["sku"]}/websites',
                        method='POST',
                        data={'websiteId': website_id}
                    )

            return product_id

        except Exception as e:
            _logger.error(f"Error creating product in Magento: {str(e)}")
            self.binding.write({
                'sync_status': 'error',
            })
            raise

    def _update(self, data):
        """Update product in Magento"""
        client = self.backend_record._get_magento_client()

        try:
            client.update_product(data['sku'], data)

            # Update websites availability
            if self.binding.magento_website_ids:
                current_websites = client._make_request(
                    f'products/{data["sku"]}/websites',
                    method='GET'
                )

                # Add product to websites
                website_ids = self.binding.magento_website_ids.mapped('external_id')
                for website_id in website_ids:
                    if website_id not in current_websites:
                        client._make_request(
                            f'products/{data["sku"]}/websites',
                            method='POST',
                            data={'websiteId': website_id}
                        )

                # Remove product from websites not in binding
                for website_id in current_websites:
                    if website_id not in website_ids:
                        client._make_request(
                            f'products/{data["sku"]}/websites/{website_id}',
                            method='DELETE'
                        )

            return True

        except Exception as e:
            _logger.error(f"Error updating product in Magento: {str(e)}")
            self.binding.write({
                'sync_status': 'error',
            })
            raise

    def _map_data(self):
        return self._prepare_product_data()

    def _after_export(self):
        """Hook called at the end of the export"""
        self.binding.write({
            'sync_date': fields.Datetime.now(),
            'sync_status': 'synced',
        })

        # Export all variants if needed
        if len(self.binding.product_variant_ids) > 1:
            for variant in self.binding.product_variant_ids:
                magento_variant = self.env['magento.product.product'].search([
                    ('backend_id', '=', self.backend_record.id),
                    ('odoo_id', '=', variant.id)
                ], limit=1)

                if magento_variant:
                    magento_variant.with_delay(
                        channel='root.magento.product'
                    ).export_record()


class MagentoProductStockExporter(Component):
    _name = 'magento.product.stock.exporter'
    _inherit = ['magento.exporter']
    _apply_on = ['magento.product.product']

    def _prepare_stock_data(self):
        """Prepare stock data for Magento"""
        product = self.binding.odoo_id

        data = {
            'qty': int(product.qty_available),
            'is_in_stock': 1 if product.qty_available > 0 else 0,
            'manage_stock': 1,
            'use_config_manage_stock': 0,
        }

        return data

    def _map_data(self):
        return self._prepare_stock_data()

    def _update(self, data):
        """Update stock in Magento"""
        client = self.backend_record._get_magento_client()

        try:
            sku = self.binding.magento_sku or self.binding.default_code or f'odoo-{self.binding.id}'
            result = client.update_stock_item(sku, data)

            self.binding.write({
                'sync_date': fields.Datetime.now(),
            })

            return True

        except Exception as e:
            _logger.error(f"Error updating stock in Magento: {str(e)}")
            raise