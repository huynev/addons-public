from odoo import http
from odoo.http import request
import barcode
from barcode.writer import ImageWriter
import io
import base64

class ProductController(http.Controller):
    @http.route('/api/products', type='json', auth='user', methods=['POST'], csrf=False)
    def get_product_list(self, page=1, page_size=50):
        # Ensure page and page_size are integers
        try:
            page = int(page)
            page_size = int(page_size)
        except ValueError:
            return {'success': False, 'error': 'Page and page_size must be integers.'}

        domain = [('type', 'in', ['product', 'consu'])];

        # Fetch product.product records
        products = request.env['product.product'].sudo().search(domain,
                                                                    limit=page_size,
                                                                    offset=(page - 1) * page_size,
                                                                    )

        total_count = request.env['product.product'].sudo().search_count(domain)
        has_more = page * page_size < total_count
        # Prepare the response data
        response_data = {
            'total_count': total_count,
            'has_more': has_more,
            'product_records': []
        }

        for product in products:
            response_data['product_records'].append({
                'id': product.id,
                'name': product.display_name,
                'description': product.description_sale or product.description,
                'price': {
                    'list_price': product.list_price,
                    'cost_price': product.standard_price,
                },
                'quantity': {
                    'available': product.qty_available,
                    'incoming': product.incoming_qty,
                    'outgoing': product.outgoing_qty,
                    'forecast': product.virtual_available,
                },
                'uom': {
                    'id': product.uom_id.id, # Đơn vị đo lường
                    'name': product.uom_id.display_name,
                },
                'category': {   # Danh mục sản phẩm
                    'id': product.categ_id.id,
                    'name': product.categ_id.display_name,
                },
                'product_image': product.image_1920,
                'currency': {
                    'id': product.currency_id.id,
                    'name': product.currency_id.name,
                    'symbol': product.currency_id.symbol,
                    'position': product.currency_id.position,  # Vị trí của ký hiệu tiền tệ (trước/sau giá)
                },
            })

        return {'success': True, 'data': response_data}


    @http.route('/api/products/get-by-barcodes', type='json', auth='user', methods=['POST'])
    def get_products_by_barcodes(self, barcodes):
        """
        Method to get products based on a list of barcodes
        """
        try:
            # Ensure barcodes is a list
            if not isinstance(barcodes, list):
                return {'success': False, 'error': 'Invalid data format, expected a list of barcodes'}

            # Search for products using the barcodes
            products = request.env['product.product'].sudo().search([('barcode', 'in', barcodes)])

            # Prepare the result to send back
            product_data = []
            for product in products:
                # Get the product_uom_id from the product
                product_uom = product.uom_id  # This is the default UoM for the product

                product_data.append({
                    'id': product.id,
                    'name': product.display_name,
                    'barcode': product.barcode,
                    'product_uom_id': product_uom.id,
                    'product_uom_name': product_uom.name,
                })

            # Return the product data as JSON
            return {'success': True, 'data': product_data}

        except Exception as e:
            return {'success': False, 'error': str(e)}


    @http.route('/api/products/show', type='json', auth='user', methods=['POST'])
    def get_product_detail(self, id):
        # Lấy sản phẩm từ ID
        product = request.env['product.product'].sudo().browse(id)
        if not product:
            return {
                'success': False,
                'error': 'Product not found.'
            }

        if product.barcode:
            # Use python-barcode to generate the barcode
            code128 = barcode.get('code128', product.barcode, writer=ImageWriter())
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

        else:
            barcode_image = False

        # Chi tiết sản phẩm
        product_details = {
            'id': product.id,
            'name': product.display_name,
            'description': product.description_sale or product.description,
            'price': {
                'list_price': product.list_price,
                'cost_price': product.standard_price,
            },
            'quantity': {
                'available': product.qty_available,
                'incoming': product.incoming_qty,
                'outgoing': product.outgoing_qty,
                'forecast': product.virtual_available,
            },
            'uom': {
                'id': product.uom_id.id, # Đơn vị đo lường
                'name': product.uom_id.display_name,
            },
            'category': {   # Danh mục sản phẩm
                'id': product.categ_id.id,
                'name': product.categ_id.display_name,
            },
            'barcode': product.barcode,
            'barcode_image': barcode_image,
            'product_image': product.image_1920,
            'currency': {
                'id': product.currency_id.id,
                'name': product.currency_id.name,
                'symbol': product.currency_id.symbol,
                'position': product.currency_id.position,  # Vị trí của ký hiệu tiền tệ (trước/sau giá)
            },
        }

        return {
            'success': True,
            'data': product_details
        }