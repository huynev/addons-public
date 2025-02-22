from odoo import fields, models


class Company(models.Model):
    _inherit = "res.company"
    
    stock_confirm_image = fields.Boolean("Stock Done Image", default=False)
    stock_confirm_image_count = fields.Integer('Stock Image Number', default=1)