from odoo.addons.component.core import Component
from odoo.addons.connector.components.mapper import mapping
import logging

_logger = logging.getLogger(__name__)

class ProductImporter(Component):
    _name = 'prestashop.product.importer'
    _inherit = 'prestashop.importer'
    _apply_on = 'prestashop.product.template'

    def _import_dependencies(self):
        record = self.prestashop_record
        # Import categories
        if record.get('id_category_default'):
            self._import_dependency(
                record['id_category_default'],
                'prestashop.product.category'
            )

    def _create(self, data):
        binding = super()._create(data)
        self._import_images(binding)
        return binding

    def _import_images(self, binding):
        prestashop = self.backend_record._get_prestashop_client()
        try:
            image_ids = prestashop.get(
                'images/products/%s' % self.external_id
            )
            # Process images...
        except Exception as e:
            _logger.error(
                'Failed to import images for product %s: %s',
                binding.prestashop_id,
                str(e)
            )

class ProductImportMapper(Component):
    _name = 'prestashop.product.import.mapper'
    _inherit = 'prestashop.import.mapper'
    _apply_on = 'prestashop.product.template'

    @mapping
    def name(self, record):
        return {'name': record.get('name', {}).get('language', '')}

    @mapping
    def type(self, record):
        return {'type': 'product'}

    @mapping
    def standard_price(self, record):
        return {'standard_price': float(record.get('wholesale_price', 0.0))}

    @mapping
    def list_price(self, record):
        return {'list_price': float(record.get('price', 0.0))}

    @mapping
    def active(self, record):
        return {'active': record.get('active') == '1'}

    @mapping
    def barcode(self, record):
        return {'barcode': record.get('ean13') or record.get('isbn')}

    @mapping
    def weight(self, record):
        return {'weight': float(record.get('weight', 0.0))}