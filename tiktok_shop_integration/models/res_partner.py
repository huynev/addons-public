from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class ResPartner(models.Model):
    _inherit = 'res.partner'

    tiktok_user_id = fields.Char(string='TikTok User ID', readonly=True)

    _sql_constraints = [
        ('tiktok_user_id_unique', 'unique(tiktok_user_id)', 'TikTok User ID must be unique!')
    ]

    @api.constrains('tiktok_user_id')
    def _check_tiktok_user_id_unique(self):
        for record in self:
            if record.tiktok_user_id:
                duplicate = self.search([
                    ('tiktok_user_id', '=', record.tiktok_user_id),
                    ('id', '!=', record.id)
                ])
                if duplicate:
                    raise ValidationError(_('TikTok User ID must be unique. The ID %s is already used.') % record.tiktok_user_id)