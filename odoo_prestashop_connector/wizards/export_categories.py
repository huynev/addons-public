from odoo import models, fields, api


class PrestashopExportCategories(models.TransientModel):
    _name = 'prestashop.export.categories'
    _description = 'Export Categories to PrestaShop'

    shop_id = fields.Many2one(
        'prestashop.shop',
        'PrestaShop Shop',
        required=True
    )

    category_ids = fields.Many2many(
        'product.category',
        string='Categories to Export'
    )

    def export_categories(self):
        self.ensure_one()

        # Sort categories by level to export parents first
        sorted_categories = self.category_ids.sorted(lambda r: len(r.parent_path.split('/')) - 1)

        for category in sorted_categories:
            binding = self.env['prestashop.product.category'].search([
                ('odoo_id', '=', category.id),
                ('shop_id', '=', self.shop_id.id)
            ], limit=1)

            if not binding:
                binding = self.env['prestashop.product.category'].create({
                    'odoo_id': category.id,
                    'shop_id': self.shop_id.id
                })

            binding.export_record()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Success',
                'message': 'Categories export started',
                'type': 'success',
            }
        }