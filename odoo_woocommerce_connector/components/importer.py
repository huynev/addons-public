# -*- coding: utf-8 -*-
# Copyright 2023 Your Company
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo.addons.component.core import Component
from odoo.addons.connector.exception import IDMissingInBackend
from odoo import fields, _
import logging
from datetime import datetime

_logger = logging.getLogger(__name__)


class WooImporter(Component):
    """Base importer for WooCommerce"""
    _name = 'woo.importer'
    _inherit = ['base.importer', 'base.woo.connector']
    _usage = 'record.importer'

    def __init__(self, work_context):
        super().__init__(work_context)
        self.woo_id = None
        self.woo_record = None

    def _get_woo_data(self):
        """Return the WooCommerce data for processing"""
        try:
            return self.backend_adapter.read(self.woo_id)
        except Exception as e:
            _logger.error("Error in _get_woo_data: %s", str(e))
            raise

    def _before_import(self):
        """Hook called before the import"""
        return

    def _is_uptodate(self, binding):
        """Check if the import is up to date with the external data"""
        assert binding
        if not hasattr(binding, 'woo_updated_at') or not binding.woo_updated_at:
            return False

        woo_updated_at = self.woo_record.get('date_modified')
        if not woo_updated_at:
            return False

        try:
            # Try ISO 8601 format (with Z or +00:00)
            if 'T' in woo_updated_at:
                if woo_updated_at.endswith('Z'):
                    woo_updated_at = woo_updated_at[:-1] + '+00:00'
                # Parse with Python's fromisoformat
                woo_dt = datetime.fromisoformat(woo_updated_at)
                return binding.woo_updated_at >= woo_dt
        except (ValueError, TypeError):
            # Fallback to basic comparison
            pass

        return False

    def _import_dependencies(self):
        """Import the dependencies for the record"""
        return

    def _map_data(self):
        """Returns an instance of
        :py:class:`~odoo.addons.connector.components.mapper.MapRecord`
        """
        return self.mapper.map_record(self.woo_record)

    def _validate_data(self, data):
        """Check if the values to import are correct"""
        return data

    def _get_binding(self):
        """Return the binding record for the external ID"""
        return self.binder.to_internal(self.woo_id)

    def _create(self, data):
        """Create the Odoo record"""
        # Special case for translatable fields:
        # TODO: handle translations if needed

        model_ctx = {}
        if 'lang' in data:
            model_ctx['lang'] = data.pop('lang')

        binding = self.model.with_context(**model_ctx).create(data)

        _logger.debug('%s created from WooCommerce %s', binding, self.woo_id)
        return binding

    def _update(self, binding, data):
        """Update an Odoo record"""
        binding.with_context(connector_no_export=True).write(data)
        _logger.debug('%s updated from WooCommerce %s', binding, self.woo_id)
        return binding

    def _after_import(self, binding):
        """Hook called at the end of the import"""
        return

    def run(self, woo_id, force=False):
        """Run the synchronization"""
        self.woo_id = woo_id

        try:
            self.woo_record = self._get_woo_data()
        except IDMissingInBackend:
            return _('Record does not exist in WooCommerce')

        binding = self._get_binding()

        # If already exists and not forced, check if it's up-to-date
        if binding and not force and self._is_uptodate(binding):
            return _('Already up-to-date')

        # Call hook before import
        self._before_import()

        # Import dependencies
        self._import_dependencies()

        # Map WooCommerce record to Odoo data
        map_record = self._map_data()
        data = map_record.values()

        # Validate data
        data = self._validate_data(data)

        # Create or update the binding
        if binding:
            binding = self._update(binding, data)
        else:
            binding = self._create(data)

        # Bind the external ID to the binding
        self.binder.bind(self.woo_id, binding)

        # Call hook after import
        self._after_import(binding)

        return _('Import complete for: %s') % binding.display_name


class WooBatchImporter(Component):
    """Batch importer for WooCommerce"""
    _name = 'woo.batch.importer'
    _inherit = ['base.importer', 'base.woo.connector']
    _usage = 'batch.importer'

    def run(self, filters=None):
        """Run the batch import"""
        if filters is None:
            filters = {}

        # Get batch size from backend
        batch_size = 100
        if self.backend_record.product_import_batch_size and 'woo.product.template' in self.model._name:
            batch_size = self.backend_record.product_import_batch_size
        elif self.backend_record.order_import_batch_size and 'woo.sale.order' in self.model._name:
            batch_size = self.backend_record.order_import_batch_size

        # Add pagination to filters
        filters['per_page'] = batch_size
        page = 1
        filters['page'] = page

        record_count = 0
        while True:
            _logger.info(
                'Importing %s from WooCommerce page %s with filters %s',
                self.model._name, page, filters
            )

            # Search records for this page
            record_ids = self.backend_adapter.search(filters)

            if not record_ids:
                break

            # Process each record
            for record_id in record_ids:
                self._import_record(record_id)
                record_count += 1

            # Check if we need to continue pagination
            if len(record_ids) < batch_size:
                break

            # Move to next page
            page += 1
            filters['page'] = page

        # Update the last import date
        if 'woo.product.template' in self.model._name:
            self.backend_record.last_product_import_date = fields.Datetime.now()
        elif 'woo.sale.order' in self.model._name:
            self.backend_record.last_order_import_date = fields.Datetime.now()

        return _('Batch import of %d records completed') % record_count

    def _import_record(self, record_id):
        """Import a record directly or by job"""
        importer = self.component(usage='record.importer')
        importer.run(record_id)


class WooProductImporter(Component):
    """Product importer for WooCommerce"""
    _name = 'woo.product.importer'
    _inherit = 'woo.importer'
    _apply_on = 'woo.product.template'

    def _import_dependencies(self):
        """Import product dependencies"""
        record = self.woo_record

        # Import product categories
        if 'categories' in record and record['categories']:
            for category in record['categories']:
                category_id = category.get('id')
                if category_id:
                    self._import_dependency(category_id, 'woo.product.category')

    def _import_dependency(self, woo_id, model_name, always=False):
        """Import a dependency"""
        importer = self.component(usage='record.importer', model_name=model_name)
        importer.run(woo_id, force=always)


class WooProductCategoryImporter(Component):
    """Product category importer for WooCommerce"""
    _name = 'woo.category.importer'
    _inherit = 'woo.importer'
    _apply_on = 'woo.product.category'

    def _import_dependencies(self):
        """Import category dependencies"""
        record = self.woo_record

        # Import parent category
        parent_id = record.get('parent')
        if parent_id and parent_id != 0:
            self._import_dependency(parent_id, 'woo.product.category')

    def _import_dependency(self, woo_id, model_name, always=False):
        """Import a dependency"""
        importer = self.component(usage='record.importer', model_name=model_name)
        importer.run(woo_id, force=always)


class WooSaleOrderImporter(Component):
    """Sale order importer for WooCommerce"""
    _name = 'woo.order.importer'
    _inherit = 'woo.importer'
    _apply_on = 'woo.sale.order'

    def _import_dependencies(self):
        """Import order dependencies"""
        record = self.woo_record

        # Import customer
        if record.get('customer_id'):
            self._import_dependency(record['customer_id'], 'woo.res.partner')

        # Import products from line items
        for line in record.get('line_items', []):
            if line.get('product_id'):
                self._import_dependency(line['product_id'], 'woo.product.template')

    def _import_dependency(self, woo_id, model_name, always=False):
        """Import a dependency"""
        importer = self.component(usage='record.importer', model_name=model_name)
        importer.run(woo_id, force=always)

    def _after_import(self, binding):
        """Hook called at the end of the import"""
        record = self.woo_record

        # Create order lines
        self._import_order_lines(binding, record)

        # Update order status
        self._update_order_status(binding, record)

        return

    def _import_order_lines(self, binding, record):
        """Import order lines"""
        if not record.get('line_items'):
            return

        order_line_model = self.env['woo.sale.order.line']
        sale_line_model = self.env['sale.order.line']
        product_binder = self.binder_for('woo.product.template')

        for line_data in record['line_items']:
            # Find product
            product = None
            if line_data.get('product_id'):
                woo_product = product_binder.to_internal(line_data['product_id'])
                if woo_product:
                    product = woo_product.odoo_id.product_variant_ids[0]

            if not product and line_data.get('sku'):
                product = self.env['product.product'].search([
                    ('default_code', '=', line_data['sku'])
                ], limit=1)

            if not product:
                # Use a default product
                product = self.env.ref('product.product_product_1', raise_if_not_found=False)
                if not product:
                    _logger.warning('No default product found for order line')
                    continue

            # Prepare values for order line
            line_values = {
                'order_id': binding.odoo_id.id,
                'product_id': product.id,
                'name': line_data.get('name', product.name),
                'product_uom_qty': float(line_data.get('quantity', 1.0)),
                'price_unit': float(line_data.get('price', 0.0)),
                'tax_id': [(6, 0, [])],  # Empty taxes, we'll handle them separately
            }

            # Handle taxes
            if line_data.get('total_tax', 0.0) and float(line_data['total_tax']) > 0:
                # Find or create tax
                tax_value = float(line_data['total_tax']) / float(line_data.get('quantity', 1.0))
                tax_percent = (tax_value / float(line_data.get('price', 1.0))) * 100 if float(
                    line_data.get('price', 0.0)) else 0

                tax = self.env['account.tax'].search([
                    ('type_tax_use', '=', 'sale'),
                    ('amount', '>=', tax_percent - 0.1),
                    ('amount', '<=', tax_percent + 0.1),
                ], limit=1)

                if not tax:
                    tax = self.env['account.tax'].create({
                        'name': f"WooCommerce Tax {tax_percent:.2f}%",
                        'type_tax_use': 'sale',
                        'amount_type': 'percent',
                        'amount': tax_percent,
                    })

                line_values['tax_id'] = [(6, 0, [tax.id])]

            # Create sale order line
            sale_line = sale_line_model.create(line_values)

            # Create WooCommerce binding
            order_line_model.create({
                'backend_id': binding.backend_id.id,
                'odoo_id': sale_line.id,
                'woo_order_id': binding.id,
                'woo_id': str(line_data['id']),
            })

        # Handle shipping lines
        for shipping in record.get('shipping_lines', []):
            # Use a generic product for shipping
            product = self.env.ref('delivery.product_product_delivery', raise_if_not_found=False)
            if not product:
                continue

            # Create line
            line_values = {
                'order_id': binding.odoo_id.id,
                'product_id': product.id,
                'name': shipping.get('method_title', 'Shipping'),
                'product_uom_qty': 1.0,
                'price_unit': float(shipping.get('total', 0.0)),
                'tax_id': [(6, 0, [])],
            }

            sale_line_model.create(line_values)

        # Handle fee lines
        for fee in record.get('fee_lines', []):
            # Use a generic product for fees
            product = self.env.ref('product.product_product_1', raise_if_not_found=False)
            if not product:
                continue

            # Create line
            line_values = {
                'order_id': binding.odoo_id.id,
                'product_id': product.id,
                'name': fee.get('name', 'Fee'),
                'product_uom_qty': 1.0,
                'price_unit': float(fee.get('total', 0.0)),
                'tax_id': [(6, 0, [])],
            }

            sale_line_model.create(line_values)

    def _update_order_status(self, binding, record):
        """Update order status based on WooCommerce status"""
        status = record.get('status', 'pending')
        order = binding.odoo_id

        # Map WooCommerce status to Odoo actions
        if status in ['pending', 'on-hold']:
            # Just created
            pass
        elif status == 'processing':
            # Confirm order
            if order.state == 'draft':
                order.action_confirm()
        elif status == 'completed':
            # Confirm and deliver order
            if order.state == 'draft':
                order.action_confirm()

            # Create invoice if not exists
            if not order.invoice_ids:
                try:
                    invoice = order._create_invoices()
                    invoice.action_post()
                except Exception as e:
                    _logger.error("Error creating invoice: %s", str(e))

            # Deliver products
            for picking in order.picking_ids.filtered(lambda p: p.state != 'done'):
                try:
                    for move in picking.move_lines:
                        move.quantity_done = move.product_uom_qty
                    picking.button_validate()
                except Exception as e:
                    _logger.error("Error validating picking: %s", str(e))
        elif status == 'cancelled':
            # Cancel order
            if order.state != 'cancel':
                order.action_cancel()


class WooCustomerImporter(Component):
    """Customer importer for WooCommerce"""
    _name = 'woo.customer.importer'
    _inherit = 'woo.importer'
    _apply_on = 'woo.res.partner'