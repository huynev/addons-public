from odoo import models, fields

class StockDoneImage(models.Model):
    _name = "stock.confirm.image"
    _description = "Image for stock before done state"
    
    picking_id = fields.Many2one('stock.picking', string="Stock Picking")
    name = fields.Char('Name', required = False)
    image = fields.Binary('Image', attachment=True)