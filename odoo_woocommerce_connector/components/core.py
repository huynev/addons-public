# -*- coding: utf-8 -*-
# Copyright 2023 Your Company
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo.addons.component.core import AbstractComponent


class WooConnectorComponent(AbstractComponent):
    """Base WooCommerce Connector Component.

    All components of the WooCommerce Connector inherit from this component.
    It's a layer on top of the 'base.connector' to add WooCommerce specific logic.
    """
    _name = 'base.woo.connector'
    _inherit = 'base.connector'
    _collection = 'woo.backend'