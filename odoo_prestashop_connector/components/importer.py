# components/importer.py
from odoo.addons.component.core import AbstractComponent
from odoo.addons.connector.components.mapper import ImportMapper
import logging

_logger = logging.getLogger(__name__)

class PrestashopImporter(AbstractComponent):
    """ Generic importer for PrestaShop """
    _name = 'prestashop.importer'
    _inherit = ['base.importer']
    _usage = 'record.importer'

    def __init__(self, work_context):
        super().__init__(work_context)
        self.prestashop_record = None
        self.external_id = None

    def _get_prestashop_data(self):
        """ Return the raw PrestaShop data for """
        return self.backend_record._get_prestashop_client().get(
            self.backend_record._prestashop_model_name,
            self.external_id
        )

    def _before_import(self):
        """ Hook called before the import """
        pass

    def _import_dependencies(self):
        """ Import the dependencies for the record"""
        pass

    def _map_data(self):
        """ Returns an instance of
        :py:class:`~odoo.addons.connector.components.mapper.MapRecord`
        """
        return self.mapper.map_record(self.prestashop_record)

    def _validate_data(self, data):
        """ Check if the values to import are correct """
        return data

    def _create(self, data):
        """ Create the Odoo record """
        return self.model.create(data)

    def _update(self, binding, data):
        """ Update an Odoo record """
        binding.write(data)

    def _after_import(self, binding):
        """ Hook called at the end of the import """
        pass

    def run(self, external_id, force=False):
        """ Run the synchronization
        :param external_id: identifier of the record on PrestaShop
        """
        self.external_id = external_id
        lock_name = 'import({}, {}, {}, {})'.format(
            self.backend_record._name,
            self.backend_record.id,
            self.work.model_name,
            external_id,
        )

        self.prestashop_record = self._get_prestashop_data()

        if not self.prestashop_record:
            _logger.info(
                'Record for model %s with external ID %s not found on PrestaShop. Skipping.',
                self.model._name, external_id
            )
            return

        # import dependencies first
        self._before_import()
        self._import_dependencies()

        # map record
        map_record = self._map_data()
        record = map_record.values()

        if not record:
            return

        # import the record
        record = self._validate_data(record)
        binding = self._create(record)

        self._after_import(binding)