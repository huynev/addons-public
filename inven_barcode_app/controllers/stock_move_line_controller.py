from . import base_controller
from odoo import http
from odoo.http import request

class StockMoveLineController(base_controller.BaseAPIController):
    
    @http.route('/api/stock-move-line/update', type='json', auth='user', methods=['POST'], csrf=False)
    def update_stock_move_line(self, **post):
        id = post.get('id')
        
        if not id:
            return {
                'success': False, 
                'error': 'Missing line id',
            }
        
        line = request.env['stock.move.line'].browse(id)
        
        if not line.exists():
            return {
                'success': False,
                'error': 'Stock Move Line Not Found',
            }
        
        quantity = post.get('quantity')
        package_id = post.get('package_id')
        
        if quantity > 0:
            line.write({
                'quantity': quantity,
                'result_package_id': package_id,
            })
        else:
            line.unlink()
        
        
        return {
            'success': True,
            'message': 'Update move line successfull',
        }
        
    @http.route('/api/stock-move-line/store', type='json', auth='user', methods=['POST'], csrf=False)
    def create_stock_move_line(self, **post):
        move_id = post.get('move_id')
        quantity = post.get('quantity')
        
        if not move_id or not quantity or quantity <= 0:
            return {
                'success': False, 
                'error': 'Missing Move id or quantity invalid',
            }
        
        stock_move = request.env['stock.move'].browse(move_id)
        
        if not stock_move.exists():
            return {
                'success': False,
                'error': 'Stock Move Not Found',
            }
        
        package_id = post.get('package_id')
        
        line = request.env['stock.move.line'].create({
            'move_id': stock_move.id,
            'company_id': stock_move.company_id.id,
            'picking_id': stock_move.picking_id.id,
            'quantity': quantity,
            'result_package_id': package_id,
            'product_id': stock_move.product_id.id,
            'product_uom_id': stock_move.product_uom.id,
        })
        
        return {
            'success': True,
            'data': {
                'id': line.id,
                'lot_id': line.lot_id.name if line.lot_id else None,
                'quantity': line.quantity,
                'location': {
                    'id': line.location_id.id,
                    'name': line.location_id.display_name,
                },
                'dest_location': {
                    'id': line.location_dest_id.id,
                    'name': line.location_dest_id.display_name,
                },
                'product': {
                    'id': line.product_id.id,
                    'name': line.product_id.display_name,
                },
                'product_uom': {
                    'id': line.product_uom_id.id,
                    'name': line.product_uom_id.display_name,
                },
                'package': {
                    'id': line.package_id.id,
                    'name': line.package_id.display_name,
                    'type': {
                        'id': line.package_id.package_type_id.id,
                        'name': line.package_id.package_type_id.display_name
                    }
                },
                'result_package': {
                    'id': line.result_package_id.id,
                    'name': line.result_package_id.display_name,
                    'type': {
                        'id': line.result_package_id.package_type_id.id,
                        'name': line.result_package_id.package_type_id.display_name
                    }
                },
                'package_level': {
                    'id': line.package_level_id.id,
                    'package': {
                        'id': line.package_level_id.package_id.id,
                        'name': line.package_level_id.package_id.display_name,
                        'type': {
                            'id': line.package_level_id.package_id.package_type_id.id,
                            'name': line.package_level_id.package_id.package_type_id.display_name
                        }
                    }
                }
            }
        }