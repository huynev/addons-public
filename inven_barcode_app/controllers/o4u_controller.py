from . import base_controller
from odoo import http

class o4u_controller(base_controller.BaseAPIController):
    @http.route('/api/o4u/stock-barcode', type='json', auth='user', methods=['POST'], csrf=False)
    def module_info(self):
        return {
            'success': True,
            'data': {}
        }