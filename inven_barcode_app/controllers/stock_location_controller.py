from odoo import http
from odoo.http import request
from . import base_controller

class StockLocationController(base_controller.BaseAPIController):

    @http.route('/api/stock-locations', type='json', auth='user', methods=['POST'], csrf=False)
    def get_stock_location_list(self):
        try:
            context = self._set_context()
            active_company_id = context.get('company_id') or context['allowed_company_ids'][0]
            location_domain = ['|', ('company_id', '=', active_company_id), ('company_id', '=', False), ('usage', '<>', 'view')]
            locations = request.env['stock.location'].sudo().search(location_domain)
            location_data = [
                {
                    'id': location.id,
                    'name': location.display_name,
                } for location in locations
            ]

            return {
                'success': True,
                'data': location_data,
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    @http.route('/api/stock-locations/find-from-barcode', type='json', auth='user', methods=['POST'], csrf=False)
    def find_from_barcode(self, barcode):
        if not barcode:
            return {
                'success': False,
                'error': 'barcode là bắt buộc'
            }

        context = self._set_context()

        active_company_id = context.get('company_id') or context['allowed_company_ids'][0]
        domain = [('company_id', '=', active_company_id)]

        stock_location = request.env['stock.location'].sudo().search(domain + [('barcode', '=', barcode)], limit=1)

        if stock_location:
            return {
                'success': True,
                'data': {
                    'id': stock_location.id,
                    'name': stock_location.display_name,
                }
            }

        return {
            'success': False,
            'error': 'stock location not found'
        }