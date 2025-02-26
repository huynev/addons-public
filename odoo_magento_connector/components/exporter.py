from odoo.addons.component.core import Component
import logging

_logger = logging.getLogger(__name__)


class MagentoExporter(Component):
    """ Base exporter for Magento """
    _name = 'magento.exporter'
    _inherit = ['base.exporter', 'magento.base.connector']
    _usage = 'record.exporter'

    def __init__(self, work_context):
        super().__init__(work_context)
        self.binding = None
        self.external_id = None

    def _get_binding(self):
        return self.binding

    def _map_data(self):
        """ Convert the external record to Magento data """
        return self.mapper.map_record(self._get_binding())

    def _validate_data(self, data):
        """ Check if the values to export are correct """
        return data

    def _export_dependencies(self):
        """ Export the dependencies for the record"""
        return

    def _lock(self):
        """ Lock the binding record """
        # Lock the binding record
        self.binding.with_context(connector_no_export=True).write({'sync_status': 'exporting'})

    def _unlock(self):
        """ Unlock the binding record """
        self.binding.with_context(connector_no_export=True).write({'sync_status': 'synced'})

    def _has_to_skip(self):
        """ Return True if the export can be skipped """
        return False

    def _create(self, data):
        """ Create the Magento record """
        magento = self.backend_record._get_magento_client()
        result = magento.create(self.backend_record._magento_model_name, data)
        return result

    def _update(self, data):
        """ Update the Magento record """
        magento = self.backend_record._get_magento_client()
        result = magento.write(self.backend_record._magento_model_name,
                               self.external_id, data)
        return result

    def _after_export(self):
        """ Hook called at the end of the export """
        return

    def run(self, binding, *args, **kwargs):
        """ Run the synchronization
        :param binding: binding record to export
        """
        self.binding = binding
        self.external_id = self.binder.to_external(self.binding)

        if self._has_to_skip():
            return

        # Export the dependencies first
        self._export_dependencies()

        # Lock
        self._lock()

        try:
            # Map record
            map_record = self._map_data()
            data = map_record.values()

            # Validate data
            data = self._validate_data(data)

            if self.external_id:
                # Update
                self._update(data)
            else:
                # Create
                self.external_id = self._create(data)

            # Bind record
            self.binder.bind(self.external_id, self.binding)

            # After export hook
            self._after_export()
        finally:
            # Unlock
            self._unlock()

        return self.external_id