# -*- coding: utf-8 -*-

from odoo import models, fields, api


class WarehouseMap(models.Model):
    _name = 'warehouse.map'
    _description = 'Warehouse Map Layout'
    _order = 'sequence, name'

    name = fields.Char(string='Tên sơ đồ', required=True)
    warehouse_id = fields.Many2one('stock.warehouse', string='Kho', required=True)
    location_id = fields.Many2one('stock.location', string='Vị trí kho chính', 
                                   domain="[('usage', '=', 'internal')]")
    rows = fields.Integer(string='Số hàng', default=10)
    columns = fields.Integer(string='Số cột', default=10)
    
    # Spacing configuration
    row_spacing_interval = fields.Integer(
        string='Khoảng cách sau mỗi X hàng',
        default=0,
        help='Thêm khoảng trống sau mỗi X hàng (0 = không có). VD: 5 = có khoảng trống sau hàng 5, 10, 15...'
    )
    column_spacing_interval = fields.Integer(
        string='Khoảng cách sau mỗi X cột',
        default=0,
        help='Thêm khoảng trống sau mỗi X cột (0 = không có). VD: 3 = có khoảng trống sau cột 3, 6, 9...'
    )
    
    sequence = fields.Integer(string='Thứ tự', default=10)
    active = fields.Boolean(string='Hoạt động', default=True)
    
    # Blocked cells count
    blocked_cell_count = fields.Integer(
        string='Số ô bị chặn',
        compute='_compute_blocked_cell_count'
    )
    
    @api.depends('row_spacing_interval')  # dummy depends
    def _compute_blocked_cell_count(self):
        for record in self:
            record.blocked_cell_count = self.env['warehouse.map.blocked.cell'].search_count([
                ('warehouse_map_id', '=', record.id)
            ])
    
    @api.model
    def get_map_data(self, map_id):
        """Lấy dữ liệu sơ đồ kho với thông tin lot - mỗi lot là 1 vị trí"""
        warehouse_map = self.browse(map_id)
        if not warehouse_map:
            return {}
        
        # Lấy tất cả locations con
        domain = [('location_id', 'child_of', warehouse_map.location_id.id),
                  ('usage', '=', 'internal')]
        locations = self.env['stock.location'].search(domain)
        
        # Lấy thông tin quants (lot/serial) - mỗi quant là 1 vị trí trên sơ đồ
        # CHỈ hiển thị sản phẩm có theo dõi lô/serial (tracking != 'none')
        quants = self.env['stock.quant'].search([
            ('location_id', 'in', locations.ids),
            ('quantity', '>', 0),
            ('display_on_map', '=', True),
            ('product_id.tracking', '!=', 'none'),  # Chỉ sản phẩm có tracking
        ])
        
        # Tổ chức dữ liệu theo vị trí x, y của quant
        lot_data = {}
        for quant in quants:
            # Lấy vị trí x, y từ quant
            x = quant.posx or 0
            y = quant.posy or 0
            z = quant.posz or 0
            
            # Tạo key unique cho mỗi vị trí
            position_key = f"{x}_{y}_{z}"
            
            lot_info = {
                'id': quant.id,
                'quant_id': quant.id,
                'product_id': quant.product_id.id,
                'product_name': quant.product_id.display_name,
                'product_code': quant.product_id.default_code or '',
                'lot_id': quant.lot_id.id if quant.lot_id else False,
                'lot_name': quant.lot_id.name if quant.lot_id else 'No Lot',
                'partner_id': quant.lot_id.partner_id.name if quant.lot_id.partner_id else 'No Vendor',
                'quantity': quant.quantity,
                'uom': quant.product_uom_id.name,
                'reserved_quantity': quant.reserved_quantity,
                'available_quantity': quant.quantity - quant.reserved_quantity,
                'location_id': quant.location_id.id,
                'location_name': quant.location_id.name,
                'location_complete_name': quant.location_id.complete_name,
                'in_date': quant.in_date.strftime('%d-%m-%Y') if quant.in_date else False,
                'days_in_stock': quant.days_in_stock,
                'x': x,
                'y': y,
                'z': z,
                'position_key': position_key,
            }
            
            lot_data[position_key] = lot_info
        
        # Lấy blocked cells
        blocked_cells = self.env['warehouse.map.blocked.cell'].get_blocked_cells_dict(warehouse_map.id)
        
        return {
            'id': warehouse_map.id,
            'name': warehouse_map.name,
            'rows': warehouse_map.rows,
            'columns': warehouse_map.columns,
            'row_spacing_interval': warehouse_map.row_spacing_interval,
            'column_spacing_interval': warehouse_map.column_spacing_interval,
            'warehouse_id': warehouse_map.warehouse_id.id,
            'warehouse_name': warehouse_map.warehouse_id.name,
            'lots': lot_data,
            'blocked_cells': blocked_cells,
        }
    
    def action_view_map(self):
        """Mở view hiển thị sơ đồ kho"""
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'warehouse_map_view',
            'name': f'Sơ đồ - {self.name}',
            'context': {
                'active_id': self.id,
            }
        }
    
    def action_open_block_cell_wizard(self, posx, posy, posz=0):
        """Mở wizard để chặn/bỏ chặn ô"""
        self.ensure_one()
        return {
            'name': 'Chặn/Bỏ chặn ô',
            'type': 'ir.actions.act_window',
            'res_model': 'block.cell.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_warehouse_map_id': self.id,
                'default_posx': posx,
                'default_posy': posy,
                'default_posz': posz,
            }
        }
