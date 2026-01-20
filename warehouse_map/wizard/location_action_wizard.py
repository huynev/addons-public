# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class LocationActionWizard(models.TransientModel):
    _name = 'location.action.wizard'
    _description = 'Wizard thực hiện action trên vị trí kho'

    location_id = fields.Many2one('stock.location', string='Vị trí nguồn', required=True)
    action_type = fields.Selection([
        ('pick', 'Lấy hàng'),
        ('move', 'Chuyển vị trí'),
        ('transfer', 'Chuyển kho'),
    ], string='Loại thao tác', required=True, default='pick')
    
    quant_ids = fields.Many2many('stock.quant', string='Chọn lot/sản phẩm',
                                  domain="[('location_id', '=', location_id), ('quantity', '>', 0)]")
    
    dest_location_id = fields.Many2one('stock.location', string='Vị trí đích',
                                        domain="[('usage', '=', 'internal')]")
    
    product_id = fields.Many2one('product.product', string='Sản phẩm')
    lot_id = fields.Many2one('stock.lot', string='Lot/Serial')
    quantity = fields.Float(string='Số lượng', default=1.0)
    
    picking_type_id = fields.Many2one('stock.picking.type', string='Loại phiếu')
    
    @api.onchange('location_id', 'action_type')
    def _onchange_location_action(self):
        """Tự động chọn picking type phù hợp"""
        if self.location_id and self.action_type:
            warehouse = self.env['stock.warehouse'].search([
                ('lot_stock_id', 'parent_of', self.location_id.id)
            ], limit=1)
            
            if warehouse:
                if self.action_type == 'pick':
                    self.picking_type_id = warehouse.out_type_id
                elif self.action_type == 'move':
                    self.picking_type_id = warehouse.int_type_id
                elif self.action_type == 'transfer':
                    self.picking_type_id = warehouse.int_type_id
    
    def action_confirm(self):
        """Xác nhận và tạo stock picking"""
        self.ensure_one()
        
        if not self.picking_type_id:
            raise UserError(_('Vui lòng chọn loại phiếu!'))
        
        # Tạo picking
        picking_vals = {
            'picking_type_id': self.picking_type_id.id,
            'location_id': self.location_id.id,
            'location_dest_id': self._get_dest_location().id,
            'origin': f'{self.action_type.upper()} - {self.location_id.name}',
        }
        
        picking = self.env['stock.picking'].create(picking_vals)
        
        # Tạo stock moves
        if self.quant_ids:
            # Nếu đã chọn quants cụ thể
            for quant in self.quant_ids:
                self._create_stock_move(picking, quant.product_id, quant.lot_id, 
                                       min(quant.quantity, quant.quantity - quant.reserved_quantity))
        elif self.product_id:
            # Nếu chọn sản phẩm/lot cụ thể
            self._create_stock_move(picking, self.product_id, self.lot_id, self.quantity)
        else:
            raise UserError(_('Vui lòng chọn sản phẩm hoặc lot để di chuyển!'))
        
        # Confirm picking
        picking.action_confirm()
        
        # Mở form picking
        return {
            'name': _('Phiếu kho'),
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'res_id': picking.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    def _get_dest_location(self):
        """Lấy vị trí đích dựa vào loại action"""
        if self.action_type == 'pick':
            # Lấy hàng -> customer location
            if self.dest_location_id:
                return self.dest_location_id
            return self.picking_type_id.default_location_dest_id
        elif self.action_type in ('move', 'transfer'):
            # Chuyển vị trí/kho
            if not self.dest_location_id:
                raise UserError(_('Vui lòng chọn vị trí đích!'))
            return self.dest_location_id
        
        return self.location_id
    
    def _create_stock_move(self, picking, product, lot, quantity):
        """Tạo stock move line"""
        move_vals = {
            'name': product.name,
            'product_id': product.id,
            'product_uom_qty': quantity,
            'product_uom': product.uom_id.id,
            'picking_id': picking.id,
            'location_id': self.location_id.id,
            'location_dest_id': picking.location_dest_id.id,
        }
        
        move = self.env['stock.move'].create(move_vals)
        
        # Nếu có lot thì gán vào move line
        if lot:
            move_line_vals = {
                'move_id': move.id,
                'product_id': product.id,
                'location_id': self.location_id.id,
                'location_dest_id': picking.location_dest_id.id,
                'lot_id': lot.id,
                'quantity': quantity,
                'product_uom_id': product.uom_id.id,
                'picking_id': picking.id,
            }
            self.env['stock.move.line'].create(move_line_vals)
        
        return move
