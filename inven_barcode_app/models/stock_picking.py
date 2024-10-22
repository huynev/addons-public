from odoo import models, fields, api
import base64
from io import BytesIO
import barcode

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    barcode_image = fields.Binary(string="Barcode Image", readonly=True)
    barcode = fields.Char(string="Barcode", readonly=True)

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

    def process_validate_with_backorder(self):
        # Create an instance of the backorder confirmation wizard
        wizard = self.env['stock.backorder.confirmation'].create({
            'pick_ids': [(6, 0, self.ids)]
        })

        # Call the process method of the wizard
        wizard.process()

        # Continue with any other logic
        return True

    def process_validate_without_backorder(self):
        # Create an instance of the backorder confirmation wizard
        wizard = self.env['stock.backorder.confirmation'].create({
            'pick_ids': [(6, 0, self.ids)]
        })

        # Call the process method of the wizard
        wizard.process_cancel_backorder()

        # Continue with any other logic
        return True