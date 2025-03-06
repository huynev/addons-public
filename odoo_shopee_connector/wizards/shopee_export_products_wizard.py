from odoo import api, fields, models


class ShopeeExportProducts(models.TransientModel):
    _name = 'shopee.export.products'
    _description = 'Export Products to Shopee'

    backend_id = fields.Many2one(
        'shopee.backend',
        'Shopee Backend',
        required=True,
        default=lambda self: self.env['shopee.backend'].search([], limit=1)
    )
    category_ids = fields.Many2many(
        'product.category',
        string='Product Categories'
    )
    product_ids = fields.Many2many(
        'product.template',
        string='Products to Export'
    )

    def export_products(self):
        self.ensure_one()
        products = self.product_ids
        if self.category_ids:
            category_ids = self.env['product.category'].search([('id', 'child_of', self.category_ids.ids)])
            products |= self.env['product.template'].search([('categ_id', 'in', category_ids.ids)])

        job_count = 0
        for product in products:
            binding = self.env['shopee.product.template'].search([
                ('odoo_id', '=', product.id),
                ('backend_id', '=', self.backend_id.id)
            ], limit=1)
            if not binding:
                binding = self.env['shopee.product.template'].create({
                    'odoo_id': product.id,
                    'backend_id': self.backend_id.id,
                    'shopee_name': product.name,
                    'shopee_price': product.list_price,
                    # 'shopee_stock': product.qty_available,
                    'shopee_description': product.description_sale or product.name,
                })
            # binding.with_delay(channel='root.shopee').export_record()
            binding.export_record()
            job_count += 1

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Thành công',
                'message': f'{job_count} sản phẩm đã được lên lịch xuất lên Shopee',
                'type': 'success',
            }
        }