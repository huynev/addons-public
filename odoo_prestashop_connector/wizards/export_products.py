from odoo import models, fields, api

class PrestashopExportProducts(models.TransientModel):
    _name = 'prestashop.export.products'
    _description = 'Export Products to PrestaShop'

    shop_id = fields.Many2one(
        'prestashop.shop',
        'PrestaShop Shop',
        required=True,
        default=lambda self: self.env['prestashop.shop'].search([], limit=1)
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

        for product in products:
            binding = self.env['prestashop.product.template'].search([
                ('odoo_id', '=', product.id),
                ('shop_id', '=', self.shop_id.id)
            ], limit=1)
            if not binding:
                binding = self.env['prestashop.product.template'].create({
                    'odoo_id': product.id,
                    'shop_id': self.shop_id.id
                })
            binding.with_delay(channel='root.prestashop').export_record()
            # binding.export_record()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Success',
                'message': 'Product export started',
                'type': 'success',
            }
        }
