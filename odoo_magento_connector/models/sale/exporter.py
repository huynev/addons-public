from odoo.addons.component.core import Component
from odoo import fields
import logging

_logger = logging.getLogger(__name__)


class MagentoSaleOrderExporter(Component):
    _name = 'magento.sale.order.exporter'
    _inherit = ['magento.exporter']
    _apply_on = ['magento.sale.order']

    def _has_to_skip(self):
        """Return True if the export can be skipped"""
        # Skip if order is not confirmed
        if self.binding.odoo_id.state not in ['sale', 'done']:
            return True
        return False

    def _prepare_order_data(self):
        """Prepare order data for Magento"""
        order = self.binding.odoo_id
        store = self.binding.store_id

        # Customer info
        customer_id = None
        if order.partner_id.magento_bind_ids:
            partner_binding = order.partner_id.magento_bind_ids.filtered(
                lambda b: b.backend_id == self.backend_record
            )
            if partner_binding:
                customer_id = partner_binding[0].external_id

        # Basic order data
        data = {
            'customer_id': customer_id,
            'customer_email': order.partner_id.email or 'guest@example.com',
            'customer_firstname': order.partner_id.name.split(' ')[0] if order.partner_id.name else 'Guest',
            'customer_lastname': ' '.join(order.partner_id.name.split(' ')[
                                          1:]) if order.partner_id.name and ' ' in order.partner_id.name else 'Customer',
            'store_id': store.external_id if store else 1,
            'items': self._prepare_order_lines(),
            'billing_address': self._prepare_billing_address(),
            'payment': {
                'method': 'checkmo'  # Default to check/money order
            },
            'status': 'pending',
        }

        # Add shipping info if available
        if order.partner_shipping_id:
            data['extension_attributes'] = {
                'shipping_assignments': [
                    {
                        'shipping': {
                            'address': self._prepare_shipping_address(),
                            'method': 'flatrate_flatrate'  # Default to flat rate
                        }
                    }
                ]
            }

        return data

    def _prepare_order_lines(self):
        """Prepare order lines data for Magento"""
        lines = []

        for line in self.binding.odoo_id.order_line:
            # Skip shipping/delivery lines
            if line.is_delivery:
                continue

            # Find product in Magento
            product_binding = None
            if line.product_id.magento_bind_ids:
                product_binding = line.product_id.magento_bind_ids.filtered(
                    lambda b: b.backend_id == self.backend_record
                )

            sku = product_binding and product_binding[
                0].magento_sku or line.product_id.default_code or f'odoo-{line.product_id.id}'

            line_data = {
                'sku': sku,
                'qty': line.product_uom_qty,
                'price': line.price_unit,
                'name': line.name,
                'product_type': 'simple',
            }

            lines.append(line_data)

        return lines

    def _prepare_billing_address(self):
        """Prepare billing address data for Magento"""
        partner = self.binding.odoo_id.partner_invoice_id or self.binding.odoo_id.partner_id

        address = {
            'firstname': partner.name.split(' ')[0] if partner.name else '',
            'lastname': ' '.join(
                partner.name.split(' ')[1:]) if partner.name and ' ' in partner.name else partner.name or '',
            'street': [partner.street or '', partner.street2 or ''],
            'city': partner.city or '',
            'postcode': partner.zip or '',
            'telephone': partner.phone or '',
            'email': partner.email or self.binding.odoo_id.partner_id.email or '',
        }

        if partner.country_id:
            address['country_id'] = partner.country_id.code

        if partner.state_id:
            address['region'] = partner.state_id.name
            address['region_id'] = partner.state_id.code

        return address

    def _prepare_shipping_address(self):
        """Prepare shipping address data for Magento"""
        partner = self.binding.odoo_id.partner_shipping_id

        address = {
            'firstname': partner.name.split(' ')[0] if partner.name else '',
            'lastname': ' '.join(
                partner.name.split(' ')[1:]) if partner.name and ' ' in partner.name else partner.name or '',
            'street': [partner.street or '', partner.street2 or ''],
            'city': partner.city or '',
            'postcode': partner.zip or '',
            'telephone': partner.phone or '',
        }

        if partner.country_id:
            address['country_id'] = partner.country_id.code

        if partner.state_id:
            address['region'] = partner.state_id.name
            address['region_id'] = partner.state_id.code

        return address

    def _map_data(self):
        return self._prepare_order_data()

    def _create(self, data):
        """Create order in Magento"""
        client = self.backend_record._get_magento_client()

        try:
            result = client.create_order(data)
            order_id = result.get('entity_id')
            increment_id = result.get('increment_id')

            # Update binding
            self.binding.write({
                'external_id': order_id,
                'magento_increment_id': increment_id,
                'sync_date': fields.Datetime.now(),
            })

            return order_id

        except Exception as e:
            _logger.error(f"Error creating order in Magento: {str(e)}")
            raise

    def _after_export(self):
        """Hook called at the end of the export"""
        # Export all order lines
        for line in self.binding.magento_order_line_ids:
            line.sync_date = fields.Datetime.now()