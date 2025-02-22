from odoo.addons.component.core import Component
import logging

_logger = logging.getLogger(__name__)

class PrestashopBatchImporter(Component):
    _name = 'prestashop.batch.importer'
    _inherit = ['base.importer']
    _usage = 'batch.importer'

    def run(self, filters=None):
        """ Run the synchronization """
        record_ids = self._search_prestashop(filters)
        _logger.info('search for prestashop %s returned %s',
                   self.model._name, record_ids)
        for record_id in record_ids:
            self._import_record(record_id)

    def _search_prestashop(self, filters):
        """ Search records according to the filters """
        prestashop = self.backend_record._get_prestashop_client()
        try:
            products = prestashop.get('products', filters)
            if not products.get('products'):
                return []
            return [int(product['id']) for product in products['products']]
        except Exception as err:
            _logger.error("Error searching products: %s", str(err))
            return []

    def _import_record(self, record_id):
        """ Import a record directly or delay the import of the record """
        # Sử dụng with_delay() để tạo job
        self.env[self.model._name].with_delay().import_record(
            self.backend_record,
            record_id
        )