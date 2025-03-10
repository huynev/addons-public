# -*- coding: utf-8 -*-
# Copyright 2023 Your Company
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo.addons.component.core import Component
from odoo import _
import logging

_logger = logging.getLogger(__name__)


class WooExporter(Component):
    """Base exporter for WooCommerce"""
    _name = 'woo.exporter'
    _inherit = ['base.exporter', 'base.woo.connector']
    _usage = 'record.exporter'

    def __init__(self, work_context):
        super().__init__(work_context)
        self.binding = None
        self.woo_id = None

    def _get_data(self, fields=None):
        """Return the data to export"""
        return self.mapper.map_record(self.binding).values(fields=fields)

    def _validate_data(self, data):
        """Check if the values to export are correct"""
        return data

    def _create(self, data):
        """Create the WooCommerce record"""
        return self.backend_adapter.create(data)

    def _update(self, data):
        """Update the WooCommerce record"""
        assert self.woo_id
        return self.backend_adapter.write(self.woo_id, data)

    def _run(self, fields=None):
        """Flow of the export"""
        assert self.binding

        if not self.woo_id:
            fields = None  # Export all fields for new records

        data = self._get_data(fields=fields)
        data = self._validate_data(data)

        if self.woo_id:
            self._update(data)
        else:
            self.woo_id = self._create(data)
            if self.woo_id:
                self.binder.bind(self.woo_id, self.binding)

        return _('Record exported with ID %s on WooCommerce') % self.woo_id

    def run(self, binding, *args, **kwargs):
        """Run the export"""
        self.binding = binding

        self.woo_id = self.binder.to_external(binding)

        result = self._run(*args, **kwargs)

        self.binding.write({
            'woo_updated_at': fields.Datetime.now(),
        })

        return result


class WooStockExporter(Component):
    """Export stock quantity to WooCommerce"""
    _name = 'woo.stock.exporter'
    _inherit = ['base.exporter', 'base.woo.connector']
    _usage = 'stock.exporter'

    def run(self, binding):
        """Export the stock quantity to WooCommerce"""
        woo_id = self.binder.to_external(binding)
        if not woo_id:
            return _('Record %s has no external ID') % binding.display_name

        product = binding.odoo_id

        # Calculate stock quantity
        qty_available = 0
        for variant in product.product_variant_ids:
            qty_available += variant.qty_available

        data = {
            'stock_quantity': int(qty_available),
            'manage_stock': True,
            'in_stock': qty_available > 0,
        }

        try:
            self.backend_adapter.write(woo_id, data)
            _logger.info(
                'Updated stock for product %s to %s on WooCommerce',
                woo_id, qty_available
            )

            # Update last export date
            binding.backend_id.last_stock_export_date = fields.Datetime.now()

            return _('Stock updated for %s') % binding.display_name
        except Exception as e:
            _logger.error(
                'Failed to update stock for product %s: %s',
                woo_id, str(e)
            )
            return _('Failed to update stock: %s') % str(e)


class WooProductExporter(Component):
    """Export products to WooCommerce"""
    _name = 'woo.product.exporter'
    _inherit = 'woo.exporter'
    _apply_on = 'woo.product.template'

    def _validate_data(self, data):
        """Check if the values to export are correct"""
        # Required fields in WooCommerce
        if not data.get('name'):
            data['name'] = self.binding.odoo_id.name or 'Product'

        return data


class WooCategoryExporter(Component):
    """Export product categories to WooCommerce"""
    _name = 'woo.category.exporter'
    _inherit = 'woo.exporter'
    _apply_on = 'woo.product.category'