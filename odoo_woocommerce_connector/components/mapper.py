# -*- coding: utf-8 -*-
# Copyright 2023 Your Company
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo.addons.component.core import Component
from odoo.addons.connector.components.mapper import mapping, changed_by
import logging

_logger = logging.getLogger(__name__)


class WooImportMapper(Component):
    """Base mapper for importing WooCommerce records"""
    _name = 'woo.import.mapper'
    _inherit = ['base.woo.connector', 'base.import.mapper']
    _usage = 'import.mapper'

    @mapping
    def backend_id(self, record):
        """Always set the backend from which we import the record"""
        return {'backend_id': self.backend_record.id}


class WooExportMapper(Component):
    """Base mapper for exporting records to WooCommerce"""
    _name = 'woo.export.mapper'
    _inherit = ['base.woo.connector', 'base.export.mapper']
    _usage = 'export.mapper'


# Product Mappers
class WooProductImportMapper(Component):
    """Mapper for importing WooCommerce products"""
    _name = 'woo.product.import.mapper'
    _inherit = 'woo.import.mapper'
    _apply_on = 'woo.product.template'

    @mapping
    def name(self, record):
        """Map product name"""
        return {'name': record['name']}

    @mapping
    def description(self, record):
        """Map product description"""
        return {
            'description': record.get('description', ''),
            'description_sale': record.get('short_description', '')
        }

    @mapping
    def price(self, record):
        """Map product price"""
        price = record.get('price', '0.0')
        if not price:
            price = '0.0'
        return {'list_price': float(price)}

    @mapping
    def active(self, record):
        """Map product active state"""
        return {'active': record.get('status') == 'publish'}

    @mapping
    def default_code(self, record):
        """Map product reference (SKU)"""
        return {'default_code': record.get('sku', '')}

    @mapping
    def type(self, record):
        """Map product type"""
        return {'type': 'product'}  # Stock managed product

    @mapping
    def woo_status(self, record):
        """Map WooCommerce status"""
        return {'woo_status': record.get('status', 'draft')}

    @mapping
    def woo_updated_at(self, record):
        """Map WooCommerce updated date"""
        if 'date_modified' in record:
            from datetime import datetime
            date_modified = record['date_modified']
            if 'T' in date_modified:
                # Handle ISO 8601 format
                try:
                    return {'woo_updated_at': datetime.fromisoformat(date_modified.replace('Z', '+00:00'))}
                except ValueError:
                    pass
            # Fallback
            return {'woo_updated_at': datetime.now()}
        return {}


class WooProductExportMapper(Component):
    """Mapper for exporting products to WooCommerce"""
    _name = 'woo.product.export.mapper'
    _inherit = 'woo.export.mapper'
    _apply_on = 'woo.product.template'

    @mapping
    def name(self, record):
        return {'name': record.name}

    @mapping
    def description(self, record):
        return {
            'description': record.description or '',
            'short_description': record.description_sale or ''
        }

    @mapping
    def price(self, record):
        return {'price': str(record.list_price)}

    @mapping
    def status(self, record):
        return {'status': 'publish' if record.active else 'draft'}

    @mapping
    def sku(self, record):
        return {'sku': record.default_code or ''}

    @mapping
    def inventory(self, record):
        qty = 0
        for variant in record.product_variant_ids:
            qty += variant.qty_available

        return {
            'manage_stock': True,
            'stock_quantity': int(qty),
            'in_stock': qty > 0
        }


# Category Mappers
class WooCategoryImportMapper(Component):
    """Mapper for importing WooCommerce product categories"""
    _name = 'woo.category.import.mapper'
    _inherit = 'woo.import.mapper'
    _apply_on = 'woo.product.category'

    @mapping
    def name(self, record):
        return {'name': record['name']}

    @mapping
    def parent_id(self, record):
        """Map category parent"""
        if not record.get('parent') or record['parent'] == 0:
            return {}

        binder = self.binder_for('woo.product.category')
        parent = binder.to_internal(record['parent'], unwrap=True)

        if parent:
            return {'parent_id': parent.id}
        return {}

    @mapping
    def woo_parent_id(self, record):
        """Map WooCommerce parent category"""
        if not record.get('parent') or record['parent'] == 0:
            return {}

        binder = self.binder_for('woo.product.category')
        parent = binder.to_internal(record['parent'])

        if parent:
            return {'woo_parent_id': parent.id}
        return {}


# Order Mappers
class WooOrderImportMapper(Component):
    """Mapper for importing WooCommerce orders"""
    _name = 'woo.order.import.mapper'
    _inherit = 'woo.import.mapper'
    _apply_on = 'woo.sale.order'

    @mapping
    def name(self, record):
        """Map order name"""
        return {'name': 'WOO/%s' % record['id']}

    @mapping
    def partner_id(self, record):
        """Map order customer"""
        binder = self.binder_for('woo.res.partner')

        # Try to find partner by WooCommerce customer ID
        if record.get('customer_id'):
            customer = binder.to_internal(record['customer_id'], unwrap=True)
            if customer:
                return {
                    'partner_id': customer.id,
                    'partner_invoice_id': customer.id,
                    'partner_shipping_id': customer.id
                }

        # If no customer ID or binding, create a new partner
        billing = record.get('billing', {})
        if not billing:
            return {}

        partner_obj = self.env['res.partner']

        # Search by email
        email = billing.get('email')
        if email:
            partner = partner_obj.search([('email', '=', email)], limit=1)
            if partner:
                return {
                    'partner_id': partner.id,
                    'partner_invoice_id': partner.id,
                    'partner_shipping_id': partner.id
                }

        # Create a new partner
        country_obj = self.env['res.country']
        state_obj = self.env['res.country.state']

        # Find country
        country = None
        if billing.get('country'):
            country = country_obj.search([('code', '=', billing['country'])], limit=1)

        # Find state
        state = None
        if billing.get('state') and country:
            state = state_obj.search([
                ('code', '=', billing['state']),
                ('country_id', '=', country.id)
            ], limit=1)

        # Create partner values
        partner_values = {
            'name': '%s %s' % (billing.get('first_name', ''), billing.get('last_name', '')),
            'email': email,
            'phone': billing.get('phone', ''),
            'street': billing.get('address_1', ''),
            'street2': billing.get('address_2', ''),
            'city': billing.get('city', ''),
            'zip': billing.get('postcode', ''),
            'country_id': country.id if country else False,
            'state_id': state.id if state else False,
            'customer': True,
        }

        partner = partner_obj.create(partner_values)

        return {
            'partner_id': partner.id,
            'partner_invoice_id': partner.id,
            'partner_shipping_id': partner.id
        }

    @mapping
    def date_order(self, record):
        """Map order date"""
        if 'date_created' in record:
            from datetime import datetime
            date_created = record['date_created']
            if 'T' in date_created:
                # Handle ISO 8601 format
                try:
                    return {'date_order': datetime.fromisoformat(date_created.replace('Z', '+00:00'))}
                except ValueError:
                    pass
        return {}

    @mapping
    def woo_status(self, record):
        """Map WooCommerce order status"""
        return {'woo_status': record.get('status', 'pending')}

    @mapping
    def woo_order_key(self, record):
        """Map WooCommerce order key"""
        return {'woo_order_key': record.get('order_key', '')}

    @mapping
    def woo_customer_id(self, record):
        """Map WooCommerce customer ID"""
        if record.get('customer_id'):
            return {'woo_customer_id': record['customer_id']}
        return {}

    @mapping
    def state(self, record):
        """Map order state based on WooCommerce status"""
        # Initial state
        state = 'draft'

        # Map WooCommerce status to Odoo state
        woo_status = record.get('status', 'pending')
        if woo_status in ('processing', 'on-hold'):
            state = 'sale'
        elif woo_status == 'completed':
            state = 'done'
        elif woo_status == 'cancelled':
            state = 'cancel'

        return {'state': state}


# Customer Mappers
class WooCustomerImportMapper(Component):
    """Mapper for importing WooCommerce customers"""
    _name = 'woo.customer.import.mapper'
    _inherit = 'woo.import.mapper'
    _apply_on = 'woo.res.partner'

    @mapping
    def name(self, record):
        """Map customer name"""
        name = '%s %s' % (record.get('first_name', ''), record.get('last_name', ''))
        return {'name': name.strip() or 'WooCommerce Customer'}

    @mapping
    def woo_email(self, record):
        """Map customer email"""
        return {'woo_email': record.get('email', '')}

    @mapping
    def email(self, record):
        """Map customer email"""
        return {'email': record.get('email', '')}

    @mapping
    def woo_username(self, record):
        """Map customer username"""
        return {'woo_username': record.get('username', '')}

    @mapping
    def phone(self, record):
        """Map customer phone"""
        if record.get('billing') and record['billing'].get('phone'):
            return {'phone': record['billing']['phone']}
        return {}

    @mapping
    def address(self, record):
        """Map customer address"""
        if not record.get('billing'):
            return {}

        billing = record['billing']
        country_obj = self.env['res.country']
        state_obj = self.env['res.country.state']

        # Find country
        country = None
        if billing.get('country'):
            country = country_obj.search([('code', '=', billing['country'])], limit=1)

        # Find state
        state = None
        if billing.get('state') and country:
            state = state_obj.search([
                ('code', '=', billing['state']),
                ('country_id', '=', country.id)
            ], limit=1)

        return {
            'street': billing.get('address_1', ''),
            'street2': billing.get('address_2', ''),
            'city': billing.get('city', ''),
            'zip': billing.get('postcode', ''),
            'country_id': country.id if country else False,
            'state_id': state.id if state else False,
        }