from odoo.addons.component.core import Component, AbstractComponent

class MagentoBaseConnectorComponent(AbstractComponent):
    """ Base Magento Connector Component """
    _name = 'magento.base.connector'
    _inherit = 'base.connector'
    _collection = 'magento.backend'