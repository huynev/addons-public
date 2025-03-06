# -*- coding: utf-8 -*-
from odoo.addons.component.core import AbstractComponent


class ShopeeConnectorComponent(AbstractComponent):
    """Base Shopee Connector Component.

    All components of the Shopee Connector inherit from this component.
    It's a layer on top of the 'base.connector' to add Shopee specific logic.
    """
    _name = 'base.shopee.connector'
    _inherit = 'base.connector'
    _collection = 'shopee.backend'