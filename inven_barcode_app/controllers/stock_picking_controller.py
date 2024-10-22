from odoo import http
from odoo.http import request
import barcode
from barcode.writer import ImageWriter
import io
import base64
from odoo.exceptions import ValidationError
from . import base_controller
import logging

_logger = logging.getLogger(__name__)


class StockPickingController(base_controller.BaseAPIController):

    @http.route('/api/stock-picking', type='json', auth='user', methods=['POST'], csrf=False)
    def get_stock_picking(self, picking_type=None, page=1, page_size=50):
        # Ensure page and page_size are integers
        try:
            page = int(page)
            page_size = int(page_size)
        except ValueError:
            return {'success': False, 'error': 'Page and page_size must be integers.'}

        # set context
        context = self._set_context()

        # Search for stock.picking records based on the type
        active_company_id = context.get('company_id') or context['allowed_company_ids'][0]
        domain = [('company_id', '=', active_company_id)]
        if picking_type:
            domain.append(('picking_type_id.code', '=', picking_type))

        state = request.params.get('state')
        if state:
            if isinstance(state, str):
                domain.append(('state', '=', state))
            elif isinstance(state, list):
                domain.append(('state', 'in', state))

        src_location_id = request.params.get('source_location_id')
        if src_location_id:
            if isinstance(src_location_id, str):
                domain.append(('location_id', '=', src_location_id))
            elif isinstance(src_location_id, list):
                domain.append(('location_id', 'in', src_location_id))

        dest_location_id = request.params.get('dest_location_id')
        if dest_location_id:
            if isinstance(dest_location_id, str):
                domain.append(('location_dest_id', '=', dest_location_id))
            elif isinstance(dest_location_id, list):
                domain.append(('location_dest_id', 'in', dest_location_id))

        warehouse_id = request.params.get('warehouse_id')
        if warehouse_id:
            if isinstance(warehouse_id, str):
                domain.append(('picking_type_id.warehouse_id', '=', warehouse_id))
            elif isinstance(warehouse_id, list):
                domain.append(('picking_type_id.warehouse_id', 'in', warehouse_id))

        # Fetch stock.picking records
        stock_pickings = request.env['stock.picking'].sudo().search(domain,
                                                                    limit=page_size,
                                                                    offset=(page - 1) * page_size,
                                                                    order='scheduled_date DESC, create_date DESC'
                                                                    )

        total_count = request.env['stock.picking'].sudo().search_count(domain)
        has_more = page * page_size < total_count
        # Prepare the response data
        response_data = {
            'total_count': total_count,
            'has_more': has_more,
            'picking_records': []
        }

        for picking in stock_pickings:
            response_data['picking_records'].append({
                'id': picking.id,
                'name': picking.display_name,
                'state': picking.state,
                'location': {
                    'id': picking.location_id.id,
                    'name': picking.location_id.display_name,
                },
                'dest_location': {
                    'id': picking.location_dest_id.id,
                    'name': picking.location_dest_id.display_name,
                },
                'picking_type': {
                    'id': picking.picking_type_id.id,
                    'name': picking.picking_type_id.display_name,
                    'code': picking.picking_type_id.code,
                },

                # Add other fields as needed
            })

        return {'success': True, 'data': response_data}

    def _get_default_picking_values_from_type(self, picking_type):
            # Check the operation type (receipt, delivery, or internal)
            if picking_type == 'incoming':
                picking_type = request.env.ref('stock.picking_type_in')
                source_location = request.env.ref('stock.stock_location_suppliers')  # Vendors/Suppliers
                destination_location = request.env.ref('stock.stock_location_stock')  # WH/Stock

            elif picking_type == 'outgoing':
                picking_type = request.env.ref('stock.picking_type_out')
                source_location = request.env.ref('stock.stock_location_stock')  # WH/Stock
                destination_location = request.env.ref('stock.stock_location_customers')  # Customers

            elif picking_type == 'internal':
                picking_type = request.env.ref('stock.picking_type_internal')
                source_location = request.env.ref('stock.stock_location_stock')  # WH/Stock
                destination_location = request.env.ref('stock.stock_location_stock')  # WH/Stock

            else:
                raise ValidationError('Invalid picking type')

            return {
                'picking_type': picking_type,
                'source_location': source_location,
                'destination_location': destination_location,
            }

    # Get default values for stock picking create
    @http.route('/api/stock-picking/create', type='json', auth='user', methods=['POST'], csrf=False)
    def get_default_picking_values(self, picking_type):
        self._set_context()

        try:
            data = self._get_default_picking_values_from_type(picking_type)

            picking_type = data['picking_type']
            source_location = data['source_location']
            destination_location = data['destination_location']

            # Prepare the response data
            response_data = {
                'picking_type_id': picking_type.id if picking_type else False,
                'picking_type_name': picking_type.display_name if picking_type else False,
                'location_id': source_location.id if source_location else False,
                'location_name': source_location.display_name if source_location else False,
                'location_dest_id': destination_location.id if destination_location else False,
                'location_dest_name': destination_location.display_name if destination_location else False,
            }

            return {'success': True, 'data': response_data}

        except Exception as e:
            return {'success': False, 'error': str(e)}

    @http.route('/api/stock-picking/default-from-source-barcode', type='json', auth='user', methods=['POST'],
                csrf=False)
    def get_picking_type_from_source_barcode(self, **post):
        # Get the barcode from the request
        barcode = post.get('barcode')
        type = post.get('type')
        dest_id = post.get('dest_location_id')

        if not barcode or not type or not dest_id:
            return {
                'success': False,
                'error': 'Missing Params'
            }

        try:
            context = self._set_context()
            active_company_id = context.get('company_id')
            primary_domain = [('company_id', 'in', [active_company_id, False])]
            domain = [('company_id', '=', active_company_id)]

            # Search for the source location using the barcode
            source_location = request.env['stock.location'].sudo().search(primary_domain + [('barcode', '=', barcode)], limit=1)

            if not source_location:
                return {
                    'success': False,
                    'error': f"Source location with barcode '{barcode}' not found."
                }

            # Find picking type
            picking_type = request.env['stock.picking.type'].sudo().search(domain + [
                ('code', '=', type),
                ('default_location_src_id', '=', source_location.id),
                ('default_location_dest_id', '=', dest_id)
            ], limit=1)
            dest_location = request.env['stock.location'].sudo().search(primary_domain + [('id', '=', dest_id)], limit=1)

            if not picking_type and type == 'incoming':
                loop = 1

                while not picking_type and loop < 4:
                    if loop == 1:
                        picking_type = request.env['stock.picking.type'].sudo().search(domain + [
                            ('code', '=', type),
                            ('default_location_src_id', '=', source_location.id),
                        ], limit=1)
                    else:
                        default_src_location = request.env.ref('stock.stock_location_suppliers')  # Vendors/Suppliers

                        if default_src_location.id == source_location.id:
                            if loop == 2:
                                picking_type = request.env['stock.picking.type'].sudo().search(domain + [
                                    ('code', '=', type),
                                    ('default_location_src_id', '=', False),
                                    ('default_location_dest_id', '=', dest_id)
                                ], limit=1)

                            if loop == 3:
                                picking_type = request.env['stock.picking.type'].sudo().search(domain + [
                                    ('code', '=', type),
                                    ('default_location_src_id', '=', False),
                                ], limit=1)
                        else:
                            loop = 3

                    loop += 1
            elif not picking_type and type == 'outgoing':
                default_dest_location = request.env.ref('stock.stock_location_customers')  # Customers
                if default_dest_location.id == dest_id:
                    picking_type = request.env['stock.picking.type'].sudo().search(domain + [
                        ('code', '=', type),
                        ('default_location_src_id', '=', source_location.id),
                        ('default_location_dest_id', '=', False)
                    ], limit=1)


            # Return the picking type ID and name
            return {
                'success': True,
                'data': {
                    'picking_type_id': picking_type.id if picking_type is not None else False,
                    'picking_type_name': picking_type.display_name if picking_type is not None else False,
                    'location_id': source_location.id,
                    'location_name': source_location.display_name,
                    'location_dest_id': dest_location.id if dest_location is not None else False,
                    'location_dest_name': dest_location.display_name if dest_location is not None else False,
                }
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    @http.route('/api/stock-picking/default-from-dest-barcode', type='json', auth='user', methods=['POST'],
                csrf=False)
    def get_picking_type_from_dest_barcode(self, **post):
        # Get the barcode from the request
        barcode = post.get('barcode')
        type = post.get('type')
        source_id = post.get('source_location_id')

        if not barcode or not type or not source_id:
            return {
                'success': False,
                'error': ' Missing Params'
            }

        try:
            context = self._set_context()
            active_company_id = context.get('company_id')
            primary_domain = [('company_id', 'in', [active_company_id, False])]
            domain = [('company_id', '=', active_company_id)]

            # Search for the source location using the barcode
            dest_location = request.env['stock.location'].sudo().search(primary_domain + [('barcode', '=', barcode)], limit=1)

            if not dest_location:
                return {
                    'success': False,
                    'error': f"Dest location with barcode '{barcode}' not found."
                }

            # Find Picking Type
            picking_type = request.env['stock.picking.type'].sudo().search(domain + [
                ('code', '=', type),
                ('default_location_dest_id', '=', dest_location.id),
                ('default_location_src_id', '=', source_id)
            ], limit=1)
            source_location = request.env['stock.location'].sudo().search(primary_domain + [('id', '=', source_id)],
                                                                        limit=1)

            if type == 'outgoing':
                loop = 1

                while not picking_type and loop < 4:
                    if loop == 1:
                        picking_type = request.env['stock.picking.type'].sudo().search(domain + [
                            ('code', '=', type),
                            ('default_location_dest_id', '=', dest_location.id),
                        ], limit=1)
                    else:
                        default_dest_location = request.env.ref('stock.stock_location_customers')  # Customers

                        if default_dest_location.id == dest_location.id:
                            if loop == 2:
                                picking_type = request.env['stock.picking.type'].sudo().search(domain + [
                                    ('code', '=', type),
                                    ('default_location_dest_id', '=', False),
                                    ('default_location_src_id', '=', source_id)
                                ], limit=1)
                            if loop == 3:
                                picking_type = request.env['stock.picking.type'].sudo().search(domain + [
                                    ('code', '=', type),
                                    ('default_location_dest_id', '=', False),
                                ], limit=1)
                        else:
                            loop = 3

                    loop += 1
            elif not picking_type and type == 'incoming':
                default_src_location = request.env.ref('stock.stock_location_suppliers')  # Vendors/Suppliers
                if default_src_location.id == source_location.id:
                    picking_type = request.env['stock.picking.type'].sudo().search(domain + [
                        ('code', '=', type),
                        ('default_location_src_id', '=', False),
                        ('default_location_dest_id', '=', dest_location.id)
                                                                                   ], limit=1)



            # Return the picking type ID and name
            return {
                'success': True,
                'data': {
                    'picking_type_id': picking_type.id if picking_type is not None else False,
                    'picking_type_name': picking_type.display_name if picking_type is not None else False,
                    'location_id': source_location.id if source_location is not None else False,
                    'location_name': source_location.display_name if source_location is not None else False,
                    'location_dest_id': dest_location.id,
                    'location_dest_name': dest_location.display_name,
                }
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    @http.route('/api/stock-picking/add-move', type='json', auth='user', methods=['POST'])
    def add_move(self, id, product_data):
        """
        Method to add new Stock Move to Stock Picking
        :param id: id of stockpicking
        :param productId: product id of stockpicking
        """
        try:
            stock_picking = request.env['stock.picking'].sudo().browse(id)

            if not  stock_picking:
                return {
                    'success': False,
                    'error': f"Stock Picking with id '{id}' not found."
                }

            # Create stock.move records
            move = request.env['stock.move'].sudo().create({
                'name': product_data.get('product_name', ''),
                'product_id': product_data.get('product_id'),
                'product_uom_qty': product_data.get('product_uom_qty', 0),
                'product_uom': product_data.get('product_uom'),  # UoM ID
                'picking_id': stock_picking.id,  # Link to the stock picking
                'location_id': stock_picking.location_id.id,  # Source location
                'location_dest_id': stock_picking.location_dest_id.id,  # Destination location
            })

            # Return success response
            return {
                'success': True,
                'message': 'Stock picking created successfully.',
                'data': {
                    'id': move.id,
                    'product': {
                        'id': move.product_id.id,
                        'name': move.product_id.display_name,
                    },
                    'product_uom_qty': move.product_uom_qty,
                    'product_uom': {
                        'id': move.product_uom.id,
                        'name': move.product_uom.display_name,
                    },
                }
            }

        except Exception as e:
            return {'success': False, 'error': str(e), }

    @http.route('/api/stock-picking/store', type='json', auth='user', methods=['POST'])
    def save_stock_picking(self, picking_data):
        """
        Method to save a new stock picking record.
        :param picking_data: JSON object containing the details of the stock picking.
        """
        try:
            # Validate incoming data
            if not picking_data or not isinstance(picking_data, dict):
                return {'success': False, 'error': 'Invalid data format. Expecting a dictionary.'}

            update_data = {
                'picking_type_id': picking_data.get('picking_type_id'),
                'location_id': picking_data.get('location_id'),
                'location_dest_id': picking_data.get('location_dest_id'),
            }
            StockPicking = request.env['stock.picking']
            if 'id' in picking_data and picking_data['id']:
                # Update existing stock.picking
                stock_picking = StockPicking.sudo().browse(picking_data['id'])
                if stock_picking.exists() and stock_picking.state != 'done':
                    stock_picking.write(update_data)
                    moves = stock_picking.move_ids_without_package
                    if moves:
                        moves.unlink()  # This will delete all stock moves related to this picking
                else:
                    return {'status': 'error', 'message': f'Stock Picking with ID {picking_data["id"]} does not exist or in done status.'}
            else:
                # Create the stock picking record
                stock_picking = StockPicking.sudo().create(update_data)

            # Prepare move lines to create stock.move records
            move_lines = []
            for move in picking_data.get('move_lines', []):
                move_lines.append({
                    'name': move.get('name', ''),
                    'product_id': move.get('product_id'),
                    'product_uom_qty': move.get('product_uom_qty', 0),
                    'product_uom': move.get('product_uom'),  # UoM ID
                    'picking_id': stock_picking.id,  # Link to the stock picking
                    'location_id': picking_data.get('location_id'),  # Source location
                    'location_dest_id': picking_data.get('location_dest_id'),  # Destination location
                })

            # Create stock.move records
            if move_lines:
                request.env['stock.move'].sudo().create(move_lines)

            # Return success response
            return {
                'success': True,
                'message': 'Stock picking created successfully.',
                'picking_id': stock_picking.id,
            }

        except Exception as e:
            return {'success': False, 'error': str(e), }

    @http.route('/api/stock-picking/show', type='json', auth='user', methods=['POST'])
    def get_stock_picking_details(self, id):
        """
        Get the details of a stock.picking and its stock.move.lines by the stock picking ID.
        :param picking_id: int, ID of the stock.picking record
        :return: dict, details of stock picking including move lines
        """
        # Search for the stock picking by its ID
        picking = request.env['stock.picking'].sudo().browse(id)

        # Check if the picking exists
        if not picking.exists():
            return {'success': False, 'error': 'Stock picking not found'}

        if picking.barcode:
            # Use python-barcode to generate the barcode
            code128 = barcode.get('code128', picking.barcode, writer=ImageWriter())
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

        # Prepare the stock picking details including move lines
        picking_details = {
            'id': picking.id,
            'name': picking.display_name,
            'partner_id': picking.partner_id.name if picking.partner_id else None,
            'scheduled_date': picking.scheduled_date,
            'origin': picking.origin,
            'state': picking.state,
            'barcode': picking.barcode if picking.barcode else None,
            'barcode_image': barcode_image if picking.barcode else None,
            'location': {
                'id': picking.location_id.id,
                'name': picking.location_id.display_name,
            },
            'dest_location': {
                'id': picking.location_dest_id.id,
                'name': picking.location_dest_id.display_name,
            },
            'picking_type': {
                'id': picking.picking_type_id.id,
                'name': picking.picking_type_id.display_name,
                'code': picking.picking_type_id.code,
            },
            'move_lines': [{
                'id': move.id,
                'product': {
                    'id': move.product_id.id,
                    'name': move.product_id.display_name,
                },
                'product_uom_qty': move.product_uom_qty,
                'product_uom': {
                    'id': move.product_uom.id,
                    'name': move.product_uom.display_name,
                },
                'move_line_ids': [{
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
                } for line in move.move_line_ids],
            } for move in picking.move_ids_without_package],
        }

        return {
            'success': True,
            'data': picking_details
        }

    @http.route('/api/stock-picking/validate', type='json', auth='user', methods=['POST'], csrf=False)
    def validate_stock_picking(self, picking_id, move_lines_data, create_backorder):
        """
        Remove all move_lines in the picking, create new ones, and validate the picking.
        :param picking_id: The ID of the stock.picking to update.
        :param move_lines_data: List of new move_lines data to create.
        :param create_backorder: Create backorder if move_line don't have enough quantity
        :return: JSON response with success or error message.
        """
        # Tìm phiếu nhập hàng theo ID
        picking = request.env['stock.picking'].sudo().browse(picking_id)

        # Kiểm tra xem phiếu nhập hàng có tồn tại không
        if not picking or picking.state == 'done':
            return {'success': False, 'error': 'Stock picking not found or completed'}

        try:
            # Xóa tất cả các move_lines hiện có
            picking.move_line_ids.unlink()

            # Tạo mới các move_lines dựa trên dữ liệu từ body request
            new_move_lines = []
            move_id = 0
            for line_data in move_lines_data:
                new_move_lines.append({
                    'product_id': line_data.get('product_id'),
                    'quantity': line_data.get('quantity'),
                    'move_id': line_data.get('move_id'),
                    'location_id': picking.location_id.id,
                    'location_dest_id': picking.location_dest_id.id,
                    'product_uom_id': line_data.get('product_uom_id'),
                    'picked': True
                })
                move_id = line_data.get('move_id')

            # Tạo các dòng chuyển động mới cho phiếu nhập hàng
            picking.write({
                'move_line_ids': [(0, 0, move_line) for move_line in new_move_lines]
            })

            # Xác nhận phiếu nhập hàng
            ctx = {
                'button_validate_picking_ids': [picking.id],  # Đặt ID của picking hiện tại
            }
            if create_backorder:
                # Xác nhận phiếu và kích hoạt tạo backorder nếu cần
                picking.with_context(ctx).process_validate_with_backorder()
            else:
                picking.with_context(ctx).process_validate_without_backorder()

            # Kiểm tra trạng thái của phiếu
            if picking.state != 'done':
                raise ValidationError(
                    "The picking could not be validated and marked as 'done'. Check if all conditions are met.")

            return {
                'success': True,
                'message': 'Stock picking updated and validated successfully',
                'picking_id': picking_id,
                'backorders': [backorder.id for backorder in picking.backorder_ids],
            }

        except ValidationError as e:
            return {'success': False, 'error': str(e)}
        except Exception as e:
            return {'success': False, 'error': f'An unexpected error occurred: {str(e)}'}
