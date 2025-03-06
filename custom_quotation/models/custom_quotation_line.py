from odoo import models, fields, api

class CustomQuotationLine(models.Model):
    _name = 'custom.quotation.line'
    _description = 'Custom Quotation Line'

    quotation_id = fields.Many2one('custom.quotation', string='Quotation Reference', ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Product', required=True)
    name = fields.Text(string='Description')
    product_uom_id = fields.Many2one('uom.uom', string='Unit of Measure', related='product_id.uom_id')
    price_unit = fields.Float(string='Unit Price')
    packaging_info = fields.Text(string='Packaging Info')
    tax_ids = fields.Many2many('account.tax', string='Taxes')
    price_with_tax = fields.Float(string='Giá bao gồm thuế', store=True, compute='_compute_price_with_tax')

    @api.depends('price_unit', 'tax_ids')
    def _compute_price_with_tax(self):
        for line in self:
            price = line.price_unit
            taxes_amount = 0

            if line.tax_ids:
                # Tính thuế thủ công không sử dụng currency_id
                for tax in line.tax_ids:
                    if tax.amount_type == 'percent':
                        taxes_amount += price * tax.amount / 100

            line.price_with_tax = price + taxes_amount

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            try:
                if self.quotation_id.pricelist_id:
                    price = self.quotation_id.pricelist_id._get_product_price(
                        product=self.product_id,
                        quantity=1.0,
                        partner=self.quotation_id.partner_id,
                        date=fields.Date.today(),
                        uom_id=self.product_id.uom_id
                    )
                    if price is None:
                        price = self.product_id.list_price
                else:
                    price = self.product_id.list_price
            except Exception:
                price = self.product_id.list_price

            self.name = self.product_id.name
            self.price_unit = price

            taxes = self.product_id.taxes_id
            # Lấy tất cả các quy cách đóng gói của sản phẩm
            packagings = self.env['product.packaging'].search([
                ('product_id', '=', self.product_id.id)
            ])

            # Tạo chuỗi thông tin đóng gói
            packaging_info = []
            if packagings:
                for pack in packagings:
                    packaging_info.append(f"- {pack.name}: {pack.qty} {self.product_id.uom_id.name}")
            packaging_info = '\n'.join(packaging_info) if packaging_info else ''

            if packaging_info:
                self.packaging_info = packaging_info
            if taxes:
                self.tax_ids = taxes.ids

    # def action_add_from_catalog(self):
    #     quotation = self.env['custom.quotation'].browse(self.env.context.get('quotation_id'))
    #     return quotation.action_add_from_catalog()
