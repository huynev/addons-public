from odoo import models, fields, api

class TikTokCategoryMappingWizard(models.TransientModel):
    _name = 'tiktok.category.mapping.wizard'
    _description = 'TikTok Category Mapping Wizard'

    tiktok_category_id = fields.Many2one('tiktok.category', string='TikTok Category', required=True)
    odoo_category_ids = fields.Many2many('product.category', string='Odoo Categories')

    @api.onchange('tiktok_category_id')
    def _onchange_tiktok_category(self):
        if self.tiktok_category_id:
            self.odoo_category_ids = self.tiktok_category_id.odoo_category_ids

    def action_map_categories(self):
        self.ensure_one()
        self.tiktok_category_id.odoo_category_ids = self.odoo_category_ids
        return {'type': 'ir.actions.act_window_close'}