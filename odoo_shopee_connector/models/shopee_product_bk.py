# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ShopeeProductProduct(models.Model):
    _name = 'shopee.product.product'
    _description = 'Shopee Product'
    _inherit = 'shopee.binding'

    odoo_id = fields.Many2one(
        comodel_name='product.product',
        string='Product',
        required=True,
        ondelete='cascade',
    )
    shopee_name = fields.Char('Name')
    shopee_description = fields.Text('Description')
    shopee_price = fields.Float('Price')
    shopee_stock = fields.Float('Stock')
    shopee_category_id = fields.Char('Category ID')
    shopee_category = fields.Many2one('shopee.category', 'Shopee Category',
                                      compute='_compute_shopee_category', store=True)
    shopee_image_ids = fields.One2many(
        comodel_name='shopee.product.image',
        inverse_name='shopee_product_id',
        string='Images',
    )

    @api.depends('shopee_category_id', 'backend_id')
    def _compute_shopee_category(self):
        """Link the product to its Shopee category"""
        for product in self:
            if product.shopee_category_id:
                category = self.env['shopee.category'].search([
                    ('backend_id', '=', product.backend_id.id),
                    ('shopee_category_id', '=', product.shopee_category_id)
                ], limit=1)
                product.shopee_category = category.id if category else False
            else:
                product.shopee_category = False

    def export_inventory(self):
        """Export inventory to Shopee"""
        self.ensure_one()
        self.export_inventory_job()
        return True

    def export_inventory_job(self):
        """Job: Export inventory to Shopee"""
        with self.backend_id.work_on(self._name) as work:
            exporter = work.component(usage='inventory.exporter')
            return exporter.run(self)

    @api.model
    def import_batch(self, backend, since_date=None):
        """Import batch from Shopee"""
        with backend.work_on(self._name) as work:
            importer = work.component(usage='batch.importer')
            return importer.run(since_date=since_date)

    def get_and_apply_category_recommendation(self):
        """Lấy gợi ý danh mục từ Shopee và áp dụng ngay cho sản phẩm"""
        self.ensure_one()

        if not self.shopee_name and not self.odoo_id.name:
            raise UserError(_("Sản phẩm cần có tên để gợi ý danh mục!"))

        with self.backend_id.work_on(self._name) as work:
            adapter = work.component(usage='backend.adapter')

            # Chuẩn bị tham số
            item_name = self.shopee_name or self.odoo_id.name
            params = {'item_name': item_name}

            # Thêm hình ảnh sản phẩm nếu có
            if self.shopee_image_ids:
                image_id = self.shopee_image_ids[0].image_url
                if image_id:
                    params['product_cover_image'] = image_id

            # Gọi API Shopee để lấy gợi ý danh mục
            result = adapter.call('/api/v2/product/category_recommend', 'GET', params=params)

            if result and not result.get('error'):
                # Lấy danh sách ID danh mục được gợi ý
                recommended_category_ids = result.get('response', {}).get('category_id', [])

                if recommended_category_ids:
                    # Chọn danh mục đầu tiên từ danh sách gợi ý
                    first_category_id = str(recommended_category_ids[0])

                    # Tìm danh mục tương ứng trong Odoo
                    category = self.env['shopee.category'].search([
                        ('backend_id', '=', self.backend_id.id),
                        ('shopee_category_id', '=', first_category_id)
                    ], limit=1)

                    # Nếu không tìm thấy danh mục, kiểm tra xem cần import danh mục mới không
                    if not category and len(recommended_category_ids) > 0:
                        # Gọi API import danh mục nếu cần
                        self.backend_id.import_categories()
                        # Tìm lại danh mục sau khi import
                        category = self.env['shopee.category'].search([
                            ('backend_id', '=', self.backend_id.id),
                            ('shopee_category_id', '=', first_category_id)
                        ], limit=1)

                    if category:
                        # Cập nhật danh mục sản phẩm
                        self.shopee_category_id = first_category_id
                        self.shopee_category = category.id

                        # Hiển thị thông báo kèm theo tên danh mục đã áp dụng
                        return {
                            'type': 'ir.actions.client',
                            'tag': 'display_notification',
                            'params': {
                                'title': _('Thành công'),
                                'message': _('Đã áp dụng danh mục "%s" cho sản phẩm') % category.name,
                                'type': 'success',
                            }
                        }
                    else:
                        return {
                            'type': 'ir.actions.client',
                            'tag': 'display_notification',
                            'params': {
                                'title': _('Cảnh báo'),
                                'message': _(
                                    'Tìm thấy danh mục gợi ý (ID: %s) nhưng không có trong hệ thống. Vui lòng import danh mục Shopee trước.') % first_category_id,
                                'type': 'warning',
                            }
                        }
                else:
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _('Thông báo'),
                            'message': _('Không tìm thấy danh mục gợi ý nào từ Shopee cho sản phẩm này.'),
                            'type': 'warning',
                        }
                    }
            else:
                error_msg = result.get('message', 'Unknown error')
                raise UserError(_("Không thể lấy danh mục gợi ý: %s") % error_msg)


class ShopeeProductImage(models.Model):
    _name = 'shopee.product.image'
    _description = 'Shopee Product Image'
    _order = 'position'

    shopee_product_id = fields.Many2one(
        comodel_name='shopee.product.product',
        string='Shopee Product',
        required=True,
        ondelete='cascade',
    )
    image_url = fields.Char('Image URL')
    position = fields.Integer('Position')


class ProductProduct(models.Model):
    _inherit = 'product.product'

    shopee_bind_ids = fields.One2many(
        'shopee.product.product',
        'odoo_id',
        string='Shopee Bindings'
    )