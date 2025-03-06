from odoo import models, api
from datetime import datetime

class ProductProduct(models.Model):
    _inherit = 'product.product'

    def action_add_to_quotation(self):
        quotation_id = self.env.context.get('quotation_id')
        active_ids = self.env.context.get('active_ids', [])

        if quotation_id and active_ids:
            quotation = self.env['custom.quotation'].browse(quotation_id)
            QuotationLine = self.env['custom.quotation.line']
            quotation_lines = []

            # Lấy danh sách sản phẩm đã tồn tại
            existing_products = quotation.quotation_line_ids.mapped('product_id').ids

            for product in self.env['product.product'].browse(active_ids):
                # Bỏ qua nếu sản phẩm đã tồn tại
                if product.id in existing_products:
                    continue

                # Lấy giá từ pricelist
                try:
                    if quotation.pricelist_id:
                        price = quotation.pricelist_id._get_product_price(
                            product=product,
                            quantity=1.0,
                            partner=quotation.partner_id,
                            date=datetime.now().date(),
                            uom_id=product.uom_id
                        )
                        if price is None:
                            price = product.list_price
                    else:
                        price = product.list_price
                except Exception:
                    price = product.list_price

                # Lấy thông tin đóng gói
                packagings = self.env['product.packaging'].search([
                    ('product_id', '=', product.id)
                ])

                packaging_info = []
                if packagings:
                    for pack in packagings:
                        packaging_info.append(f"- {pack.name}: {pack.qty} {product.uom_id.name}")
                packaging_info = '\n'.join(packaging_info) if packaging_info else ''

                vals = {
                    'quotation_id': quotation.id,
                    'product_id': product.id,
                    'name': product.name,
                    'price_unit': price,
                    'product_uom_id': product.uom_id.id,
                    'packaging_info': packaging_info,
                    'tax_ids': [(6, 0, product.taxes_id.ids)]
                }
                quotation_lines.append(vals)

            # Tạo quotation lines mới
            if quotation_lines:
                QuotationLine.create(quotation_lines)

        # Thay đổi phần return để đóng popup và refresh form view
        return {
            'type': 'ir.actions.act_window_close'
        }