from . import base_controller
from odoo import http
from odoo.http import request
import barcode
from barcode.writer import ImageWriter
import io
import base64
import re
from odoo.addons.inven_barcode_app.utils import barcode_util

class StockQuantityPackageController(base_controller.BaseAPIController):
    
    @http.route('/api/stock-qty-package', type='json', auth='user', methods=['POST'], csrf=False)
    def get_list(self):
        
        context = self._set_context()
        active_company_id = context.get('company_id') or context['allowed_company_ids'][0]
        domain = ['|', ('company_id', '=', active_company_id), ('company_id', '=', False)]
        
        list = request.env['stock.quant.package'].search(
            domain,
            order='create_date DESC'
        )
        
        return {
            'success': True,
            'data': [self._format_package_response(package) for package in list],
        }
        
    @http.route('/api/stock-qty-package/search', type='json', auth='user', methods=['POST'], csrf=False)
    def search_list(self, search):
        
        context = self._set_context()
        active_company_id = context.get('company_id') or context['allowed_company_ids'][0]
        domain = [
            '|', 
            ('company_id', '=', active_company_id), 
            ('company_id', '=', False), 
            ('name', '=', search)
        ]
        
        list = request.env['stock.quant.package'].search(
            domain,
            order='create_date DESC'
        )
        
        return {
            'success': True,
            'data': [self._format_package_response(package) for package in list],
        }
        
    @http.route('/api/stock-qty-package/find-or-create', type='json', auth='user', methods=['POST'], csrf=False)
    def find_or_create(self, package_name):
        
        context = self._set_context()
        active_company_id = context.get('company_id') or context['allowed_company_ids'][0]
        domain = [
            '|', 
            ('company_id', '=', active_company_id), 
            ('company_id', '=', False), 
            ('name', '=', package_name)
        ]
        
        package = request.env['stock.quant.package'].search(
            domain,
            limit = 1
        )
        
        if package.exists():
            return {
                'success': True,
                'data': self._format_package_response(package),
            }
             
        barcode_formatted = request.env['barcode.rule'].sudo().search([
            ('barcode_nomenclature_id.is_gs1_nomenclature', '=', False),
            ('type', '=', 'package')
        ], order='sequence ASC')
        
        if barcode_formatted:
            new_package = False
            for barcode_for in barcode_formatted:
                if package_name.startswith(barcode_for.pattern):
                    new_package = True
                    break
            
            if new_package:
                package = request.env['stock.quant.package'].create({
                    'name': package_name
                })
                
                new_sequence = barcode_util.extract_number_from_barcode(barcode_for.pattern, package_name)
                current_sequence = request.env['ir.sequence'].search([
                    ('company_id', 'in', (active_company_id, False)),
                    ('code', '=', 'stock.quant.package'),
                    ('prefix', '=', barcode_for.pattern),
                ], order='company_id', limit=1)
                
                if current_sequence and new_sequence and current_sequence.number_next <= new_sequence:
                    current_sequence.write({
                        'number_next': new_sequence + 1
                    })
                
                return {
                    'success': True,
                    'data': self._format_package_response(package),
                }

        return {
            'success': False,
            'error': 'Package Not Found',
        }
             
        
        
    
    @http.route('/api/stock-qty-package/paginate', type='json', auth='user', methods=['POST'], csrf=False)
    def get_paginate_list(self, page = 1, page_size = 50):
        # Ensure page and page_size are integers
        try:
            page = int(page)
            page_size = int(page_size)
        except ValueError:
            return {'success': False, 'error': 'Page and page_size must be integers.'}
        
        context = self._set_context()
        active_company_id = context.get('company_id') or context['allowed_company_ids'][0]
        domain = ['|', ('company_id', '=', active_company_id), ('company_id', '=', False)]
        
        list = request.env['stock.quant.package'].search(
            domain, 
            limit=page_size,
            offset=(page - 1) * page_size,
            order='create_date DESC'
        )
        
        total_count = request.env['stock.quant.package'].search_count(domain)
        has_more = page * page_size < total_count
        response_data = {
            'total_count': total_count,
            'has_more': has_more,
            'records': [self._format_package_response(package) for package in list]
        }
        
        return {
            'success': True,
            'data': response_data,
        }
        
    @http.route('/api/stock-qty-package/create', type='json', auth='user', methods=['POST'], csrf=False)
    def create_stock_qty_package(self, **post):
        line_data_list = post.get('line_data') or []
        picking_id = post.get('picking_id')
        
        if not picking_id:
            return {
                'success': False,
                'error': 'Missing picking id',
            }
        
        for line_data in line_data_list:
            if line_data['id']:
                line = request.env['stock.move.line'].browse(line_data['id'])
               
                if not line:
                   return {
                       'success': False,
                       'error': 'Stock Move Line not found',
                   } 

                line.write(line_data)
            else:
                line.create(line_data)
        
        picking = request.env['stock.picking'].browse(picking_id)
        
        if not picking:
             return {
                'success': False,
                'error': 'Picking not found',
            }
            
        if not post.get('package_name'):
            picking.action_put_in_pack()
        else:
            picking.action_put_in_pack_with_specific_name(post.get('package_name'))
        
        return {
            'success': True,
        }
        
    @http.route('/api/stock-qty-package/show', type='json', auth='user', methods=['POST'])
    def get_package_detail(self, id):
        # Lấy sản phẩm từ ID
        package = request.env['stock.quant.package'].sudo().browse(id)
        if not package:
            return {
                'success': False,
                'error': 'Package not found.'
            }

        # Chi tiết sản phẩm
        package_detail = self._format_package_response(package)

        return {
            'success': True,
            'data': package_detail
        }
    
    def _format_package_response(self, package):
        # Use python-barcode to generate the barcode
        code128 = barcode.get('code128', package.name, writer=ImageWriter())
        buffer = io.BytesIO()  # Create a BytesIO buffer

        try:
            code128.write(buffer)  # Write the barcode to the buffer
            buffer.seek(0)  # Move to the beginning of the buffer

            # Convert the buffer content to base64
            barcode_image = base64.b64encode(buffer.read()).decode('utf-8')

        except Exception as e:
            barcode_image = False
        finally:
            buffer.close()  # Ensure the buffer is closed to free up resources
            
        return {
            'id': package.id,
            'name': package.name,
            'type': {
                'id': package.package_type_id.id,
                'name': package.package_type_id.name,
            },
            'package_use': package.package_use,
            'package_date': package.pack_date,
            'barcode_image': barcode_image,
            'stock_quants': [
                {
                    'id': stock_quant.id,
                    'product': {
                        'id': stock_quant.product_id.id,
                        'name': stock_quant.product_id.display_name,
                        'product_uom': {
                            'id': stock_quant.product_id.uom_id.id,
                            'name': stock_quant.product_id.uom_id.display_name,
                        },
                        'barcode': stock_quant.product_id.barcode,
                    },
                    'location': {
                        'id': stock_quant.location_id.id,
                        'name': stock_quant.location_id.display_name,
                    },
                    'quantity': stock_quant.quantity,
                    'user_id': stock_quant.user_id.id if stock_quant.user_id else False,
                    'inventory_quantity_set': stock_quant.inventory_quantity_set,
                } for stock_quant in package.quant_ids
            ]
        }