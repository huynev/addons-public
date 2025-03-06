# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
import datetime
import logging
import hashlib
import hmac
import json
import time
import requests
from urllib.parse import urlencode
from datetime import timedelta

from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class ShopeeBackend(models.Model):
    _name = 'shopee.backend'
    _description = 'Shopee Backend'
    _inherit = 'connector.backend'

    name = fields.Char('Name', required=True)
    shop_id = fields.Char('Shopee Shop ID', required=True)
    partner_id = fields.Char('Partner ID', required=True)
    partner_key = fields.Char('Partner Key', required=True)
    code = fields.Char(string='Code')
    access_token = fields.Char(string='Access Token', required=True)
    refresh_token = fields.Char(string='Refresh Token')
    token_expire_time = fields.Datetime(string='Token Expiration Time')
    api_url = fields.Char('API URL', required=True, default='https://partner.shopeemobile.com')
    warehouse_id = fields.Many2one('stock.warehouse', 'Warehouse', required=True)
    location_id = fields.Char(string='location_id in Shopee', required=True)
    company_id = fields.Many2one('res.company', 'Company', required=True, default=lambda self: self.env.company)
    pricelist_id = fields.Many2one(
        'product.pricelist',
        string='Bảng Giá Mặc Định',
        required=True,
        help='Bảng giá được sử dụng để xuất giá sản phẩm sang PrestaShop'
    )
    push_url = fields.Char(
        string='Push URL',
        help='URL để nhận thông báo push từ Shopee (phải có thể truy cập công khai)',
    )

    def register_push_url(self):
        """Đăng ký Push URL với API Shopee"""
        self.ensure_one()

        if not self.push_url:
            raise UserError(_("Push URL chưa được cấu hình"))

        # Sử dụng API Shopee để đăng ký Push URL
        api = self._get_api()
        response = api.register_push_url(
            url=self.push_url
        )

        if response.get('error'):
            raise UserError(_(f"Không thể đăng ký Push URL: {response.get('error')}"))

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Thành công"),
                'message': _("Đã đăng ký Push URL thành công"),
                'sticky': False,
            }
        }
    import_orders_from_date = fields.Datetime('Import Orders From Date')

    def check_connection(self):
        """Check connection with Shopee API"""
        self.ensure_one()
        with self.work_on('shopee.backend') as work:
            adapter = work.component(usage='backend.adapter')
            try:
                result = adapter.call('/api/v2/shop/get_shop_info')
                if result and not result.get('error'):
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': 'Success',
                            'message': 'Successfully connected to Shopee API',
                            'type': 'success',
                        }
                    }
                else:
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': 'Error',
                            'message': result.get('error', 'Failed to connect to Shopee API'),
                            'type': 'danger',
                        }
                    }
            except Exception as e:
                _logger.error("Shopee connection error: %s", str(e))
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Error',
                        'message': str(e),
                        'type': 'danger',
                    }
                }

    def import_products_batch(self, since_date=None):
        """Schedule import of products from Shopee"""
        for backend in self:
            backend.with_delay(channel='root.shopee').import_products_batch_job(since_date)
        return True

    def import_products_batch_job(self, since_date=None):
        """Import products from Shopee using job"""
        return self.env['shopee.product.template'].import_batch(self, since_date=since_date)

    def import_orders_batch(self, since_date=None):
        """Schedule import of orders from Shopee"""
        for backend in self:
            backend.with_delay(channel='root.shopee').import_orders_batch_job(since_date)
        return True

    def import_orders_batch_job(self, since_date=None):
        """Import orders from Shopee using job"""
        return self.env['shopee.sale.order'].import_batch(self, since_date=since_date)

    def get_access_token(self, code, shop_id=None, main_account_id=None):
        """Get access token with code"""
        self.ensure_one()
        with self.work_on('shopee.backend') as work:
            adapter = work.component(usage='backend.adapter')
            return adapter.get_access_token(code, shop_id, main_account_id)

    def refresh_access_token(self):
        """Refresh access token"""
        self.ensure_one()
        with self.work_on('shopee.backend') as work:
            adapter = work.component(usage='backend.adapter')
            return adapter.refresh_access_token()

    def check_and_refresh_token(self):
        """Check and refresh token if needed"""
        if not self.token_expire_time:
            return True

        if self.token_expire_time <= datetime.datetime.now() + timedelta(minutes=30):
            # Token sắp hết hạn, làm mới
            return self.refresh_access_token()

        # Token vẫn còn hiệu lực
        return True

    @api.model
    def _scheduler_import_products(self):
        """Scheduler method to import products"""
        for backend in self.search([]):
            backend.import_products_batch()

    @api.model
    def _scheduler_import_orders(self):
        """Scheduler method to import orders"""
        for backend in self.search([]):
            backend.import_orders_batch()

    @api.model
    def _scheduler_update_stock(self):
        """Scheduler method to update stock"""
        products = self.env['shopee.product.template'].search([])
        for product in products:
            product.with_delay(channel='root.shopee').export_inventory_job()

    def import_categories(self):
        """Import categories from Shopee"""
        self.ensure_one()
        self.env['shopee.category'].import_batch(self)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Success',
                'message': 'Shopee categories import started',
                'type': 'success',
            }
        }

    def fetch_location_id(self):
        """Lấy location_id từ API Shopee và lưu vào trường location_id"""
        self.ensure_one()

        with self.work_on('shopee.backend') as work:
            adapter = work.component(usage='backend.adapter')

            # Gọi API get_warehouse_detail
            warehouses = adapter.get_warehouse_detail()

            if not warehouses:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Thông báo'),
                        'message': _('Không tìm thấy warehouse nào. Không cần thiết lập location_id.'),
                        'type': 'info',
                    }
                }

            # Ưu tiên warehouse mặc định
            location_id = None
            for warehouse in warehouses:
                if warehouse.get('default_warehouse', False):
                    location_id = warehouse.get('location_id')
                    break

            # Nếu không có warehouse mặc định, dùng warehouse đầu tiên
            if not location_id and warehouses:
                location_id = warehouses[0].get('location_id')

            if location_id:
                self.write({'location_id': location_id})
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Thành công'),
                        'message': _('Đã cập nhật location_id thành: %s') % location_id,
                        'type': 'success',
                    }
                }
            else:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Cảnh báo'),
                        'message': _('Không thể lấy location_id từ warehouse.'),
                        'type': 'warning',
                    }
                }