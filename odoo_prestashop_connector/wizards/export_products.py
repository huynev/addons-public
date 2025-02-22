from odoo import models, fields, api

class PrestashopExportProducts(models.TransientModel):
    _name = 'prestashop.export.products'
    _description = 'Export Products to PrestaShop'

    shop_id = fields.Many2one(
        'prestashop.shop',
        'PrestaShop Shop',
        required=True
    )
    product_ids = fields.Many2many(
        'product.template',
        string='Products to Export'
    )

    def export_products(self):
        self.ensure_one()
        for product in self.product_ids:
            # Tạo binding nếu chưa có
            binding = self.env['prestashop.product.template'].search([
                ('odoo_id', '=', product.id),
                ('shop_id', '=', self.shop_id.id)
            ], limit=1)
            if not binding:
                binding = self.env['prestashop.product.template'].create({
                    'odoo_id': product.id,
                    'shop_id': self.shop_id.id
                })
            # Export sản phẩm
            # binding.with_delay(channel='root.prestashop').export_record()
            binding.export_record()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Success',
                'message': 'Product export started',
                'type': 'success',
            }
        }