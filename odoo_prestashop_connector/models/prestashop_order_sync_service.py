from odoo import api, models, fields
import logging
import xml.etree.ElementTree as ET

_logger = logging.getLogger(__name__)


class PrestashopOrderSyncService(models.Model):
    _name = 'prestashop.order.sync.service'
    _description = 'PrestaShop Order Synchronization Service'

    name = fields.Char('Tên Tiến Trình', default='Đồng Bộ Đơn Hàng PrestaShop')
    shop_id = fields.Many2one(
        'prestashop.shop',
        'PrestaShop Shop',
        required=True
    )

    # Thống kê đồng bộ
    total_orders_imported = fields.Integer('Tổng Đơn Nhập', default=0)
    total_orders_exported = fields.Integer('Tổng Đơn Xuất', default=0)
    last_sync_date = fields.Datetime('Lần Đồng Bộ Cuối')

    # Trạng thái đồng bộ
    sync_status = fields.Selection([
        ('draft', 'Chưa Đồng Bộ'),
        ('running', 'Đang Đồng Bộ'),
        ('completed', 'Hoàn Thành'),
        ('error', 'Lỗi')
    ], default='draft')

    @api.model
    def sync_orders_from_prestashop(self):
        """
        Đồng bộ đơn hàng từ PrestaShop sang Odoo
        """
        try:
            backend = self.shop_id.backend_id
            prestashop = backend._get_prestashop_client()
            # Tìm đơn hàng mới
            try:
                # Gọi API và lấy dữ liệu XML
                orders_xml = prestashop.search('orders', {
                    'display': 'full',
                    'sort': '[id_DESC]',
                    'limit': 50
                })
            except Exception as search_error:
                _logger.error(f"Lỗi tìm kiếm đơn hàng: {str(search_error)}")
                return 0

            # Tìm tất cả các phần tử order
            orders = orders_xml.findall('.//order')

            sync_count = 0
            update_count = 0
            for order_elem in orders:
                try:
                    # Trích xuất ID đơn hàng
                    order_id = order_elem.find('id').text.strip()

                    # Kiểm tra xem đơn hàng đã tồn tại chưa
                    existing_order = self.env['prestashop.sale.order'].search([
                        ('shop_id', '=', self.shop_id.id),
                        ('prestashop_id', '=', order_id)
                    ], limit=1)

                    order_dict = self._parse_order_xml(order_elem)

                    if not existing_order:
                        # Tạo đơn hàng mới
                        self._create_sale_order(order_dict, backend)
                        sync_count += 1
                    else:
                        # Cập nhật đơn hàng đã tồn tại
                        self._update_sale_order(existing_order, order_dict, backend)
                        update_count += 1

                except Exception as order_error:
                    _logger.error(f"Lỗi xử lý đơn hàng: {str(order_error)}")
                    continue

            self.write({
                'total_orders_imported': sync_count,
                'total_orders_exported': update_count,
                'last_sync_date': fields.Datetime.now(),
                'sync_status': 'completed' if (sync_count + update_count) > 0 else 'draft'
            })

            _logger.info(f"Đã đồng bộ {sync_count} đơn hàng mới và cập nhật {update_count} đơn hàng từ PrestaShop")
            return sync_count + update_count

        except Exception as e:
            _logger.error(f"Lỗi đồng bộ đơn hàng từ PrestaShop: {str(e)}")
            self.write({
                'sync_status': 'error'
            })
            return 0

    def _update_sale_order(self, existing_order, order_data, backend):
        """
        Cập nhật đơn hàng Odoo từ dữ liệu PrestaShop
        """
        try:
            order_info = order_data.get('order', {})
            existing_order.write({
                'total_amount': float(order_info.get('total_paid', 0)),
                'date_upd': fields.Datetime.now(),
            })

            sale_order = existing_order.odoo_id

            sale_order.write({
                'origin': f"PrestaShop Order {order_info.get('reference', '')}",
                'client_order_ref': order_info.get('reference', ''),
            })

            sale_order.order_line.unlink()
            self._create_order_lines(sale_order, order_data, existing_order)

            return sale_order

        except Exception as e:
            _logger.error(f"Lỗi cập nhật đơn hàng: {str(e)}")
            raise

    def _parse_order_xml(self, order_elem):
        """
        Chuyển đổi phần tử XML đơn hàng sang dictionary
        """
        order_dict = {}

        # Trích xuất các trường đơn hàng
        for child in order_elem:
            # Xử lý các trường đặc biệt
            if child.tag == 'associations':
                order_dict['order_rows'] = self._parse_order_rows(child)
            elif child.text and child.text.strip():
                order_dict[child.tag] = child.text.strip()

        return {'order': order_dict}

    def _parse_order_rows(self, associations_elem):
        """
        Trích xuất chi tiết sản phẩm từ associations
        """
        order_rows = []

        # Tìm tất cả các order_row
        rows = associations_elem.findall('.//order_row')

        for row in rows:
            row_dict = {}
            for child in row:
                # Xử lý các trường có giá trị
                if child.text and child.text.strip():
                    row_dict[child.tag] = child.text.strip()

            order_rows.append(row_dict)

        return order_rows

    def _create_sale_order(self, order_data, backend):
        """
        Tạo đơn hàng Odoo từ dữ liệu PrestaShop
        """
        try:
            order_info = order_data.get('order', {})

            # Tìm hoặc tạo khách hàng
            partner = self._get_or_create_partner(order_info)

            # Lấy pricelist từ res.partner nếu có, không thì lấy từ shop_id
            pricelist = partner.property_product_pricelist or self.shop_id.pricelist_id

            # Tạo đơn hàng Odoo
            sale_order = self.env['sale.order'].create({
                'partner_id': partner.id,
                'origin': f"PrestaShop Order {order_info.get('reference', '')}",
                'client_order_ref': order_info.get('reference', ''),
                'pricelist_id': pricelist.id,
            })

            # Tạo liên kết PrestaShop
            prestashop_order = self.env['prestashop.sale.order'].create({
                'odoo_id': sale_order.id,
                'prestashop_id': order_info.get('id', ''),
                'shop_id': self.shop_id.id,
                'total_amount': float(order_info.get('total_paid', 0)),
                'date_add': fields.Datetime.now(),
            })

            # Tạo chi tiết đơn hàng
            self._create_order_lines(sale_order, order_data, prestashop_order)

            return sale_order

        except Exception as e:
            _logger.error(f"Lỗi tạo đơn hàng: {str(e)}")
            raise

    def _create_order_lines(self, sale_order, order_data, prestashop_order):
        try:
            order_rows = order_data.get('order', {}).get('order_rows', [])

            for row in order_rows:
                product_id = row.get('product_id')
                product_reference = row.get('product_reference')

                if not product_id:
                    _logger.warning(f"Không tìm thấy ID sản phẩm trong dòng: {row}")
                    continue

                # Tìm prestashop.product.template binding
                product_binding = self.env['prestashop.product.template'].search([
                    ('shop_id', '=', self.shop_id.id),
                    ('prestashop_id', '=', product_id)
                ], limit=1)

                if not product_binding:
                    _logger.warning(f"Không tìm thấy prestashop binding - PrestaShop ID: {product_id}")
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
                    _logger.warning(f"Sản phẩm không tồn tại: {product_binding.name}")
                    continue

                # Tạo order line
                try:
                    order_line = self.env['sale.order.line'].create({
                        'order_id': sale_order.id,
                        'product_id': product.id,
                        'product_uom_qty': float(row.get('product_quantity', 1)),
                        'price_unit': float(row.get('product_price', 0)),
                        'name': row.get('product_name', product.name),
                    })

                    self.env['prestashop.sale.order.line'].create({
                        'shop_id': self.shop_id.id,
                        'odoo_id': order_line.id,
                        'prestashop_order_id': prestashop_order.id,
                        'prestashop_id': product_id,
                        'prestashop_product_id': product_binding.id,
                    })

                except Exception as line_error:
                    _logger.error(f"Lỗi tạo dòng đơn hàng cho sản phẩm {product.name}: {str(line_error)}")
                    continue

        except Exception as e:
            _logger.error(f"Lỗi tạo chi tiết đơn hàng: {str(e)}")
            raise

    def _get_prestashop_option_id(self, attribute):
        """Get PrestaShop attribute (option) ID"""
        prestashop = self.shop_id.backend_id._get_prestashop_client()

        try:
            # Tìm attribute theo tên
            filters = {'filter[name]': str(attribute.name)}
            result = prestashop.get('product_options', options=filters)
            existing_options = result.findall('.//product_option')

            if existing_options:
                return existing_options[0].get('id')
            return None

        except Exception as e:
            _logger.error(f"Error getting PrestaShop option ID: {str(e)}")
            return None

    def _get_prestashop_option_value_id(self, value, option_id):
        """Get PrestaShop attribute value ID"""
        prestashop = self.shop_id.backend_id._get_prestashop_client()

        try:
            # Tìm value theo tên và option ID
            filters = {
                'filter[id_attribute_group]': str(option_id),
                'filter[name]': str(value.name)
            }
            result = prestashop.get('product_option_values', options=filters)
            existing_values = result.findall('.//product_option_value')

            if existing_values:
                return existing_values[0].get('id')
            return None

        except Exception as e:
            _logger.error(f"Error getting PrestaShop option value ID: {str(e)}")
            return None

    def _get_or_create_partner(self, order_data):
        """
        Tìm hoặc tạo khách hàng
        """
        try:
            # Tìm khách hàng PrestaShop
            customer_id = order_data.get('id_customer')
            existing_partner = self.env['prestashop.res.partner'].search([
                ('shop_id', '=', self.shop_id.id),
                ('prestashop_id', '=', customer_id)
            ], limit=1)

            if existing_partner:
                return existing_partner.odoo_id

            # Nếu chưa có, tạo khách hàng mới
            customer_info = self._get_customer_details(customer_id)

            partner = self.env['res.partner'].create({
                'name': customer_info.get('name', 'Khách PrestaShop'),
                'email': customer_info.get('email', ''),
            })

            # Tạo liên kết PrestaShop
            self.env['prestashop.res.partner'].create({
                'odoo_id': partner.id,
                'prestashop_id': customer_id,
                'prestashop_email': customer_info.get('email', ''),
                'shop_id': self.shop_id.id,
            })

            return partner

        except Exception as e:
            _logger.error(f"Lỗi tạo/tìm khách hàng: {str(e)}")
            raise

    def _get_customer_details(self, customer_id):
        """
        Lấy chi tiết khách hàng từ PrestaShop
        """
        try:
            prestashop = self.shop_id.backend_id._get_prestashop_client()
            customer_xml = prestashop.get('customers', customer_id)

            customer = customer_xml.find('.//customer')
            if customer is not None:
                firstname = customer.find('firstname')
                lastname = customer.find('lastname')
                email = customer.find('email')

                # Lấy text từ các elements, với giá trị mặc định là ''
                firstname_text = firstname.text if firstname is not None else ''
                lastname_text = lastname.text if lastname is not None else ''
                email_text = email.text if email is not None else ''

                return {
                    'name': f"{firstname_text} {lastname_text}".strip(),
                    'email': email_text
                }
            return {}
        except Exception as e:
            _logger.error(f"Lỗi lấy thông tin khách hàng: {str(e)}")
            return {}


    def action_sync_orders(self):
        """
        Hành động đồng bộ đơn hàng từ giao diện
        """
        for record in self:
            try:
                record.sync_orders_from_prestashop()
            except Exception as e:
                # Hiển thị thông báo lỗi
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Lỗi Đồng Bộ',
                        'message': str(e),
                        'type': 'danger',
                        'sticky': True,
                    }
                }

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Đồng Bộ Thành Công',
                'message': 'Đã đồng bộ đơn hàng từ PrestaShop',
                'type': 'success',
                'sticky': False,
            }
        }

    # def create_cron_job(self):
    #     """
    #     Create a scheduled action for automatic order synchronization
    #     """
    #     return self.env['ir.cron'].create({
    #         'name': 'Synchronize PrestaShop Orders',
    #         'model_id': self.env.ref('your_module.model_prestashop_order_sync_service').id,
    #         'state': 'code',
    #         'code': 'model.schedule_prestashop_order_synchronization()',
    #         'interval_number': 1,
    #         'interval_type': 'hours',
    #         'numbercall': -1,  # Unlimited calls
    #         'doall': False,
    #     })