# -*- coding: utf-8 -*-

from odoo import models, fields, api


class BlockCellWizard(models.TransientModel):
    _name = 'block.cell.wizard'
    _description = 'Wizard to Block/Unblock Cell'

    warehouse_map_id = fields.Many2one('warehouse.map', string='Sơ đồ kho', required=True)
    posx = fields.Integer(string='Vị trí X (Cột)', required=True, readonly=True)
    posy = fields.Integer(string='Vị trí Y (Hàng)', required=True, readonly=True)
    posz = fields.Integer(string='Vị trí Z (Tầng)', default=0, readonly=True)
    
    action_type = fields.Selection([
        ('block', 'Chặn ô này'),
        ('unblock', 'Bỏ chặn ô này'),
    ], string='Hành động', required=True, default='block')
    
    # For blocking
    block_type = fields.Selection([
        ('wall', 'Tường/Cột'),
        ('aisle', 'Lối đi'),
        ('stairs', 'Cầu thang'),
        ('equipment', 'Thiết bị cố định'),
        ('hazard', 'Khu vực nguy hiểm'),
        ('reserved', 'Khu vực dành riêng'),
        ('other', 'Khác'),
    ], string='Loại ô bị chặn', default='other')
    
    block_color = fields.Char(
        string='Màu hiển thị',
        default='#9e9e9e',
        help='Mã màu hex. VD: #ff0000'
    )
    
    note = fields.Text(string='Ghi chú')
    
    # For unblocking
    blocked_cell_id = fields.Many2one('warehouse.map.blocked.cell', string='Ô bị chặn')
    
    @api.model
    def default_get(self, fields_list):
        """Set default values from context"""
        res = super().default_get(fields_list)
        
        context = self.env.context
        if 'warehouse_map_id' in context:
            res['warehouse_map_id'] = context['warehouse_map_id']
        if 'posx' in context:
            res['posx'] = context['posx']
        if 'posy' in context:
            res['posy'] = context['posy']
        if 'posz' in context:
            res['posz'] = context['posz']
            
        # Check if cell is already blocked
        if res.get('warehouse_map_id') and res.get('posx') is not None and res.get('posy') is not None:
            blocked = self.env['warehouse.map.blocked.cell'].search([
                ('warehouse_map_id', '=', res['warehouse_map_id']),
                ('posx', '=', res['posx']),
                ('posy', '=', res['posy']),
                ('posz', '=', res.get('posz', 0)),
            ], limit=1)
            
            if blocked:
                res['action_type'] = 'unblock'
                res['blocked_cell_id'] = blocked.id
                res['block_type'] = blocked.block_type
                res['block_color'] = blocked.block_color
                res['note'] = blocked.note
            else:
                res['action_type'] = 'block'
        
        return res
    
    def action_execute(self):
        """Execute block or unblock action"""
        self.ensure_one()
        
        if self.action_type == 'block':
            return self._action_block()
        else:
            return self._action_unblock()
    
    def _action_block(self):
        """Block the cell"""
        # Check if already blocked
        existing = self.env['warehouse.map.blocked.cell'].search([
            ('warehouse_map_id', '=', self.warehouse_map_id.id),
            ('posx', '=', self.posx),
            ('posy', '=', self.posy),
            ('posz', '=', self.posz),
        ])
        
        if existing:
            # Update existing
            existing.write({
                'block_type': self.block_type,
                'block_color': self.block_color,
                'note': self.note,
            })
        else:
            # Create new
            self.env['warehouse.map.blocked.cell'].create({
                'warehouse_map_id': self.warehouse_map_id.id,
                'posx': self.posx,
                'posy': self.posy,
                'posz': self.posz,
                'block_type': self.block_type,
                'block_color': self.block_color,
                'note': self.note,
            })
        
        return {'type': 'ir.actions.act_window_close'}
    
    def _action_unblock(self):
        """Unblock the cell"""
        if self.blocked_cell_id:
            self.blocked_cell_id.unlink()
        
        return {'type': 'ir.actions.act_window_close'}
