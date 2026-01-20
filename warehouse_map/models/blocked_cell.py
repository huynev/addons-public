# -*- coding: utf-8 -*-

from odoo import models, fields, api


class WarehouseMapBlockedCell(models.Model):
    _name = 'warehouse.map.blocked.cell'
    _description = 'Blocked Cells in Warehouse Map'
    _rec_name = 'display_name'

    warehouse_map_id = fields.Many2one('warehouse.map', string='Sơ đồ kho', required=True, ondelete='cascade')
    posx = fields.Integer(string='Vị trí X (Cột)', required=True)
    posy = fields.Integer(string='Vị trí Y (Hàng)', required=True)
    posz = fields.Integer(string='Vị trí Z (Tầng)', default=0)
    
    block_type = fields.Selection([
        ('wall', 'Tường/Cột'),
        ('aisle', 'Lối đi'),
        ('stairs', 'Cầu thang'),
        ('equipment', 'Thiết bị cố định'),
        ('hazard', 'Khu vực nguy hiểm'),
        ('reserved', 'Khu vực dành riêng'),
        ('other', 'Khác'),
    ], string='Loại ô bị chặn', default='other', required=True)
    
    block_color = fields.Char(
        string='Màu hiển thị',
        default='#9e9e9e',
        help='Mã màu hex cho ô bị chặn. VD: #ff0000 = đỏ'
    )
    
    note = fields.Text(string='Ghi chú')
    display_name = fields.Char(string='Tên', compute='_compute_display_name', store=True)
    
    _sql_constraints = [
        ('unique_position', 
         'UNIQUE(warehouse_map_id, posx, posy, posz)',
         'Vị trí này đã bị chặn!')
    ]
    
    @api.depends('posx', 'posy', 'posz', 'block_type')
    def _compute_display_name(self):
        for record in self:
            type_name = dict(self._fields['block_type'].selection).get(record.block_type, 'Khác')
            record.display_name = f'[{record.posx},{record.posy}] - {type_name}'
    
    @api.model
    def get_blocked_cells_dict(self, warehouse_map_id):
        """Trả về dict các ô bị chặn theo position_key"""
        blocked_cells = self.search([('warehouse_map_id', '=', warehouse_map_id)])
        result = {}
        for cell in blocked_cells:
            position_key = f"{cell.posx}_{cell.posy}_{cell.posz}"
            result[position_key] = {
                'id': cell.id,
                'posx': cell.posx,
                'posy': cell.posy,
                'posz': cell.posz,
                'block_type': cell.block_type,
                'block_type_name': dict(self._fields['block_type'].selection).get(cell.block_type),
                'block_color': cell.block_color,
                'note': cell.note or '',
            }
        return result
