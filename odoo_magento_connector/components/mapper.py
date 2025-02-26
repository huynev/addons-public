from odoo.addons.component.core import Component
from odoo.addons.connector.components.mapper import mapping

class MagentoImportMapper(Component):
    """ Base Import Mapper for Magento """
    _name = 'magento.import.mapper'
    _inherit = ['base.import.mapper', 'magento.base.connector']
    _usage = 'import.mapper'

class MagentoExportMapper(Component):
    """ Base Export Mapper for Magento """
    _name = 'magento.export.mapper'
    _inherit = ['base.export.mapper', 'magento.base.connector']
    _usage = 'export.mapper'