from . import base_controller
from odoo.http import request
from odoo import http
from datetime import datetime, time
from odoo.exceptions import ValidationError


class StockQuantController(base_controller.BaseAPIController):

    @http.route('/api/stock-quantity', type='json', auth='user', methods=['POST'], csrf=False)
    def get_stock_quantity_list(self):
        context = self._set_context()

        # Get the current date
        today = datetime.combine(datetime.now(), time.max)

        # Search for stock.warehouse records based on the type
        active_company_id = context.get('company_id') or context['allowed_company_ids'][0]
        domain = [
            ('company_id', '=', active_company_id),
            ('inventory_date', '<=', today),
            ('user_id', 'in', [False, context.get('uid')])
        ]

        # Lấy danh sách các kho hàng thuộc công ty
        stock_quant_list = request.env['stock.quant'].search(domain)

        return {
            'success': True,
            'data': [
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
                } for stock_quant in stock_quant_list
            ]
        }

    @http.route('/api/stock-quantity/apply', type='json', auth='user', methods=['POST'], csrf=False)
    def apply_inventory(self, data):
        context = self._set_context()

        try:

            if isinstance(data, list):
                validate_data = data
            else:
                validate_data = [data]

            active_company_id = context.get('company_id') or context['allowed_company_ids'][0]
            domain = [
                ('company_id', '=', active_company_id),
                ('user_id', 'in', [False, context.get('uid')])
            ]

            for val in validate_data:
                stock_quant = request.env['stock.quant'].search(domain + [
                    ('id', '=', val.get('id')),
                ], limit=1)

                if not stock_quant:
                    raise ValidationError('Không tìm thấy sản phẩm kiểm kho tương ứng.')

                stock_quant.inventory_quantity = val.get('inventory_quantity')
                stock_quant.action_apply_inventory()

            return {
                'success': True,
                'message': 'Validate succeed',
            }

        except ValidationError as e:
            return {'success': False, 'error': str(e)}
        except Exception as e:
            return {'success': False, 'error': f'An unexpected error occurred: {str(e)}'}

    @http.route('/api/stock-quantity/find-by-barcode', type='json', auth='user', methods=['POST'], csrf=False)
    def find_by_barcode(self, barcode):
        if not barcode:
            return {
                'success': False,
                'error': 'barcode is required'
            }

        context = self._set_context()
        active_company_id = context.get('company_id') or context['allowed_company_ids'][0]
        domain = [('company_id', '=', active_company_id), ('product_id.barcode', '=', barcode)]

        stock_quants = request.env['stock.quant'].search(domain)

        return {
            'success': True,
            'data': [
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
                } for stock_quant in stock_quants
            ]
        }