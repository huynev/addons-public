from odoo import http
from odoo.http import request
import base64
from . import base_controller
import json

class StockDoneImageController(base_controller.BaseAPIController):
    
    @http.route('/api/stock-done-image', type='json', auth='user', methods=['POST'], csrf=False)
    def get_images(self, **kwargs):
        if 'picking_id' not in kwargs:
            return request.make_response('Missing picking_id data', status=400)
        
        picking_done_images = request.env['stock.done.image'].search([('picking_id', '=', kwargs.get('picking_id'))])
        
        return {
            'success': True,
            'data': [{
                'id': image.id,
                'name': image.name,
                'image': image.image
            } for image in picking_done_images]
        }
    
    @http.route('/api/stock-done-image/upload', type='http', auth='user', methods=['POST'], csrf=False)
    def upload_image(self, **kwargs):
        # Ensure file is in the request
        if 'image' not in kwargs:
            return request.make_response("No file uploaded", status=400)
        if 'picking_id' not in kwargs:
            return request.make_reponse('Missing param picking_id', status = 400)

        # Get the image file from the request
        image_file = kwargs.get('image')

        # Encode image data as base64 for storage
        image_base64 = base64.b64encode(image_file.read()).decode('utf-8')

        # Create a record in the model with the image
        record = request.env['stock.done.image'].create({
            'picking_id': kwargs.get('picking_id'),
            'name': kwargs.get('name', 'Default Name'),  # Example additional data
            'image': image_base64,  # Field where image data is saved
        })

        # Respond with success message or redirect
        return request.make_response(json.dumps({
            'success': True,
            'data': {
                'id': record.id,
            }
        }), headers=[('Content-Type', 'application/json')], status=200)
    
    @http.route('/api/stock-done-image/delete', type='json', auth='user', methods=['POST'], csrf=False)
    def delete_image_and_record(self, record_id):
        # Find the record by ID
        record = request.env['stock.done.image'].sudo().browse(record_id)

        # Check if the record exists
        if not record.exists():
            return {'status': 'error', 'message': 'Record not found'}

        # Delete the entire record
        record.unlink()

        # Respond with success message
        return {'success': True, 'message': 'Record and image deleted successfully'}