from odoo.addons.component.core import Component
import logging
import xml.etree.ElementTree as ET
from odoo import fields

_logger = logging.getLogger(__name__)


class SaleOrderExporter(Component):
    _name = 'prestashop.sale.order.exporter'
    _inherit = ['base.exporter']
    _apply_on = 'prestashop.sale.order'
    _usage = 'record.exporter'

    def run(self, binding):
        """ Export the sale order to PrestaShop """
        self.binding = binding
        prestashop = self.binding.shop_id.backend_id._get_prestashop_client()

        try:
            # Kiểm tra đơn hàng tồn tại bằng reference
            reference = self.binding.odoo_id.client_order_ref
            if reference:
                # Tìm đơn hàng có reference trùng khớp trên PrestaShop
                filters = {'filter[reference]': str(reference)}
                try:
                    all_orders = prestashop.get('orders', options=filters)
                    orders = all_orders.findall('.//order')

                    if len(orders) > 1:
                        # Nếu có nhiều đơn hàng, ghi log cảnh báo
                        prestashop_ids = [p.attrib.get('id') for p in orders if p.attrib.get('id')]
                        note_message = f"WARNING: Found multiple orders on PrestaShop with reference {reference}. Order IDs: {', '.join(prestashop_ids)}"
                        _logger.warning(note_message)
                        return

                    elif len(orders) == 1:
                        # Nếu chỉ có 1 đơn hàng, thực hiện update
                        prestashop_id = orders[0].attrib.get('id')
                        if prestashop_id:
                            # Cập nhật prestashop_id trong binding
                            self.binding.prestashop_id = int(prestashop_id)

                            # Cập nhật thông tin đơn hàng
                            data = self._prepare_data()
                            self._update(data)
                            _logger.info(f"Updated existing order on PrestaShop with reference {reference}")
                            return

                except Exception as e:
                    _logger.warning(f"Error checking existing order by reference: {str(e)}")

            # Nếu không tìm thấy đơn hàng hoặc không có reference, tạo mới
            data = self._prepare_data()
            if self.binding.prestashop_id:
                self._update(data)
            else:
                self._create(data)

        except Exception as e:
            _logger.error(f"Error during order export: {str(e)}")
            raise

    def _prepare_data(self):
        """ Prepare sale order data for export """
        prestashop = ET.Element('prestashop')
        prestashop.set('xmlns:xlink', 'http://www.w3.org/1999/xlink')
        order = ET.SubElement(prestashop, 'order')

        def create_cdata_element(parent, tag, value=''):
            elem = ET.SubElement(parent, tag)
            elem.text = f'<![CDATA[{value}]]>'
            return elem

        # ID nếu là update
        if self.binding.prestashop_id:
            create_cdata_element(order, 'id', str(self.binding.prestashop_id))

        # Basic order information
        create_cdata_element(order, 'reference', self.binding.odoo_id.client_order_ref or self.binding.odoo_id.name)

        # Customer information
        if self.binding.partner_id.prestashop_bind_ids:
            partner_binding = self.binding.partner_id.prestashop_bind_ids.filtered(
                lambda x: x.shop_id == self.binding.shop_id
            )
            if partner_binding:
                create_cdata_element(order, 'id_customer', str(partner_binding.prestashop_id))

        # Delivery and invoice addresses
        create_cdata_element(order, 'id_address_delivery',
                             str(self.binding.partner_shipping_id.prestashop_id) if self.binding.partner_shipping_id else '')
        create_cdata_element(order, 'id_address_invoice',
                             str(self.binding.partner_invoice_id.prestashop_id) if self.binding.partner_invoice_id else '')

        # Order status and payment
        create_cdata_element(order, 'current_state', '2')  # Payment accepted
        create_cdata_element(order, 'payment',
                             self.binding.payment_method_id.name if self.binding.payment_method_id else '')

        # Financial details
        create_cdata_element(order, 'total_paid', str(self.binding.amount_total))
        create_cdata_element(order, 'total_paid_tax_incl', str(self.binding.amount_total))
        create_cdata_element(order, 'total_shipping_tax_incl', '0')  # Set appropriate shipping cost

        # Order lines
        associations = ET.SubElement(order, 'associations')
        order_rows = ET.SubElement(associations, 'order_rows')

        for line in self.binding.prestashop_order_line_ids:
            order_row = ET.SubElement(order_rows, 'order_row')

            # Get product binding
            product_binding = line.product_id.prestashop_bind_ids.filtered(
                lambda x: x.shop_id == self.binding.shop_id
            )

            if product_binding:
                create_cdata_element(order_row, 'id_product', str(product_binding.prestashop_id))
                if line.product_id.default_code:  # Handle variant reference
                    create_cdata_element(order_row, 'product_reference', line.product_id.default_code)

            create_cdata_element(order_row, 'product_name', line.name)
            create_cdata_element(order_row, 'product_quantity', str(int(line.product_uom_qty)))
            create_cdata_element(order_row, 'product_price', str(line.price_unit))
            create_cdata_element(order_row, 'unit_price_tax_incl', str(line.price_unit))

        xml_str = ET.tostring(prestashop, encoding='utf-8', xml_declaration=True)
        xml_str = xml_str.decode('utf-8').replace('&lt;![CDATA[', '<![CDATA[').replace(']]&gt;', ']]>')
        return xml_str.encode('utf-8')

    def _create(self, data):
        """ Create order in PrestaShop """
        prestashop = self.binding.shop_id.backend_id._get_prestashop_client()
        try:
            result = prestashop.add('orders', data)
            if isinstance(result, ET.Element):
                order_elem = result.find('.//order')
                if order_elem is not None:
                    id_elem = order_elem.find('id')
                    if id_elem is not None and id_elem.text:
                        order_id = id_elem.text.strip('[]!CDATA')
                        self.binding.prestashop_id = int(order_id)
                        self.binding.date_add = fields.Datetime.now()
                        _logger.info(f"Created order in PrestaShop with ID: {order_id}")
                        return
            _logger.error("Could not find order ID in PrestaShop response")
        except Exception as e:
            _logger.error(f"Error creating order in PrestaShop: {str(e)}")
            raise

    def _update(self, data):
        """ Update order in PrestaShop """
        prestashop = self.binding.shop_id.backend_id._get_prestashop_client()
        try:
            prestashop.edit('orders', data)
            self.binding.date_upd = fields.Datetime.now()
            _logger.info(f"Updated order in PrestaShop with ID: {self.binding.prestashop_id}")
        except Exception as e:
            _logger.error(f"Error updating order in PrestaShop: {str(e)}")
            raise