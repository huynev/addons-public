# -*- coding: utf-8 -*-

from odoo import models, fields, api


class StockLocation(models.Model):
    _inherit = 'stock.location'

    display_on_map = fields.Boolean(string='Hiển thị trên sơ đồ', default=True)
    color_code = fields.Char(string='Mã màu', help='Mã màu hiển thị trên sơ đồ (hex color)')
    

class StockQuant(models.Model):
    _inherit = 'stock.quant'
    
    posx = fields.Integer(string='Vị trí X (Cột)', help='Vị trí cột trong sơ đồ kho')
    posy = fields.Integer(string='Vị trí Y (Hàng)', help='Vị trí hàng trong sơ đồ kho')
    posz = fields.Integer(string='Vị trí Z (Tầng)', default=0, help='Tầng/kệ trong sơ đồ kho')
    display_on_map = fields.Boolean(string='Hiển thị trên sơ đồ', default=True)
    
    days_in_stock = fields.Integer(string='Số ngày trong kho', compute='_compute_days_in_stock', store=False)
    
    @api.depends('in_date')
    def _compute_days_in_stock(self):
        """Tính số ngày từ khi nhập kho đến hiện tại"""
        from datetime import datetime
        today = datetime.now()
        
        for quant in self:
            if quant.in_date:
                delta = today - quant.in_date
                quant.days_in_stock = delta.days
            else:
                quant.days_in_stock = 0
    
    def action_pick_products(self):
        """Action lấy hàng từ vị trí"""
        self.ensure_one()
        return {
            'name': 'Lấy hàng',
            'type': 'ir.actions.act_window',
            'res_model': 'location.action.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_location_id': self.location_id.id,
                'default_product_id': self.product_id.id,
                'default_lot_id': self.lot_id.id if self.lot_id else False,
                'default_quantity': self.quantity - self.reserved_quantity,
                'default_action_type': 'pick',
            }
        }
    
    def action_move_location(self):
        """Action chuyển vị trí"""
        self.ensure_one()
        return {
            'name': 'Chuyển vị trí',
            'type': 'ir.actions.act_window',
            'res_model': 'location.action.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_location_id': self.location_id.id,
                'default_product_id': self.product_id.id,
                'default_lot_id': self.lot_id.id if self.lot_id else False,
                'default_quantity': self.quantity - self.reserved_quantity,
                'default_action_type': 'move',
            }
        }
    
    def action_transfer_warehouse(self):
        """Action chuyển kho"""
        self.ensure_one()
        return {
            'name': 'Chuyển kho',
            'type': 'ir.actions.act_window',
            'res_model': 'location.action.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_location_id': self.location_id.id,
                'default_product_id': self.product_id.id,
                'default_lot_id': self.lot_id.id if self.lot_id else False,
                'default_quantity': self.quantity - self.reserved_quantity,
                'default_action_type': 'transfer',
            }
        }
    
    def action_view_stock(self):
        """Xem chi tiết quant"""
        self.ensure_one()
        return {
            'name': f'Chi tiết - {self.product_id.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'stock.quant',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }

