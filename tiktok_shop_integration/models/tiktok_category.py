from odoo import models, fields, api

class TikTokCategory(models.Model):
    _name = 'tiktok.category'
    _description = 'TikTok Product Category'

    name = fields.Char(string='Name', required=True)
    tiktok_category_id = fields.Char(string='TikTok Category ID', required=True)
    parent_id = fields.Many2one('tiktok.category', string='Parent Category')
    child_ids = fields.One2many('tiktok.category', 'parent_id', string='Child Categories')
    odoo_category_ids = fields.Many2many('product.category', string='Odoo Categories')
    is_leaf = fields.Boolean(string='Is Leaf Category', default=False)
