# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ShopeeProductTemplate(models.Model):
    _name = 'shopee.product.template'
    _description = 'Shopee Product Template'
    _inherit = 'shopee.binding'

    odoo_id = fields.Many2one(
        comodel_name='product.template',
        string='Product Template',
        required=True,
        ondelete='cascade',
    )
    shopee_name = fields.Char('Name')
    shopee_description = fields.Text('Description')
    shopee_price = fields.Float('Price')
    shopee_stock = fields.Float('Stock', compute='_compute_shopee_stock', store=True)
    shopee_category_id = fields.Char('Category ID')
    shopee_category = fields.Many2one('shopee.category', 'Shopee Category',
                                      compute='_compute_shopee_category', store=True)
    variant_count = fields.Integer('Variant Count', compute='_compute_variant_count', store=True)

    variant_ids = fields.One2many(
        'shopee.product.product',
        'shopee_template_id',
        string='Variant Bindings'
    )
    has_variants = fields.Boolean('Has Variants', compute='_compute_variant_count', store=True)

    shopee_item_status = fields.Selection([
        ('NORMAL', 'Active'),
        ('UNLIST', 'Inactive'),
        ('DELETED', 'Deleted')
    ], string='Item Status', default='UNLIST')

    # Các trường bổ sung cho thông tin sản phẩm
    shopee_weight = fields.Float('Weight (kg)', default=1.0)
    shopee_package_length = fields.Float('Package Length (cm)', default=10.0)
    shopee_package_width = fields.Float('Package Width (cm)', default=10.0)
    shopee_package_height = fields.Float('Package Height (cm)', default=10.0)
    shopee_condition = fields.Selection([
        ('NEW', 'New'),
        ('USED', 'Used')
    ], string='Condition', default='NEW')
    shopee_brand_id = fields.Char('Brand ID')
    shopee_brand_name = fields.Char('Brand Name')

    # Trạng thái đồng bộ
    shopee_sync_status = fields.Selection([
        ('not_synced', 'Not Synced'),
        ('syncing', 'Syncing'),
        ('synced', 'Synced'),
        ('failed', 'Failed')
    ], string='Sync Status', default='not_synced')
    shopee_sync_message = fields.Text('Sync Message')

    @api.depends('odoo_id')
    def _compute_variant_count(self):
        for template in self:
            template.variant_count = len(template.odoo_id.product_variant_ids)
            template.has_variants = template.variant_count > 1

    @api.depends('shopee_category_id', 'backend_id')
    def _compute_shopee_category(self):
        """Link the product to its Shopee category"""
        for template in self:
            if template.shopee_category_id:
                category = self.env['shopee.category'].search([
                    ('backend_id', '=', template.backend_id.id),
                    ('shopee_category_id', '=', template.shopee_category_id)
                ], limit=1)
                template.shopee_category = category.id if category else False
            else:
                template.shopee_category = False

    @api.depends('variant_ids.shopee_stock', 'odoo_id.product_variant_ids.qty_available')
    def _compute_shopee_stock(self):
        """Compute total stock from variants"""
        for template in self:
            if template.has_variants and template.variant_ids:
                template.shopee_stock = sum(variant.shopee_stock for variant in template.variant_ids)
            elif template.odoo_id.product_variant_ids:
                template.shopee_stock = template.odoo_id.product_variant_ids[0].qty_available
            else:
                template.shopee_stock = 0

    def export_product(self):
        """Export product template to Shopee"""
        self.ensure_one()

        # Kiểm tra danh mục
        if not self.shopee_category_id:
            raise UserError(_("You must set a Shopee category before exporting the product."))

        self.shopee_sync_status = 'syncing'

        try:
            self.export_product_job()
            self.shopee_sync_status = 'synced'
            self.shopee_sync_message = _("Product successfully exported to Shopee at %s") % fields.Datetime.now()

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _('Product has been exported to Shopee.'),
                    'type': 'success',
                }
            }
        except Exception as e:
            self.shopee_sync_status = 'failed'
            self.shopee_sync_message = _("Export failed: %s") % str(e)

            raise UserError(_("Failed to export product: %s") % str(e))

    def export_product_job(self):
        """Job: Export product template to Shopee"""
        with self.backend_id.work_on(self._name) as work:
            exporter = work.component(usage='product.exporter')
            return exporter.run(self)

    def export_inventory(self):
        """Export inventory to Shopee"""
        self.ensure_one()

        if not self.external_id:
            raise UserError(_("Product must be exported to Shopee first before updating inventory."))

        try:
            if self.has_variants:
                # Export inventory cho từng biến thể
                for variant in self.variant_ids:
                    variant.export_inventory_job()
            else:
                # Lấy biến thể mặc định và export
                if self.variant_ids:
                    self.variant_ids[0].export_inventory_job()
                else:
                    # Tạo một binding tạm thời cho variant
                    product_variant = self.odoo_id.product_variant_ids[0]
                    variant_binding = self.env['shopee.product.product'].create({
                        'backend_id': self.backend_id.id,
                        'odoo_id': product_variant.id,
                        'external_id': self.external_id,
                        'shopee_template_id': self.id,
                        'shopee_stock': product_variant.qty_available
                    })
                    variant_binding.export_inventory_job()

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _('Inventory has been updated on Shopee.'),
                    'type': 'success',
                }
            }
        except Exception as e:
            raise UserError(_("Failed to update inventory: %s") % str(e))

    @api.model
    def import_batch(self, backend, since_date=None):
        """Import batch of product templates from Shopee"""
        with backend.work_on(self._name) as work:
            importer = work.component(usage='batch.importer')
            return importer.run(since_date=since_date)

    def get_and_apply_category_recommendation(self):
        """Lấy gợi ý danh mục từ Shopee và áp dụng ngay cho sản phẩm"""
        self.ensure_one()

        if not self.shopee_name and not self.odoo_id.name:
            raise UserError(_("Product needs a name for category recommendation!"))

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
                                'title': _('Success'),
                                'message': _('Applied category "%s" to product') % category.name,
                                'type': 'success',
                            }
                        }
                    else:
                        return {
                            'type': 'ir.actions.client',
                            'tag': 'display_notification',
                            'params': {
                                'title': _('Warning'),
                                'message': _(
                                    'Found recommended category (ID: %s) but it does not exist in the system. Please import Shopee categories first.') % first_category_id,
                                'type': 'warning',
                            }
                        }
                else:
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _('Notification'),
                            'message': _('No category recommendations found from Shopee for this product.'),
                            'type': 'warning',
                        }
                    }
            else:
                error_msg = result.get('message', 'Unknown error')
                raise UserError(_("Could not get category recommendations: %s") % error_msg)

    def create_variant_bindings(self):
        """Create shopee.product.product bindings for all variants"""
        self.ensure_one()

        if not self.has_variants:
            return

        for variant in self.odoo_id.product_variant_ids:
            # Kiểm tra xem binding đã tồn tại chưa
            existing_binding = self.env['shopee.product.product'].search([
                ('odoo_id', '=', variant.id),
                ('backend_id', '=', self.backend_id.id),
                ('shopee_template_id', '=', self.id)
            ], limit=1)

            if not existing_binding:
                # Tạo binding mới cho variant
                self.env['shopee.product.product'].create({
                    'backend_id': self.backend_id.id,
                    'odoo_id': variant.id,
                    'shopee_template_id': self.id,
                    'shopee_name': variant.name or self.shopee_name,
                    'shopee_price': variant.lst_price or self.shopee_price,
                    'shopee_stock': variant.qty_available
                })

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Created bindings for all product variants.'),
                'type': 'success',
            }
        }

    def action_view_odoo_product(self):
        """
        Mở form view sản phẩm Odoo từ record shopee.product.template
        """
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'product.template',
            'view_mode': 'form',
            'res_id': self.odoo_id.id,
            'target': 'current',
        }

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    shopee_bind_ids = fields.One2many(
        'shopee.product.template',
        'odoo_id',
        string='Shopee Bindings'
    )

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

    shopee_template_id = fields.Many2one(
        'shopee.product.template',
        string='Shopee Product Template',
        ondelete='cascade'
    )
    shopee_name = fields.Char('Name')
    shopee_price = fields.Float('Price')
    shopee_stock = fields.Float('Stock', compute='_compute_shopee_stock', store=True)
    model_id = fields.Char('Shopee Model ID')
    model_sku = fields.Char('Model SKU')
    tier_index = fields.Char('Tier Index', help='Position in the tier variation structure')

    @api.depends('odoo_id.qty_available')
    def _compute_shopee_stock(self):
        """Compute stock from product variant"""
        for variant in self:
            if variant.odoo_id:
                variant.shopee_stock = variant.odoo_id.qty_available
            else:
                variant.shopee_stock = 0

class ProductProduct(models.Model):
    _inherit = 'product.product'

    shopee_bind_ids = fields.One2many(
        'shopee.product.product',
        'odoo_id',
        string='Shopee Bindings'
    )