from odoo import http
from odoo.http import request

class ScannerController(http.Controller):

    @http.route('/api/scanner', type='json', auth='user', methods=['POST'], csrf=False)
    def get_product_by_barcode(self, barcode):
        # Search for the product using the barcode
        product = request.env['product.product'].search([('barcode', '=', barcode)], limit=1)

        if product:
            return {
                'success': True,
                'data': {
                    'type': 'product',
                    'id': product.id,
                }
            }

        # Search Stock Picking
        stock_picking = request.env['stock.picking'].search([('barcode', '=', barcode)], limit=1)
        if stock_picking:
            return {
                'success': True,
                'data': {
                    'type': 'stock_picking',
                    'id': stock_picking.id,
                }
            }
        
        # Search Packing
        package = request.env['stock.quant.package'].search([('name', '=', barcode)], limit=1)
        if package:
            return {
                'success': True,
                'data': {
                    'type': 'stock_quantity_package',
                    'id': package.id,
                }
            }

        return {
            'success': False,
            'error': 'Can not find barcode'
        }
        
    @http.route('/api/scanner/search', type='json', auth='user', methods=['POST'], csrf=False)
    def get_product_by_code(self, search):
        # Search for the product using the barcode
        product = request.env['product.product'].search([
            '|', 
            ('barcode', '=', search), 
            ('default_code', '=', search)
        ], limit=1)

        if product:
            return {
                'success': True,
                'data': {
                    'type': 'product',
                    'id': product.id,
                }
            }

        # Search Stock Picking
        stock_picking = request.env['stock.picking'].search([
            '|',
            ('barcode', '=', search),
            ('name', '=', search)    
        ], limit=1)
        if stock_picking:
            return {
                'success': True,
                'data': {
                    'type': 'stock_picking',
                    'id': stock_picking.id,
                }
            }

        return {
            'success': False,
            'error': 'Can not find by code ' + search
        }
