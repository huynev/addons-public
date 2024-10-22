from odoo import http
from . import base_controller
from odoo.http import request

class WarehouseController(base_controller.BaseAPIController):

    @http.route('/api/warehouses', type='json', auth='user', methods=['POST'], csrf=False)
    def get_warehouse_list(self):
        context = self._set_context()

        # Search for stock.warehouse records based on the type
        active_company_id = context.get('company_id') or context['allowed_company_ids'][0]
        domain = [('company_id', '=', active_company_id)]

        # Lấy danh sách các kho hàng thuộc công ty
        warehouses = request.env['stock.warehouse'].search(domain)

        return {
            'success': True,
            'data': [{
                'id': warehouse.id,
                'name': warehouse.display_name,
            } for warehouse in warehouses]
        }