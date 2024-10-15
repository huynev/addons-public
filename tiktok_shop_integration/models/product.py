import requests

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import base64
from io import BytesIO
from PIL import Image
import time

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    tiktok_product_id = fields.Char(string='TikTok Product ID', readonly=True)
    can_sell_on_tiktok = fields.Boolean(string='Can Sell on TikTok', default=False)

    def action_set_can_sell_on_tiktok(self):
        self.write({'can_sell_on_tiktok': True})

    def action_unset_can_sell_on_tiktok(self):
        self.write({'can_sell_on_tiktok': False})

    def prepare_product_images(self, tiktok_shop):
        image_ids = []
        if self.image_1920:
            image_data = BytesIO(base64.b64decode(self.image_1920))
            image = Image.open(image_data)

            # Kiểm tra và điều chỉnh kích thước hình ảnh
            width, height = image.size
            if width < 300 or height < 300:
                image = image.resize((max(300, width), max(300, height)))
            elif width > 4000 or height > 4000:
                image = image.resize((min(4000, width), min(4000, height)))

            # Chuyển đổi sang JPEG và giảm dung lượng nếu cần
            output = BytesIO()
            image.convert('RGB').save(output, format='JPEG', quality=95, optimize=True)
            image_data = base64.b64encode(output.getvalue()).decode('utf-8')

            if len(image_data) > 5 * 1024 * 1024:  # Nếu lớn hơn 5MB
                raise UserError(_("Image size exceeds 5MB limit. Please use a smaller image."))

            image_id = self.upload_image_to_tiktok(tiktok_shop, image_data)
            if image_id:
                image_ids.append({"uri": image_id})
        return image_ids

    def action_publish_to_tiktok(self):
        self.ensure_one()
        if not self.can_sell_on_tiktok:
            raise UserError(_("This product is not marked as sellable on TikTok. Please enable it first."))

        tiktok_shop = self.env['tiktok.shop'].search([], limit=1)
        if not tiktok_shop:
            raise UserError(_("No TikTok Shop configuration found."))

        # Kiểm tra sản phẩm đã tồn tại trên TikTok chưa
        existing_product = self._check_existing_tiktok_product(tiktok_shop)
        if existing_product:
            self.tiktok_product_id = existing_product.get('id')
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("Product Already Exists"),
                    'message': _("This product already exists on TikTok Shop with ID: %s. "
                                 "Please update the existing product instead of creating a new one.") % existing_product.get(
                        'id'),
                    'type': 'warning',
                    'sticky': True,
                }
            }

        # Nếu sản phẩm chưa tồn tại, tiếp tục quá trình tạo mới
        product_data = self._prepare_tiktok_product_data(tiktok_shop)
        image_ids = self.prepare_product_images(tiktok_shop)
        if image_ids:
            params_main_images = {
                "main_images": image_ids
            }
            product_data.update(params_main_images)
        response = tiktok_shop.create_product_on_tiktok(product_data)

        if response and response.get('code') == 0:
            self.tiktok_product_id = response['data']['product_id']

            # Lưu SKU_ID cho từng variant
            for sku_data in response['data'].get('skus', []):
                variant = self.product_variant_ids.filtered(lambda v: v.default_code == sku_data.get('seller_sku'))
                if variant:
                    variant.tiktok_sku_id = sku_data.get('id')
                    variant.tiktok_product_id = self.tiktok_product_id

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("Success"),
                    'message': _("Product successfully published to TikTok Shop"),
                    'type': 'success',
                }
            }
        else:
            raise UserError(
                _("Failed to publish product to TikTok Shop: %s") % response.get('message', 'Unknown error'))

    def _prepare_tiktok_product_data(self, tiktok_shop):
        self.ensure_one()

        if not tiktok_shop.tiktok_pricelist_id:
            raise UserError(_("Please set a TikTok pricelist in TikTok Shop configuration."))

        tiktok_categories = self.env['tiktok.category'].search([
            ('odoo_category_ids', 'in', self.categ_id.id)
        ])

        if not tiktok_categories:
            raise UserError(
                _("No TikTok category mapping found for this product's category. Please set up the mapping first."))

        pricelist = tiktok_shop.tiktok_pricelist_id
        price = pricelist._get_product_price(self, 1.0, False)

        # Chọn TikTok category đầu tiên trong danh sách (hoặc bạn có thể thêm logic để chọn category phù hợp nhất)
        tiktok_category = tiktok_categories[0]

        skus = []
        if self.product_variant_ids:
            for variant in self.product_variant_ids:
                variant_price = pricelist._get_product_price(variant, 1.0, False)
                sku = {
                    "seller_sku": variant.default_code or "",
                    "original_price": str(int(variant_price)),
                    "inventory": [
                        {
                            "warehouse_id": tiktok_shop.warehouse_id_in_tiktok,
                            "quantity": 0,
                        }
                    ],
                    "price":
                        {
                            "amount": str(int(variant_price)),
                            "currency": pricelist.currency_id.name,
                        },
                }
                skus.append(sku)
        else:
            skus = [{
                "seller_sku": self.default_code or "",
                "original_price": str(int(price)),
                "inventory": [
                    {
                        "warehouse_id": tiktok_shop.warehouse_id_in_tiktok,
                        "quantity": 0,
                    }
                ],
                "price":
                    {
                        "amount": str(int(price)),
                         "currency": pricelist.currency_id.name,
                    },
            }]

        return {
            "save_mode": tiktok_shop.save_mode,
            "title": self.name,
            "description": self.description or "",
            "category_id": tiktok_category.tiktok_category_id,
            "skus": skus,
            "package_weight":
                {
                    "value": "100",
                    "unit": "KILOGRAM",
                },
        }

    def _check_existing_tiktok_product(self, tiktok_shop):
        # Kiểm tra bằng product ID nếu đã có
        if self.tiktok_product_id:
            existing_product = self._search_tiktok_product_by_id(tiktok_shop, self.tiktok_product_id)
            if existing_product:
                return existing_product

        # Kiểm tra bằng SKU
        for variant in self.product_variant_ids:
            sku = variant.default_code or str(variant.id)
            existing_product = self._search_tiktok_product_by_sku(tiktok_shop, sku)
            if existing_product:
                return existing_product

        return None

    def _search_tiktok_product_by_sku(self, tiktok_shop, sku):
        path = "/product/202312/products/search"
        params = {
            'page_size': 1,
        }
        json_data = {
            "seller_skus": [sku]
        }
        response = tiktok_shop._make_request(path, method='POST', params=params, json_data=json_data)
        if response and response.get('code') == 0:
            products = response.get('data', {}).get('products', [])
            if products:
                return products[0]
        return None

    def _search_tiktok_product_by_id(self, tiktok_shop, product_id):
        path = f"/product/202309/products/{product_id}"
        response = tiktok_shop._make_request(path, method='GET')
        if response and response.get('code') == 0:
            return response.get('data')
        return None

    def upload_image_to_tiktok(self, tiktok_shop, image_data):
        path = "/api/products/upload_imgs"
        params = {
            'app_key': tiktok_shop.app_key,
            'timestamp': int(time.time()),
            'shop_id': tiktok_shop.shop_id,
            'access_token': tiktok_shop.access_token,
        }

        json_data = {
            "img_data": image_data,
            "img_scene": 1,
        }
        response = tiktok_shop._make_request(path, method='POST', params=params, json_data=json_data)
        if response and response.get('code') == 0:
            return response['data'].get('img_id')
        else:
            return None

    def action_update_tiktok_stock(self):
        self.ensure_one()
        if self.tiktok_product_id:
            for variant in self.product_variant_ids:
                variant.action_update_tiktok_stock()
        else:
            raise UserError(_("This product is not published on TikTok yet."))

class ProductProduct(models.Model):
    _inherit = 'product.product'

    tiktok_product_id = fields.Char(string='TikTok Product ID', readonly=True)
    tiktok_sku_id = fields.Char(string='TikTok SKU ID', readonly=True)
    can_sell_on_tiktok = fields.Boolean(string='Can Sell on TikTok', default=False)

    def action_set_can_sell_on_tiktok(self):
        self.write({'can_sell_on_tiktok': True})

    def action_unset_can_sell_on_tiktok(self):
        self.write({'can_sell_on_tiktok': False})

    def action_update_tiktok_stock(self):
        self.ensure_one()
        tiktok_shop = self.env['tiktok.shop'].search([], limit=1)
        if not tiktok_shop:
            raise UserError(_("No TikTok Shop configuration found."))

        if self.tiktok_product_id:
            tiktok_shop.sync_inventory(tiktok_sku_id=self.tiktok_sku_id)