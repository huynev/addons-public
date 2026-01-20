# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class AssignLotPositionWizard(models.TransientModel):
    _name = 'assign.lot.position.wizard'
    _description = 'Wizard gán vị trí cho lot'

    posx = fields.Integer(string='Vị trí X (Cột)', required=True, readonly=True)
    posy = fields.Integer(string='Vị trí Y (Hàng)', required=True, readonly=True)
    posz = fields.Integer(string='Vị trí Z (Tầng)', default=0)
    
    warehouse_map_id = fields.Many2one('warehouse.map', string='Sơ đồ kho', required=True)
    location_id = fields.Many2one('stock.location', string='Vị trí kho', 
                                   related='warehouse_map_id.location_id', readonly=True)
    
    # Cho phép chọn quant chưa có vị trí hoặc chưa hiển thị trên map
    # CHỈ sản phẩm có theo dõi lô/serial
    quant_id = fields.Many2one('stock.quant', string='Chọn Lot/Quant', 
                                required=True,
                                domain="""[
                                    ('location_id', 'child_of', location_id),
                                    ('quantity', '>', 0),
                                    ('product_id.tracking', '!=', 'none'),
                                    '|',
                                        ('display_on_map', '=', False),
                                        '&',
                                            ('posx', '=', False),
                                            ('posy', '=', False)
                                ]""")
    
    product_id = fields.Many2one('product.product', string='Sản phẩm', 
                                  related='quant_id.product_id', readonly=True)
    lot_id = fields.Many2one('stock.lot', string='Lot/Serial', 
                             related='quant_id.lot_id', readonly=True)
    quantity = fields.Float(string='Số lượng', related='quant_id.quantity', readonly=True)
    
    # Option: Tạo quant mới nếu không chọn từ list
    create_new = fields.Boolean(string='Hoặc tạo quant mới')
    new_product_id = fields.Many2one('product.product', string='Sản phẩm mới',
                                      domain="[('tracking', '!=', 'none')]")
    new_lot_id = fields.Many2one('stock.lot', string='Lot/Serial mới',
                                  domain="[('product_id', '=', new_product_id)]")
    new_quantity = fields.Float(string='Số lượng mới', default=1.0)
    
    @api.onchange('create_new')
    def _onchange_create_new(self):
        """Clear fields khi switch mode"""
        if self.create_new:
            self.quant_id = False
        else:
            self.new_product_id = False
            self.new_lot_id = False
            self.new_quantity = 1.0
    
    def action_assign_position(self):
        """Gán vị trí cho quant hoặc tạo quant mới"""
        self.ensure_one()
        
        if self.create_new:
            # Tạo quant mới
            if not self.new_product_id:
                raise UserError(_('Vui lòng chọn sản phẩm!'))
            
            # Kiểm tra vị trí đã có quant chưa
            existing = self.env['stock.quant'].search([
                ('posx', '=', self.posx),
                ('posy', '=', self.posy),
                ('posz', '=', self.posz),
                ('display_on_map', '=', True),
                ('quantity', '>', 0),
            ], limit=1)
            
            if existing:
                raise UserError(_(f'Vị trí [{self.posx}, {self.posy}] đã có lot khác!'))
            
            # Tạo quant mới
            quant_vals = {
                'product_id': self.new_product_id.id,
                'location_id': self.location_id.id,
                'quantity': self.new_quantity,
                'posx': self.posx,
                'posy': self.posy,
                'posz': self.posz,
                'display_on_map': True,
            }
            
            if self.new_lot_id:
                quant_vals['lot_id'] = self.new_lot_id.id
            
            quant = self.env['stock.quant'].create(quant_vals)
            
            return {'type': 'ir.actions.act_window_close'}
        else:
            # Gán vị trí cho quant đã chọn
            if not self.quant_id:
                raise UserError(_('Vui lòng chọn lot/quant!'))
            
            # Kiểm tra vị trí đã có quant khác chưa
            existing = self.env['stock.quant'].search([
                ('posx', '=', self.posx),
                ('posy', '=', self.posy),
                ('posz', '=', self.posz),
                ('display_on_map', '=', True),
                ('quantity', '>', 0),
                ('id', '!=', self.quant_id.id),
            ], limit=1)
            
            if existing:
                raise UserError(_(f'Vị trí [{self.posx}, {self.posy}] đã có lot khác: {existing.display_name}'))
            
            # Gán vị trí
            self.quant_id.write({
                'posx': self.posx,
                'posy': self.posy,
                'posz': self.posz,
                'display_on_map': True,
            })
            
            return {'type': 'ir.actions.act_window_close'}
