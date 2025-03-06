# -*- coding: utf-8 -*-
from odoo.addons.component.core import Component
from odoo.addons.connector.components.mapper import mapping, external_to_m2o, only_create
import datetime
from odoo import fields
import logging

_logger = logging.getLogger(__name__)


class ShopeeBaseMapper(Component):
    _name = 'shopee.base.mapper'
    _inherit = ['base.shopee.connector', 'base.mapper']
    _usage = 'mapper'


class ShopeeImportMapper(Component):
    _name = 'shopee.import.mapper'
    _inherit = ['base.shopee.connector', 'base.import.mapper']
    _usage = 'import.mapper'


class ShopeeExportMapper(Component):
    _name = 'shopee.export.mapper'
    _inherit = ['base.shopee.connector', 'base.export.mapper']
    _usage = 'export.mapper'


class ShopeeProductImportMapper(Component):
    _name = 'shopee.product.import.mapper'
    _inherit = 'shopee.import.mapper'
    _apply_on = 'shopee.product.template'

    direct = [
        ('item_id', 'external_id'),
        ('item_name', 'shopee_name'),
        ('description', 'shopee_description'),
        ('price', 'shopee_price'),
        ('stock', 'shopee_stock'),
        ('category_id', 'shopee_category_id'),
    ]

    @mapping
    def backend_id(self, record):
        return {'backend_id': self.backend_record.id}

    @only_create
    @mapping
    def odoo_id(self, record):
        """Create or link to an existing product"""
        product = self.env['product.template'].search([
            ('default_code', '=', record.get('item_sku')),
        ], limit=1)
        if product:
            return {'odoo_id': product.id}

        return {
            'odoo_id': self.env['product.template'].create({
                'name': record.get('item_name'),
                'default_code': record.get('item_sku'),
                'type': 'product',
                'sale_ok': True,
                'purchase_ok': True,
                'list_price': record.get('price'),
            }).id
        }

    @mapping
    def shopee_category(self, record):
        category_id = record.get('category_id')
        if not category_id:
            return {}

        category = self.env['shopee.category'].search([
            ('backend_id', '=', self.backend_record.id),
            ('shopee_category_id', '=', str(category_id))
        ], limit=1)

        if category:
            return {'shopee_category': category.id}
        return {}

    @mapping
    def image_ids(self, record):
        """Map product images"""
        images = []
        # Cần chỉnh sửa logic lấy images cho phù hợp với API Shopee
        image_info = record.get('image', {})
        item_images = image_info.get('image_url_list', []) if image_info else []

        for position, image_url in enumerate(item_images):
            images.append((0, 0, {
                'image_url': image_url,
                'position': position,
            }))
        return {'shopee_image_ids': images}


class ShopeeProductExportMapper(Component):
    _name = 'shopee.product.export.mapper'
    _inherit = 'shopee.export.mapper'
    _apply_on = 'shopee.product.template'

    @mapping
    def item_name(self, record):
        return {'item_name': record.shopee_name or record.odoo_id.name}

    @mapping
    def item_id(self, record):
        return {'item_id': int(record.external_id) if record.external_id else None}

    @mapping
    def item_sku(self, record):
        return {'item_sku': record.odoo_id.default_code or ''}

    @mapping
    def price(self, record):
        return {'price': record.shopee_price or record.odoo_id.list_price}

    @mapping
    def description(self, record):
        return {'description': record.shopee_description or record.odoo_id.description_sale or ''}

    # @mapping
    # def stock(self, record):
    #     return {'stock': int(record.shopee_stock or record.odoo_id.qty_available)}

    @mapping
    def category_id(self, record):
        return {'category_id': record.shopee_category_id}

class ShopeeCategoryMapper(Component):
    _name = 'shopee.category.mapper'
    _inherit = 'shopee.import.mapper'
    _apply_on = 'shopee.category'

    direct = [
        ('category_id', 'shopee_category_id'),
        ('category_name', 'name'),
        ('has_children', 'is_leaf')
    ]

    @mapping
    def is_leaf(self, record):
        return {'is_leaf': not record.get('has_children', False)}

    @mapping
    def backend_id(self, record):
        return {'backend_id': self.backend_record.id}

    @mapping
    def parent_id(self, record):
        if not record.get('parent_id'):
            return {}

        parent = self.env['shopee.category'].search([
            ('backend_id', '=', self.backend_record.id),
            ('shopee_category_id', '=', str(record['parent_id']))
        ], limit=1)

        if parent:
            return {'parent_id': parent.id}
        return {}


class ShopeeOrderImportMapper(Component):
    _name = 'shopee.order.import.mapper'
    _inherit = 'shopee.import.mapper'
    _apply_on = 'shopee.sale.order'

    direct = [
        ('order_sn', 'shopee_order_sn'),
        ('order_status', 'shopee_order_status'),
        ('payment_method', 'shopee_payment_method'),
    ]

    @mapping
    def shopee_order_date(self, record):
        """Map create_time to shopee_order_date"""
        if 'create_time' in record:
            # Nếu create_time đã được chuyển đổi thành datetime
            if isinstance(record['create_time'], datetime.datetime):
                return {'shopee_order_date': record['create_time']}

            # Nếu create_time là timestamp
            elif record['create_time']:
                try:
                    timestamp = int(record['create_time'])
                    if timestamp > 0:
                        # Kiểm tra xem timestamp có phải là milliseconds không
                        if timestamp > 100000000000:  # Có vẻ là milliseconds
                            timestamp = timestamp / 1000

                        dt = datetime.datetime.fromtimestamp(timestamp)
                        return {'shopee_order_date': dt}
                except Exception as e:
                    _logger.warning(f"Error converting create_time: {e}")

        # Giá trị mặc định nếu không thể chuyển đổi
        return {'shopee_order_date': fields.Datetime.now()}

    @mapping
    def backend_id(self, record):
        return {'backend_id': self.backend_record.id}

    @mapping
    def shipping_info(self, record):
        """Map shipping information"""
        shipping_info = record.get('shipping_detail', {})
        return {
            'shopee_shipping_carrier': shipping_info.get('shipping_carrier'),
            'shopee_tracking_number': shipping_info.get('tracking_number')
        }

    @mapping
    def odoo_id(self, record):
        """Create Odoo sale order"""
        partner = self._get_or_create_partner(record)

        sale_order_vals = {
            'partner_id': partner.id,
            'date_order': fields.Datetime.from_string(record.get('create_time')) or fields.Datetime.now(),
            'state': 'draft',
            'client_order_ref': record.get('order_sn'),
            'pricelist_id': 1,
        }

        sale_order = self.env['sale.order'].create(sale_order_vals)
        return {'odoo_id': sale_order.id}

    def _get_or_create_partner(self, record):
        """Get or create partner from Shopee order"""
        buyer_info = record.get('buyer_user_id', '')

        # Tìm partner Shopee đã tồn tại
        shopee_partner = self.env['shopee.res.partner'].search([
            ('shopee_user_id', '=', buyer_info),
            ('backend_id', '=', self.backend_record.id)
        ], limit=1)

        if shopee_partner:
            return shopee_partner.odoo_id

        # Tìm partner dựa trên email hoặc tên có chứa từ "Shopee"
        buyer_email = record.get('buyer_email', '')
        existing_partner = False

        # Tìm theo email trước nếu có
        if buyer_email:
            existing_partner = self.env['res.partner'].search([
                ('email', '=', buyer_email)
            ], limit=1)

        if not existing_partner:
            existing_partner = self.env['res.partner'].search([
                ('name', 'ilike', 'shopee')
            ], limit=1)

        partner_name = record.get('recipient_address', {}).get('name', f'Shopee Customer {buyer_info}')

        if existing_partner:
            # Dùng partner đã có
            partner = existing_partner
        else:
            # Tạo partner mới
            partner_vals = {
                'name': 'Shopee Customer',
                'email': buyer_email,
            }
            partner = self.env['res.partner'].create(partner_vals)

        # Tạo binding Shopee cho partner nếu chưa có
        shopee_partner_vals = {
            'odoo_id': partner.id,
            'backend_id': self.backend_record.id,
            'shopee_user_id': buyer_info,
            'shopee_username': partner_name
        }
        self.env['shopee.res.partner'].create(shopee_partner_vals)

        return partner


class ShopeeOrderLineImportMapper(Component):
    _name = 'shopee.order.line.import.mapper'
    _inherit = 'shopee.import.mapper'
    _apply_on = 'shopee.sale.order.line'

    direct = [
        ('item_id', 'shopee_item_id'),
        ('item_name', 'shopee_item_name'),
        ('item_sku', 'shopee_item_sku'),
        ('model_price', 'shopee_item_price'),
        ('model_quantity_purchased', 'shopee_item_quantity'),
    ]

    @mapping
    def backend_id(self, record):
        return {'backend_id': self.backend_record.id}

    @mapping
    def shopee_order_id(self, record):
        """Map shopee_order_id to shopee_order_id field"""
        # Đảm bảo shopee_order_id đã được xác định
        if 'shopee_order_id' in record:
            return {'shopee_order_id': record['shopee_order_id']}
        return {}

    @mapping
    def odoo_id(self, record):
        """Create Odoo sale order line"""
        # Lấy shopee.sale.order nếu shopee_order_id là ID của bản ghi đó
        if 'shopee_order_id' in record and isinstance(record['shopee_order_id'], int):
            shopee_order = self.env['shopee.sale.order'].browse(record['shopee_order_id'])

            # Kiểm tra xem shopee_order có tồn tại không
            if not shopee_order.exists():
                _logger.error(f"Shopee order with ID {record['shopee_order_id']} not found")
                return {}

            # Lấy ra sale.order từ shopee.sale.order
            odoo_order = shopee_order.odoo_id
        else:
            _logger.error(f"Invalid shopee_order_id: {record.get('shopee_order_id')}")
            return {}

        # Tìm sản phẩm trong Odoo
        item_id = record.get('item_id')
        item_sku = record.get('item_sku') or record.get('model_sku')
        item_name = record.get('item_name', f'Shopee Product {item_id}')

        product = None

        # Tìm theo SKU trước nếu có
        if item_sku:
            product = self.env['product.template'].search([
                ('default_code', '=', item_sku)
            ], limit=1)

        # Nếu không tìm thấy theo SKU, tìm theo item_id trong shopee.product.template
        if not product and item_id:
            shopee_product = self.env['shopee.product.template'].search([
                ('external_id', '=', str(item_id)),
                ('backend_id', '=', self.backend_record.id)
            ], limit=1)

            if shopee_product:
                product = shopee_product.odoo_id

        # Nếu vẫn không tìm thấy, tạo sản phẩm mới
        if not product:
            _logger.info(f"Creating new product for Shopee item {item_id}: {item_name}")

            product_vals = {
                'name': item_name,
                'default_code': item_sku or f'SP_{item_id}',
                'type': 'product',
                'sale_ok': True,
                'purchase_ok': True,
            }

            # Nếu có giá, thêm vào
            if record.get('model_price'):
                product_vals['list_price'] = float(record.get('model_price', 0.0))

            try:
                product = self.env['product.template'].create(product_vals)

                # Tạo binding Shopee cho sản phẩm mới nếu có item_id
                if item_id:
                    shopee_product_vals = {
                        'odoo_id': product.id,
                        'backend_id': self.backend_record.id,
                        'external_id': str(item_id),
                        'shopee_name': item_name,
                    }
                    self.env['shopee.product.template'].create(shopee_product_vals)
            except Exception as e:
                _logger.error(f"Error creating product for item {item_id}: {str(e)}")
                # Trả về trống nếu không thể tạo sản phẩm
                return {}

        # Lấy giá và số lượng
        item_price = float(record.get('model_price', 0.0) or record.get('model_discounted_price', 0.0) or 0.0)
        item_qty = float(record.get('model_quantity_purchased', 1))

        if item_price <= 0 and product:
            item_price = product.list_price

        # Kiểm tra lại product
        if not product or not product.id:
            _logger.error(f"Cannot proceed without a valid product for item {item_id}")
            # Tạo một sản phẩm mặc định nếu cần thiết để tránh lỗi
            default_product = self.env['product.template'].search([('default_code', '=', 'DEFAULT-SHOPEE')], limit=1)
            if not default_product:
                default_product = self.env['product.template'].create({
                    'name': 'Default Product',
                    'default_code': 'DEFAULT-SHOPEE',
                    'type': 'product',
                    'sale_ok': True,
                    'purchase_ok': True,
                    'list_price': item_price,
                })
            product = default_product

        try:
            # Tạo dòng đơn hàng
            order_line = self.env['sale.order.line'].create({
                'order_id': odoo_order.id,
                'product_id': product.id,
                'product_uom_qty': item_qty,
                'price_unit': item_price,
                'name': item_name,
            })

            if not order_line:
                _logger.error(f"Failed to create order line for item {item_id}")
                return {}

            return {'odoo_id': order_line.id}
        except Exception as e:
            _logger.error(f"Error creating order line for item {item_id}: {str(e)}")
            # Tạo một order line đơn giản với thông tin tối thiểu
            try:
                simple_line = self.env['sale.order.line'].create({
                    'order_id': odoo_order.id,
                    'product_id': product.id,
                    'name': f"Shopee Product: {item_name}",
                    'product_uom_qty': 1,
                    'price_unit': 0.0,
                })
                if simple_line:
                    return {'odoo_id': simple_line.id}
            except Exception as inner_e:
                _logger.error(f"Even simple order line creation failed: {str(inner_e)}")

            return {}