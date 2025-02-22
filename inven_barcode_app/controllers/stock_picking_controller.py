from odoo import http
from odoo.http import request, Response, content_disposition
import barcode
from barcode.writer import ImageWriter
import io
import base64
from odoo.exceptions import ValidationError
from . import base_controller
import logging
from odoo.addons.inven_barcode_app.utils import barcode_util

_logger = logging.getLogger(__name__)


class StockPickingController(base_controller.BaseAPIController):

    @http.route('/api/stock-picking', type='json', auth='user', methods=['POST'], csrf=False)
    def get_stock_picking(self, picking_type=None, page=1, page_size=50, exclude_ids=[]):
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
        domain = [('company_id', '=', active_company_id), ('id', 'not in', exclude_ids)]
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
            
            request.env['stock.move.line'].create(
                {
                    'move_id': move.id,
                    'quantity': product_data.get('product_uom_qty', 0),
                    'product_uom_id': product_data.get('product_uom'),  
                    'product_id': product_data.get('product_id'),  
                }
            )

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

        # Prepare the stock picking details including move lines
        picking_details = self._format_picking_response(picking)

        return {
            'success': True,
            'data': picking_details
        }

    @http.route('/api/stock-picking/validate', type='json', auth='user', methods=['POST'], csrf=False)
    def validate_stock_picking(self, picking_id):
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
            result = picking.with_context(**{
                'from_api': True
            }).button_validate()
            
            # Kiểm tra trạng thái của phiếu
            if result != True:
                return {
                    'success': True,
                    'type': result
                }

            return {
                'success': True,
                'type': 'done',
                'message': 'Stock picking updated and validated successfully',
                'picking_id': picking_id,
                'backorders': [backorder.id for backorder in picking.backorder_ids],
            }

        except ValidationError as e:
            return {'success': False, 'error': str(e)}
        except Exception as e:
            return {'success': False, 'error': f'An unexpected error occurred: {str(e)}'}
        
    
    @http.route('/api/stock-picking/validate-sms', type='json', auth='user', methods=['POST'], csrf=False)
    def validate_sms(self, **post):
        send_sms = post.get('send_sms')
        wiz_id = post.get('wiz_id')
        context_data = post.get('context_data')
        
        if not wiz_id or not context_data:
            return {
                'success': False,
                'error': 'Missing context data',
            }
        
        wizard = request.env['confirm.stock.sms'].sudo().browse(wiz_id)
        
        if not wizard.exists():
            return {'success': False, 'message': 'Wizard not found'}
        
        if context_data.get('from_api') is None:
            ctx = dict(request.env.context, **context_data, **{'from_api': True})
        else:
            ctx = dict(request.env.context, **context_data)
        
        if send_sms:
            result = wizard.with_context(ctx).send_sms()
        else:
            result = wizard.with_context(ctx).dont_send_sms()
        
        if result == True:
            return {
                'success': True,
                'message': 'Validate stock picking success',
                'type': 'done',
            }
        
        return {
            'success': True,
            'error': 'Validate stock picking failed',
            'type': result,
        }
        
    @http.route('/api/stock-picking/validate-backorder', type='json', auth='user', methods=['POST'], csrf=False)
    def validate_backorder(self, **post):
        create_backorder = post.get('create_backorder')
        context_data = post.get('context_data')
        
        if not context_data:
            return {
                'success': False,
                'error': 'Missing context data',
            }
        
        if context_data.get('from_api') is None:
            ctx = dict(request.env.context, **context_data, **{'from_api': True})
        else:
            ctx = dict(request.env.context, **context_data)
        
        wizard = request.env['stock.backorder.confirmation'].create({
            'pick_ids': [(6, 0, ctx.get('button_validate_picking_ids'))]
        })
        
        if create_backorder:
            result = wizard.with_context(ctx).process()
        else:
            result = wizard.with_context(ctx).process_cancel_backorder()
        
        if result == True:
            return {
                'success': True,
                'message': 'Validate stock picking success',
                'type': 'done',
            }
        
        return {
            'success': True,
            'error': 'Validate stock picking failed',
            'type': result,
        }
    
    @http.route('/api/stock-picking/validate-confirm-images', type='json', auth='user', methods=['POST'], csrf=False)
    def validate_confirm_images(self, **post):
        picking_id = post.get('picking_id')
        context_data = post.get('context_data')
        image_data_list = post.get('image_data_list')
        
        if not context_data or not image_data_list:
            return {
                'success': False,
                'error': 'Missing context data',
            }
        
        if context_data.get('from_api') is None:
            ctx = dict(request.env.context, **context_data, **{'from_api': True})
        else:
            ctx = dict(request.env.context, **context_data)
        
        picking = request.env['stock.picking'].browse(picking_id)
        
        if not picking or picking.state == 'done' or picking.state == 'cancel':
            return {
                'success': False,
                'errror': 'Picking not found or invalid',
            }
        
        picking.confirm_images.unlink()
        
        for image_data in image_data_list: 
            request.env['stock.confirm.image'].create({
                'picking_id': picking.id,
                'image': image_data
            })
        
        picking = request.env['stock.picking'].browse(picking_id)
            
        result  = picking.with_context(ctx).button_validate()
        
        if result == True:
            return {
                'success': True,
                'message': 'Validate stock picking success',
                'type': 'done',
            }
        
        return {
            'success': True,
            'error': 'Validate stock picking failed',
            'type': result,
        }


    @http.route('/api/stock-picking/confirm', type='json', auth='user', methods=['POST'], csrf=False)
    def confirm_picking(self, id):
        picking = request.env['stock.picking'].sudo().browse(id)
        
        if (picking.state != 'draft'):
            return {
                'success': False,
                'error': 'Picking only confirm in draft state'
            }
        
        if picking.action_confirm():
            new_picking = request.env['stock.picking'].sudo().browse(id)
            
            return {
                'success': True,
                'data': self._format_picking_response(new_picking)
            }
        
        return {
            'success': False,
            'error': 'Picking confirm failed'
        }
        
    @http.route('/api/stock-picking/assign', type='json', auth='user', methods=['POST'], csrf=False)
    def action_assign(self, id):
        picking = request.env['stock.picking'].sudo().browse(id)
        
        picking.action_assign()
        
        new_picking = request.env['stock.picking'].sudo().browse(id)
        
        if picking.state == 'assigned': 
            return {
                'success': True,
                'data': self._format_picking_response(new_picking)
            }
        
        return {
            'success': False,
            'error': 'Assign Picking Failed',
        }
        
    @http.route('/api/stock-picking/cancel', type='json', auth='user', methods=['POST'], csrf=False)
    def action_cancel(self, id):
        picking = request.env['stock.picking'].sudo().browse(id)
        
        picking.action_cancel()
        
        new_picking = request.env['stock.picking'].sudo().browse(id)
        
        if picking.state == 'cancel': 
            return {
                'success': True,
                'data': self._format_picking_response(new_picking)
            }
        
        return {
            'success': False,
            'error': 'Cancel Picking Failed',
        }

    def _format_picking_response(self, picking):
        barcode_image = self._generate_barcode_image(picking)
        
        return {
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
                'product_qty': move.product_qty,
                'quantity': move.quantity,
                'product_uom': {
                    'id': move.product_uom.id,
                    'name': move.product_uom.display_name,
                },
                'move_line_ids': [{
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
                } for line in move.move_line_ids],
            } for move in picking.move_ids_without_package],
            'confirm_images': [image.image for image in picking.confirm_images]
        }
    
    def _generate_barcode_image(self, picking):
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
            
        
        return barcode_image
    
    @http.route('/api/stock-picking/report-barcode', type='http', auth="user", methods=['POST'], csrf=False)
    def report_barcodes(self, **kwargs):
        picking_id = kwargs.get('picking_id')
        picking_id = int(picking_id)
        
        picking = request.env['stock.picking'].browse(picking_id)

        if not picking:
            return {
                'success': False,
                'error': 'Picking not found'
            }
            
        report = request.env.ref('inven_barcode_app.stock_picking_barcode_report')  # Adjust with your module and report ID
        pdf_content, content_type = request.env['ir.actions.report'].sudo()._render_qweb_pdf(
            report, 
            [picking.id],
            data = {
                'barcodes': picking.get_all_barcodes()
            }
        )
        
        # Set headers for file download
        headers = [
            ('Content-Type', 'application/pdf'),
            ('Content-Length', len(pdf_content)),
            ('Content-Disposition', content_disposition(picking.name + 'barcodes.pdf'))
        ]
        
        return Response(pdf_content, headers=headers)
