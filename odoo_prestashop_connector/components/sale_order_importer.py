from odoo.addons.component.core import Component
import logging
from odoo import fields, api
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SaleOrderImporter(Component):
    _name = 'prestashop.sale.order.importer'
    _inherit = ['base.importer']
    _apply_on = 'prestashop.sale.order'
    _usage = 'record.importer'

    def run(self, prestashop_order_data):
        """ Import sale order from PrestaShop """
        try:
            # Check if order already exists
            existing_binding = self.env['prestashop.sale.order'].search([
                ('prestashop_id', '=', prestashop_order_data['id']),
                ('shop_id', '=', self.backend_record.id)
            ], limit=1)

            order_dict = {'order': prestashop_order_data}

            if existing_binding:
                return self._update_order(existing_binding, order_dict)
            else:
                return self._create_order(order_dict)

        except Exception as e:
            _logger.error(f"Error importing PrestaShop order: {str(e)}")
            raise UserError(f"Could not import PrestaShop order: {str(e)}")

    def _create_order(self, order_data):
        """ Create a new sale order from PrestaShop data """
        order_info = order_data.get('order', {})

        # Find or create customer
        partner = self._get_or_create_partner(order_info)

        # Create Odoo sale order
        sale_order = self.env['sale.order'].create({
            'partner_id': partner.id,
            'origin': f"PrestaShop Order {order_info.get('reference', '')}",
            'client_order_ref': order_info.get('reference', ''),
            'pricelist_id': self.backend_record.pricelist_id.id,
        })

        # Create PrestaShop binding
        prestashop_order = self.env['prestashop.sale.order'].create({
            'odoo_id': sale_order.id,
            'prestashop_id': order_info.get('id', ''),
            'shop_id': self.backend_record.id,
            'total_amount': float(order_info.get('total_paid', 0)),
            'date_add': fields.Datetime.now(),
        })

        # Create order lines
        self._create_order_lines(sale_order, order_data, prestashop_order)

        return prestashop_order

    def _update_order(self, existing_binding, order_data):
        """ Update an existing sale order """
        order_info = order_data.get('order', {})
        sale_order = existing_binding.odoo_id

        # Update order details
        sale_order.write({
            'origin': f"PrestaShop Order {order_info.get('reference', '')}",
            'client_order_ref': order_info.get('reference', '')}
        )

        # Update PrestaShop binding
        existing_binding.write({
            'total_amount': float(order_info.get('total_paid', 0)),
            'date_upd': fields.Datetime.now(),
        })

        # Recreate order lines
        sale_order.order_line.unlink()
        self._create_order_lines(sale_order, order_data, existing_binding)

        return existing_binding

    def _get_or_create_partner(self, order_info):
        """Find or create partner based on PrestaShop order data"""
        try:
            # Find PrestaShop customer
            customer_id = order_info.get('id_customer')
            existing_partner = self.env['prestashop.res.partner'].search([
                ('shop_id', '=', self.backend_record.id),
                ('prestashop_id', '=', customer_id)
            ], limit=1)

            if existing_partner:
                return existing_partner.odoo_id

            # Get customer details from PrestaShop
            prestashop = self.backend_record._get_prestashop_client()
            customer_xml = prestashop.get('customers', customer_id)

            customer = customer_xml.find('.//customer')
            if customer is not None:
                firstname = customer.find('firstname')
                lastname = customer.find('lastname')
                email = customer.find('email')

                firstname_text = firstname.text if firstname is not None else ''
                lastname_text = lastname.text if lastname is not None else ''
                email_text = email.text if email is not None else ''

                # Create new partner
                partner = self.env['res.partner'].create({
                    'name': f"{firstname_text} {lastname_text}".strip() or 'PrestaShop Customer',
                    'email': email_text,
                })

                # Create PrestaShop binding
                self.env['prestashop.res.partner'].create({
                    'odoo_id': partner.id,
                    'prestashop_id': customer_id,
                    'prestashop_email': email_text,
                    'shop_id': self.backend_record.id,
                })

                return partner

        except Exception as e:
            _logger.error(f"Error creating/finding customer: {str(e)}")
            raise

    def _create_order_lines(self, sale_order, order_data, prestashop_order):
        """Create sale order lines from PrestaShop order data"""
        try:
            order_rows = order_data.get('order', {}).get('order_rows', [])

            for row in order_rows:
                product_id = row.get('product_id')
                product_reference = row.get('product_reference')

                if not product_id:
                    _logger.warning(f"Product ID not found in row: {row}")
                    continue

                # Tìm prestashop.product.template binding
                product_binding = self.env['prestashop.product.template'].search([
                    ('shop_id', '=', self.backend_record.id),
                    ('prestashop_id', '=', product_id)
                ], limit=1)

                if not product_binding:
                    _logger.warning(f"Product not found for PrestaShop ID: {product_id}")
                    continue

                # Tìm variant dựa trên reference
                product = None
                if product_reference:
                    product = self.env['product.product'].search([
                        ('default_code', '=', product_reference)
                    ], limit=1)

                # Nếu không tìm thấy qua reference, sử dụng variant đầu tiên
                if not product:
                    product = product_binding.product_variant_ids[0]

                if not product.exists():
                    _logger.warning(f"Product does not exist: {product_binding.name}")
                    continue

                # Cập nhật thuế
                tax_id = False
                if product_binding.taxes_id:
                    tax_id = product_binding.taxes_id[0].id

                # Giá chưa thuế
                unit_price_tax_excl = float(row.get('unit_price_tax_excl', 0))
                # Tạo order line
                try:
                    order_line = self.env['sale.order.line'].create({
                        'order_id': sale_order.id,
                        'product_id': product.id,
                        'product_uom_qty': float(row.get('product_quantity', 1)),
                        'price_unit': unit_price_tax_excl,
                        'name': row.get('product_name', product.name),
                        'tax_id': [(6, 0, [tax_id])] if tax_id else [],
                    })

                    self.env['prestashop.sale.order.line'].create({
                        'shop_id': self.backend_record.id,
                        'odoo_id': order_line.id,
                        'prestashop_order_id': prestashop_order.id,
                        'prestashop_id': row.get('id'),
                        'prestashop_product_id': product_binding.id,
                    })

                except Exception as line_error:
                    _logger.error(f"Error creating order line for product {product.name}: {str(line_error)}")
                    continue

        except Exception as e:
            _logger.error(f"Error creating order lines: {str(e)}")
            raise