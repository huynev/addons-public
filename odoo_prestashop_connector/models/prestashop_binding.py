from odoo import models, fields

class PrestashopBinding(models.AbstractModel):
    _name = 'prestashop.binding'
    _description = 'PrestaShop Binding (Abstract)'

    # Common fields cho tất cả các binding models
    shop_id = fields.Many2one(
        comodel_name='prestashop.shop',
        string='PrestaShop Shop',
        required=True,
        ondelete='restrict'
    )
    sync_date = fields.Datetime('Last Synchronization Date')
    prestashop_id = fields.Integer('PrestaShop ID', readonly=True)
    active = fields.Boolean(string='Active', default=True)