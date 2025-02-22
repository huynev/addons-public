from odoo import models, fields, api
import base64
from io import BytesIO
import barcode
from odoo.addons.inven_barcode_app.utils import barcode_util
from odoo.exceptions import UserError

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    barcode_image = fields.Binary(string="Barcode Image", readonly=True)
    barcode = fields.Char(string="Barcode", readonly=True)
    confirm_images = fields.One2many('stock.confirm.image', 'picking_id')
    
    def _pre_action_done_hook(self):
        res = super()._pre_action_done_hook()
        if res is True and self.env.context.get('from_api'):
            company_config = self.company_id
            if company_config.stock_confirm_image and len(self.confirm_images) < company_config.stock_confirm_image_count:
                return {
                    'name': 'Stock Done Image',
                    'type': 'ir.actions.act_window',
                    'view_mode': 'form',
                    'res_model': 'stock.confirm.image',
                    'views': [(1, 'form')],
                    'view_id': 1,
                    'target': 1,
                    'res_id': 1,
                    'context': {
                        **self.env.context,
                        'confirm_images_count': company_config.stock_confirm_image_count,
                    },
                }
                
        return res

    @api.model
    def create(self, vals):
        picking = super(StockPicking, self).create(vals)
        if not picking.barcode:
            # Generate the barcode string (code128 format for example)
            barcode_value = self.env['ir.sequence'].next_by_code('stock.picking.barcode')
            picking.barcode = barcode_value

            # Generate the barcode image and save it as binary
            picking._generate_barcode_image()
        return picking

    def _create_backorder(self):
        # Call the super method to create the backorder
        backorder = super(StockPicking, self)._create_backorder()

        # Generate the barcode string (code128 format for example)
        barcode_value = self.env['ir.sequence'].next_by_code('stock.picking.barcode')
        backorder.barcode = barcode_value

        # Generate the barcode image and save it as binary
        backorder._generate_barcode_image()

        return backorder

    def _generate_barcode_image(self):
        """Generates barcode image using python-barcode and saves it as binary."""
        if self.barcode:
            # Create the barcode
            barcode_class = barcode.get_barcode_class('code128')
            code128 = barcode_class(self.barcode)

            # Generate barcode as PNG
            buffer = BytesIO()
            code128.write(buffer, options={"write_text": False})  # Don't write text under the barcode

            # Save the image to the binary field as base64
            self.barcode_image = base64.b64encode(buffer.getvalue())
            buffer.close()
    
    @api.model
    def get_all_barcodes(self):
        barcodes = []
        
        if self.barcode:
            barcodes = barcodes + [{
                'name': self.barcode,
                'image': 'data:image/svg+xml;base64,' + barcode_util.generate_barcode_image(self.barcode).decode('utf-8')
            }]
            
        move_lines = self.move_line_ids
        
        for move_line in move_lines:
            if move_line.result_package_id:
                barcodes = barcodes + [{
                    'name': move_line.result_package_id.name,
                    'image': 'data:image/svg+xml;base64,' + barcode_util.generate_barcode_image(move_line.result_package_id.name).decode('utf-8')
                }]
        
        return barcodes


    def action_put_in_pack_with_specific_name(self, package_name):
        self.ensure_one()
        if self.state not in ('done', 'cancel'):
            move_line_ids = self._package_move_lines()
            if move_line_ids:
                res = self._pre_put_in_pack_hook(move_line_ids)
                if not res:
                    package = self._put_in_pack_with_specific_name(move_line_ids, package_name)
                    return self._post_put_in_pack_hook(package)
                return res
            raise UserError(_("There is nothing eligible to put in a pack. Either there are no quantities to put in a pack or all products are already in a pack."))
        
    
    def _put_in_pack_with_specific_name(self, move_line_ids, package_name):
        package = self.env['stock.quant.package'].create({
            'name': package_name
        })
        package_type = move_line_ids.move_id.product_packaging_id.package_type_id
        if len(package_type) == 1:
            package.package_type_id = package_type
        if len(move_line_ids) == 1:
            default_dest_location = move_line_ids._get_default_dest_location()
            move_line_ids.location_dest_id = default_dest_location._get_putaway_strategy(
                product=move_line_ids.product_id,
                quantity=move_line_ids.quantity,
                package=package)
        move_line_ids.write({
            'result_package_id': package.id,
        })
        if len(self) == 1:
            self.env['stock.package_level'].create({
                'package_id': package.id,
                'picking_id': self.id,
                'location_id': False,
                'location_dest_id': move_line_ids.location_dest_id.id,
                'move_line_ids': [(6, 0, move_line_ids.ids)],
                'company_id': self.company_id.id,
            })
        return package