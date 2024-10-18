from odoo import models, fields, api, _
import requests
import json
from datetime import datetime, timedelta
import hmac
import hashlib
import time
import logging

from odoo.exceptions import ValidationError, UserError

_logger = logging.getLogger(__name__)


class TikTokShop(models.Model):
    _name = 'tiktok.shop'
    _description = 'TikTok Shop Integration'

    name = fields.Char(string='Name', required=True)
    app_key = fields.Char(string='App Key', required=True)
    app_secret = fields.Char(string='App Secret', required=True)
    access_token = fields.Char(string='Access Token', required=True)
    shop_id = fields.Char(string='Shop ID', required=True)
    shop_cipher = fields.Char(string='shop_cipher', required=True)
    tiktok_warehouse_id = fields.Many2one('stock.warehouse', string='TikTok Warehouse', required=True)
    company_warehouse_id = fields.Many2one('stock.warehouse', string='Company Warehouse', required=True)
    default_transfer_quantity = fields.Integer(string='Default Transfer Quantity', default=10)
    warehouse_id_in_tiktok = fields.Char(string='warehouse_id in tiktok', required=True)
    tiktok_pricelist_id = fields.Many2one('product.pricelist', string='TikTok Pricelist',
                                          help='Pricelist to use when publishing products to TikTok')
    save_mode = fields.Selection([
        ('AS_DRAFT', 'As Draft'),
        ('LISTING', 'Listing')
    ], string='Save Mode', default='AS_DRAFT', required=True,
        help='AS_DRAFT: Save as draft, LISTING: Directly list the product')

    order_status = fields.Selection([
        ('UNPAID', 'Unpaid'),
        ('ON_HOLD', 'On Hold'),
        ('PARTIALLY_SHIPPING', 'Partially Shipping'),
        ('AWAITING_SHIPMENT', 'Awaiting Shipment'),
        ('AWAITING_COLLECTION', 'Awaiting Collection'),
        ('IN_TRANSIT', 'In Transit'),
        ('DELIVERED', 'Delivered'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled')
    ], string='Order Status for Sync', default='AWAITING_SHIPMENT', required=True,
        help='Status of orders to sync from TikTok Shop')

    last_sync_time = fields.Datetime(string='Last Sync Time')

    def _ensure_internal_picking_types(self):
        PickingType = self.env['stock.picking.type']

        # Từ công ty đến TikTok
        self._create_picking_type_if_not_exists(
            PickingType,
            self.company_warehouse_id,
            self.tiktok_warehouse_id,
            'Company to TikTok'
        )

        # Từ TikTok đến công ty
        self._create_picking_type_if_not_exists(
            PickingType,
            self.tiktok_warehouse_id,
            self.company_warehouse_id,
            'TikTok to Company'
        )

    def _create_picking_type_if_not_exists(self, PickingType, src_warehouse, dest_warehouse, name_suffix):
        existing = PickingType.search([
            ('code', '=', 'internal'),
            ('default_location_src_id', '=', src_warehouse.lot_stock_id.id),
            ('default_location_dest_id', '=', dest_warehouse.lot_stock_id.id)
        ], limit=1)

        if not existing:
            sequence = self.env['ir.sequence'].create({
                'name': f'Sequence for {name_suffix}',
                'prefix': f'{src_warehouse.code}2{dest_warehouse.code}/',
                'padding': 5
            })
            PickingType.create({
                'name': f'Internal Transfer: {name_suffix}',
                'code': 'internal',
                'sequence_id': sequence.id,
                'sequence_code': f'{src_warehouse.code}2{dest_warehouse.code}',
                'default_location_src_id': src_warehouse.lot_stock_id.id,
                'default_location_dest_id': dest_warehouse.lot_stock_id.id,
                'warehouse_id': src_warehouse.id,
            })

    @api.model
    def create(self, vals):
        record = super(TikTokShop, self).create(vals)
        if not record.tiktok_warehouse_id:
            record.tiktok_warehouse_id = record._create_tiktok_warehouse()
        if not record.company_warehouse_id:
            record.company_warehouse_id = self.env['stock.warehouse'].search([], limit=1)
        record._ensure_internal_picking_types()
        return record

    def write(self, vals):
        res = super(TikTokShop, self).write(vals)
        if not self.tiktok_warehouse_id:
            self.tiktok_warehouse_id = self._create_tiktok_warehouse()
        if not self.company_warehouse_id:
            self.company_warehouse_id = self.env['stock.warehouse'].search([], limit=1)
        return res

    def _create_tiktok_warehouse(self):
        Warehouse = self.env['stock.warehouse']

        # Tạo mã kho duy nhất
        code = f'TT{self.id}'
        while Warehouse.search([('code', '=', code)]):
            code = f'{code}X'

        warehouse = Warehouse.create({
            'name': f'TikTok Warehouse - {self.name}',
            'code': code,
            'company_id': self.env.company.id,
        })
        return warehouse

    def _get_signature(self, path, params, body=None):
        # Lấy app secret từ cấu hình
        secret = self.app_secret

        # Sắp xếp params theo key
        sorted_params = dict(sorted(params.items()))

        # Loại bỏ 'sign' và 'access_token' khỏi params
        sorted_params.pop('sign', None)
        sorted_params.pop('access_token', None)

        # Tạo chuỗi ký
        sign_string = secret + path
        for key, value in sorted_params.items():
            sign_string += f"{key}{value}"

        # Thêm body vào chuỗi ký nếu có
        if body:
            if isinstance(body, dict):
                body = json.dumps(body)
            sign_string += body

        # Thêm secret vào cuối chuỗi
        sign_string += secret

        # Tạo chữ ký HMAC-SHA256
        signature = hmac.new(
            secret.encode(),
            sign_string.encode(),
            hashlib.sha256
        ).hexdigest()

        return signature

    def _make_request(self, path, method='GET', params=None, json_data=None):
        base_url = "https://open-api.tiktokglobalshop.com"
        url = f"{base_url}{path}"

        timestamp = int(time.time())
        common_params = {
            'app_key': self.app_key,
            'timestamp': timestamp,
            'shop_id': self.shop_id,
            'shop_cipher': self.shop_cipher,
        }

        if params:
            common_params.update(params)

        # Tạo chữ ký
        signature = self._get_signature(path, common_params, json_data)
        common_params['sign'] = signature
        headers = {
            'Content-Type': 'application/json',
            'x-tts-access-token': self.access_token,
        }

        try:
            _logger.info(f"Making {method} request to {url}")
            _logger.info(f"Params: {common_params}")
            if json_data:
                _logger.info(f"JSON Data: {json_data}")

            if method == 'GET':
                response = requests.get(url, params=common_params, headers=headers)
            elif method in ['POST', 'PUT']:
                response = requests.request(method, url, params=common_params, headers=headers, json=json_data)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            _logger.info(f"Response status code: {response.status_code}")
            _logger.info(f"Response content: {response.text}")

            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            _logger.error(f"API call to {path} failed: {str(e)}")
            self.env['tiktok.shop.log'].create({
                'message': f"API call to {path} failed",
                'response': str(e)
            })
            return None

    def sync_orders(self):
        path = "/order/202309/orders/search"
        start_time = self.env.context.get('start_time', int((datetime.now() - timedelta(days=7)).timestamp()))
        end_time = self.env.context.get('end_time', int(datetime.now().timestamp()))
        order_status = self.env.context.get('order_status', self.order_status)

        params = {
            'page_size': 50,
        }

        json_data = {
            "order_status": order_status,
            'create_time_ge': start_time,
            'create_time_lt': end_time,
        }
        response = self._make_request(path, method='POST', params=params, json_data=json_data)
        total_orders = 0
        if response and response.get('code') == 0:
            _logger.info(f"Full response from TikTok API: {response}")

            orders = response.get('data', {}).get('orders', [])
            total_orders += len(orders)

            if not orders:
                _logger.warning("No orders found in the initial response")
            else:
                for order in orders:
                    self._create_or_update_order(order)

            # # Handle pagination if needed
            # next_page_token = response.get('data', {}).get('next_page_token')
            # while next_page_token:
            #     params['page_token'] = next_page_token
            #     response = self._make_request(path, method='POST', params=params)
            #     if response and response.get('code') == 0:
            #         orders = response.get('data', {}).get('orders', [])
            #         total_orders += len(orders)
            #         if not orders:
            #             _logger.warning("No orders found in the paginated response")
            #             break
            #         for order in orders:
            #             self._create_or_update_order(order)
            #         next_page_token = response.get('data', {}).get('next_page_token')
            #     else:
            #         _logger.error(f"Error in paginated request: {response}")
            #         break
        else:
            _logger.error(f"Error in initial request: {response}")
            raise UserError(_("Failed to sync orders from TikTok. Please check the logs for more details."))

        self.last_sync_time = fields.Datetime.now()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('TikTok Order Sync'),
                'message': _('%d orders have been synchronized from TikTok.') % total_orders,
                'type': 'info',
                'sticky': False,
            }
        }

    def _create_or_update_order(self, order_data):
        existing_order = self.env['sale.order'].search([('tiktok_order_id', '=', order_data['id'])], limit=1)
        order_vals = self._prepare_sale_order_vals(order_data)
        order_vals['warehouse_id'] = self.tiktok_warehouse_id.id
        if existing_order:
            try:
                existing_order.write({
                    'tiktok_status': order_data['status'],
                    'tiktok_order_id': order_data['id'],
                    'tiktok_user_id': order_data['user_id'],
                })
                _logger.info(f"Updated order {existing_order.name} from TikTok order {order_data['id']}")
            except ValidationError as e:
                _logger.error(f"Failed to update order {order_data['id']}: {str(e)}")
        else:
            try:
                new_order = self.env['sale.order'].create(order_vals)
                _logger.info(f"Created new order {new_order.name} from TikTok order {order_data['id']}")
            except ValidationError as e:
                _logger.error(f"Failed to create order for TikTok order {order_data['id']}: {str(e)}")

    def _prepare_sale_order_vals(self, order_data):
        partner = self._get_or_create_customer(order_data['user_id'], order_data.get('recipient_address', {}))
        order_lines = []
        for item in order_data['line_items']:
            line = self._prepare_sale_order_line(item)
            if line:
                order_lines.append((0, 0, line))

        return {
            'partner_id': partner.id,
            'tiktok_order_id': order_data['id'],
            'tiktok_user_id': order_data['user_id'],
            'date_order': datetime.fromtimestamp(order_data['create_time']),
            'state': self._map_order_status(order_data['status']),
            'delivery_status': self._map_order_delivery_status(order_data['status']),
            'order_line': order_lines,
            'amount_total': float(order_data['payment']['total_amount']),
            'pricelist_id': 1,
        }

    def _prepare_sale_order_line(self, item):
        product = self._get_or_create_product_by_sku(item['seller_sku'], item)
        if product:
            values = {
                'product_id': product.id,
                'product_uom_qty': 1,
                'price_unit': float(item['sale_price']),
                'tiktok_order_line_id': item['id'],
                'tax_id': []
            }
            return values
        else:
            raise UserError(_("Failed to create or find product with SKU: %s") % item['seller_sku'])

    def _get_or_create_product_by_sku(self, sku, item):
        product = self.env['product.product'].sudo().search([('default_code', '=', sku)], limit=1)
        if not product:
            product_vals = self._prepare_product_vals(sku, item)
            product = self.env['product.product'].sudo().create(product_vals)
        else:
            product.write({
                'tiktok_product_id': item['product_id']
            })

        # Cập nhật TikTok Product ID nếu có
        if 'tiktok_product_id' in item:
            try:
                product.product_tmpl_id.write({'tiktok_product_id': item['tiktok_product_id']})
                _logger.info(f"Updated TikTok Product ID for SKU {sku}: {item['tiktok_product_id']}")
            except Exception as e:
                _logger.error(f"Failed to update TikTok Product ID for SKU {sku}: {str(e)}")

        return product

    def _prepare_product_vals(self, sku, item):
        return {
            'name': item.get('product_name', 'TikTok Product'),
            'default_code': sku,
            'type': 'product',
            'sale_ok': True,
            'purchase_ok': False,
            'can_sell_on_tiktok': True,
            'list_price': float(item['sale_price']),
            'tiktok_product_id': item.get('tiktok_product_id'),
        }

    def _get_or_create_customer(self, tiktok_user_id, address_data=None):
        partner = self.env['res.partner'].search([('tiktok_user_id', '=', tiktok_user_id)], limit=1)
        if not address_data:
            address_data = {}
        ttest = address_data.get('address_detail')
        partner_vals = {
            'name': address_data.get('name', f'TikTok Customer {tiktok_user_id}'),
            'tiktok_user_id': tiktok_user_id,
            'street': ttest,
            'street2': address_data.get('full_address', ''),
            'city': address_data.get('city', ''),
            'state_id': self._get_state_id(address_data.get('state', '')),
            'zip': address_data.get('zipcode', ''),
            'country_id': self._get_country_id(address_data.get('region_code', '')),
            'phone': address_data.get('phone_number', ''),
            'mobile': address_data.get('phone_number', ''),
        }

        if partner:
            partner.write(partner_vals)
        else:
            partner = self.env['res.partner'].create(partner_vals)

        return partner

    def _get_state_id(self, state_name):
        if not state_name:
            return False
        state = self.env['res.country.state'].search([('name', 'ilike', state_name)], limit=1)
        return state.id if state else False

    def _get_country_id(self, country_code):
        if not country_code:
            return False
        country = self.env['res.country'].search([('code', '=', country_code.upper())], limit=1)
        return country.id if country else False

    def _get_product_by_sku(self, seller_sku):
        product = self.env['product.product'].search([('default_code', '=', seller_sku)], limit=1)
        if product:
            existing_product = product.product_tmpl_id._search_tiktok_product_by_sku(self, seller_sku)
            if existing_product:
                product.tiktok_product_id = existing_product.get('id')
            return product
        product_template = self.env['product.template'].search([('default_code', '=', seller_sku)], limit=1)
        if product_template:
            existing_product = product_template._search_tiktok_product_by_sku(self, seller_sku)
            if existing_product:
                product_template.tiktok_product_id = existing_product.get('id')
            return product_template

    def _map_order_status(self, status):
        status_mapping = {
            'UNPAID': 'draft',
            'AWAITING_SHIPMENT': 'draft',
            'AWAITING_COLLECTION': 'draft',
            'IN_TRANSIT': 'sale',
            'DELIVERED': 'sale',
            'COMPLETED': 'sale',
            'CANCELLED': 'cancel',
        }
        return status_mapping.get(status, 'draft')

    def _map_order_delivery_status(self, status):
        status_mapping = {
            'UNPAID': '',
            'AWAITING_SHIPMENT': '',
            'AWAITING_COLLECTION': '',
            'IN_TRANSIT': '',
            'DELIVERED': '',
            'COMPLETED': '',
            'CANCELLED': '',
        }
        return status_mapping.get(status, 'draft')

    def sync_inventory(self, tiktok_product_id=None, tiktok_sku_id=None):
        self.ensure_one()
        path = "/api/products/stocks"

        params = {
            'app_key': self.app_key,
            'timestamp': int(time.time()),
            'shop_id': self.shop_id,
            'access_token': self.access_token,
        }

        if tiktok_product_id:
            products = self.env['product.product'].search([('tiktok_product_id', '=', tiktok_product_id)])
        elif tiktok_sku_id:
            products = self.env['product.product'].search([('tiktok_sku_id', '=', tiktok_sku_id)])
        else:
            products = self.env['product.product'].search([('tiktok_product_id', '!=', False)])

        updated_products = 0
        failed_products = 0

        for product in products:
            tiktok_qty = self._get_tiktok_stock_quantity(product)
            data = {
                'product_id': product.tiktok_product_id,
                'skus': [{
                    'id': product.tiktok_sku_id,
                    'stock_infos': [{
                        'warehouse_id': self.warehouse_id_in_tiktok,
                        'available_stock': tiktok_qty,
                    }]
                }]
            }
            response = self._make_request(path, method='PUT', params=params, json_data=data)
            if response and response.get('code') == 0:
                _logger.info(f"Successfully updated stock for product {product.name} on TikTok")
                updated_products += 1
            else:
                _logger.error(f"Failed to update stock for product {product.name} on TikTok: {response.get('message')}")
                failed_products += 1

        # Hiển thị thông báo cho người dùng
        message = f"Updated stock for {updated_products} products on TikTok."
        if failed_products > 0:
            message += f" Failed to update {failed_products} products."

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Stock Update'),
                'message': message,
                'type': 'success' if failed_products == 0 else 'warning',
            }
        }

    def _get_tiktok_stock_quantity(self, product):
        quants = self.env['stock.quant'].search([
            ('product_id', '=', product.id),
            ('location_id', '=', self.tiktok_warehouse_id.lot_stock_id.id)
        ])
        return int(sum(quants.mapped('quantity')))

    def transfer_products_to_tiktok_warehouse(self):
        StockPicking = self.env['stock.picking']
        StockMove = self.env['stock.move']

        # Tìm hoặc tạo loại điều chuyển phù hợp
        picking_type = self._get_or_create_picking_type()

        picking = StockPicking.create({
            'picking_type_id': picking_type.id,
            'location_id': self.company_warehouse_id.lot_stock_id.id,
            'location_dest_id': self.tiktok_warehouse_id.lot_stock_id.id,
        })

        products = self.env['product.product'].search([('type', '=', 'product'), ('can_sell_on_tiktok', '=', True)])
        for product in products:
            StockMove.create({
                'name': product.name,
                'product_id': product.id,
                'product_uom_qty': self.default_transfer_quantity,
                'product_uom': product.uom_id.id,
                'picking_id': picking.id,
                'location_id': self.company_warehouse_id.lot_stock_id.id,
                'location_dest_id': self.tiktok_warehouse_id.lot_stock_id.id,
            })

        picking.action_confirm()
        picking.action_assign()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Transfer to TikTok Warehouse'),
            'res_model': 'stock.picking',
            'res_id': picking.id,
            'view_mode': 'form',
            'view_type': 'form',
            'target': 'current',
        }

    def _get_or_create_picking_type(self):
        PickingType = self.env['stock.picking.type']

        # Tìm kiếm loại điều chuyển hiện có
        picking_type = PickingType.search([
            ('code', '=', 'internal'),
            ('default_location_src_id', '=', self.company_warehouse_id.lot_stock_id.id),
            ('default_location_dest_id', '=', self.tiktok_warehouse_id.lot_stock_id.id)
        ], limit=1)

        if not picking_type:
            # Nếu không tìm thấy, tạo mới
            sequence = self.env['ir.sequence'].create({
                'name': f'Sequence for TikTok transfer {self.company_warehouse_id.name} to {self.tiktok_warehouse_id.name}',
                'prefix': 'TT/',
                'padding': 5
            })
            picking_type = PickingType.create({
                'name': f'Transfer to TikTok Warehouse {self.tiktok_warehouse_id.name}',
                'code': 'internal',
                'sequence_id': sequence.id,
                'sequence_code': f'TT.{self.company_warehouse_id.code}.{self.tiktok_warehouse_id.code}',
                # Thêm dòng này
                'default_location_src_id': self.company_warehouse_id.lot_stock_id.id,
                'default_location_dest_id': self.tiktok_warehouse_id.lot_stock_id.id,
                'warehouse_id': self.company_warehouse_id.id,
            })

        return picking_type

    def create_product_on_tiktok(self, product_data):
        path = "/product/202309/products"
        params = {
            'app_key': self.app_key,
            'timestamp': int(time.time()),
            'shop_id': self.shop_id,
            'access_token': self.access_token,
        }

        response = self._make_request(path, method='POST', params=params, json_data=product_data)
        return response

    def action_sync_categories(self):
        self.ensure_one()
        categories = self._get_tiktok_categories()
        if categories:
            self._create_or_update_categories(categories)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _('TikTok categories have been synchronized.'),
                    'type': 'success',
                }
            }
        else:
            raise UserError(_("Failed to retrieve categories from TikTok."))

    def _get_tiktok_categories(self):
        path = "/product/202309/categories"
        response = self._make_request(path, method='GET')
        if response and response.get('code') == 0:
            return response.get('data', {}).get('categories', [])
        return []

    def _create_or_update_categories(self, categories):
        TikTokCategory = self.env['tiktok.category']
        for category in categories:
            existing = TikTokCategory.search([('tiktok_category_id', '=', category['id'])], limit=1)
            if category['parent_id']:
                parent = TikTokCategory.search([('tiktok_category_id', '=', category['parent_id'])], limit=1)

            if existing:
                existing.write({
                    'name': parent.name + ' / ' + category['local_name'] if parent else category['local_name'],
                    'parent_id': parent.id if parent else '',
                    'is_leaf': category.get('is_leaf', False),
                })
            else:
                new_category = TikTokCategory.create({
                    'name': parent.name + ' / ' + category['local_name'] if parent else category['local_name'],
                    'tiktok_category_id': category['id'],
                    'parent_id': parent.id if parent else '',
                    'is_leaf': category.get('is_leaf', False),
                })

class TikTokShopLog(models.Model):
    _name = 'tiktok.shop.log'
    _description = 'TikTok Shop Log'

    message = fields.Text(string='Message')
    response = fields.Text(string='API Response')
    create_date = fields.Datetime(string='Created On', default=fields.Datetime.now)

