# -*- coding: utf-8 -*-
# Copyright 2023 Your Company
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo.addons.component.core import AbstractComponent
import logging

_logger = logging.getLogger(__name__)


class WooApiError(Exception):
    """Exception raised when the WooCommerce API returns an error"""

    def __init__(self, status_code, message):
        self.status_code = status_code
        self.message = message
        super().__init__(message)


class WooBackendAdapter(AbstractComponent):
    """Base Backend Adapter for WooCommerce"""
    _name = 'woo.backend.adapter'
    _inherit = ['base.backend.adapter', 'base.woo.connector']
    _usage = 'backend.adapter'

    def search(self, filters=None):
        """Search records according to filters and return IDs"""
        raise NotImplementedError

    def read(self, woo_id, attributes=None):
        """Read a record from WooCommerce"""
        raise NotImplementedError

    def search_read(self, filters=None):
        """Search and read records from WooCommerce"""
        woo_ids = self.search(filters)
        if not woo_ids:
            return []
        return [self.read(woo_id) for woo_id in woo_ids]

    def create(self, data):
        """Create a record in WooCommerce"""
        raise NotImplementedError

    def write(self, woo_id, data):
        """Update a record in WooCommerce"""
        raise NotImplementedError

    def delete(self, woo_id):
        """Delete a record from WooCommerce"""
        raise NotImplementedError


class GenericAdapter(AbstractComponent):
    """Generic adapter for WooCommerce endpoints"""
    _name = 'woo.adapter'
    _inherit = 'woo.backend.adapter'
    _usage = 'backend.adapter'

    _woo_endpoint = None
    _woo_model = None

    def search(self, filters=None):
        """Search records according to filters and return IDs"""
        if filters is None:
            filters = {}

        wcapi = self.backend_record._get_woo_api()
        result = wcapi.get(self._woo_endpoint, params=filters)

        if result.status_code != 200:
            raise WooApiError(
                result.status_code,
                "Error searching %s: %s" % (self._woo_model, result.text)
            )

        records = result.json()
        return [str(record['id']) for record in records]

    def read(self, woo_id, attributes=None):
        """Read a record from WooCommerce"""
        wcapi = self.backend_record._get_woo_api()
        result = wcapi.get("%s/%s" % (self._woo_endpoint, woo_id))

        if result.status_code != 200:
            raise WooApiError(
                result.status_code,
                "Error reading %s with ID %s: %s" % (
                    self._woo_model, woo_id, result.text
                )
            )

        return result.json()

    def create(self, data):
        """Create a record in WooCommerce"""
        wcapi = self.backend_record._get_woo_api()
        result = wcapi.post(self._woo_endpoint, data)

        if result.status_code not in (200, 201):
            raise WooApiError(
                result.status_code,
                "Error creating %s: %s" % (self._woo_model, result.text)
            )

        record = result.json()
        return str(record['id'])

    def write(self, woo_id, data):
        """Update a record in WooCommerce"""
        wcapi = self.backend_record._get_woo_api()
        result = wcapi.put("%s/%s" % (self._woo_endpoint, woo_id), data)

        if result.status_code not in (200, 201):
            raise WooApiError(
                result.status_code,
                "Error updating %s with ID %s: %s" % (
                    self._woo_model, woo_id, result.text
                )
            )

        return True

    def delete(self, woo_id):
        """Delete a record from WooCommerce"""
        wcapi = self.backend_record._get_woo_api()
        result = wcapi.delete("%s/%s" % (self._woo_endpoint, woo_id))

        if result.status_code not in (200, 201, 204):
            raise WooApiError(
                result.status_code,
                "Error deleting %s with ID %s: %s" % (
                    self._woo_model, woo_id, result.text
                )
            )

        return True


class WooProductAdapter(AbstractComponent):
    """Product adapter for WooCommerce"""
    _name = 'woo.product.adapter'
    _inherit = 'woo.adapter'
    _apply_on = 'woo.product.template'
    _woo_endpoint = 'products'
    _woo_model = 'product'


class WooOrderAdapter(AbstractComponent):
    """Order adapter for WooCommerce"""
    _name = 'woo.order.adapter'
    _inherit = 'woo.adapter'
    _apply_on = 'woo.sale.order'
    _woo_endpoint = 'orders'
    _woo_model = 'order'


class WooCategoryAdapter(AbstractComponent):
    """Category adapter for WooCommerce"""
    _name = 'woo.category.adapter'
    _inherit = 'woo.adapter'
    _apply_on = 'woo.product.category'
    _woo_endpoint = 'products/categories'
    _woo_model = 'category'


class WooCustomerAdapter(AbstractComponent):
    """Customer adapter for WooCommerce"""
    _name = 'woo.customer.adapter'
    _inherit = 'woo.adapter'
    _apply_on = 'woo.res.partner'
    _woo_endpoint = 'customers'
    _woo_model = 'customer'