from odoo import models, fields

class ResPartner(models.Model):
    _inherit = 'res.partner'

    tiktok_user_id = fields.Char(string='TikTok User ID', readonly=True)