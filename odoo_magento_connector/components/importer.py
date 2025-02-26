from odoo.addons.component.core import Component
import logging

_logger = logging.getLogger(__name__)


class MagentoImporter(Component):
    """ Base importer for Magento """
    _name = 'magento.importer'
    _inherit = ['base.importer', 'magento.base.connector']
    _usage = 'record.importer'

    def __init__(self, work_context):
        super().__init__(work_context)
        self.magento_record = None
        self.magento_id = None

    def _get_magento_data(self):
        """ Return the raw Magento data """
        return self.backend_record._get_magento_client().get(
            self.backend_record._magento_model_name,
            self.magento_id
        )

    def _map_data(self):
        """ Returns an instance of
        :py:class:`~odoo.addons.connector.components.mapper.MapRecord`
        """
        return self.mapper.map_record(self.magento_record)

    def _import_dependencies(self):
        """ Import the dependencies for the record"""
        return

    def _validate_data(self, data):
        """ Check if the values to import are correct """
        return data

    def _must_skip(self):
        """ Return True if the import must be skipped """
        return False

    def _create(self, data):
        """ Create the Odoo record """
        binding = self.model.create(data)
        return binding

    def _update(self, binding, data):
        """ Update an Odoo record """
        binding.write(data)
        return binding

    def _after_import(self, binding):
        """ Hook called at the end of the import """
        return

    def run(self, magento_id, force=False):
        """ Run the synchronization
        :param magento_id: identifier of the record on Magento
        """
        self.magento_id = magento_id

        skip = self._must_skip()
        if skip:
            return skip

        self.magento_record = self._get_magento_data()

        # Import dependencies first
        self._import_dependencies()

        # Map record
        map_record = self._map_data()
        record = map_record.values()

        if not record:
            return

        # Find existing binding
        binding = self.binder.to_internal(self.magento_id)

        # Import the record
        record = self._validate_data(record)

        if binding:
            # Update
            binding = self._update(binding, record)
        else:
            # Create
            binding = self._create(record)

        # Bind record
        self.binder.bind(self.magento_id, binding)

        # After import hook
        self._after_import(binding)

        return binding