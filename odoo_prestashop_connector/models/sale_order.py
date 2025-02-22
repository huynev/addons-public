from odoo import models, fields, api
from datetime import datetime

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    prestashop_bind_ids = fields.One2many(
        'prestashop.sale.order',
        'odoo_id',
        string='PrestaShop Bindings'
    )

    prestashop_bind_count = fields.Integer(
        string='Number of PrestaShop Bindings',
        compute='_compute_prestashop_bind_count'
    )

    @api.depends('prestashop_bind_ids')
    def _compute_prestashop_bind_count(self):
        for record in self:
            record.prestashop_bind_count = len(record.prestashop_bind_ids)

    def action_view_prestashop_bindings(self):
        self.ensure_one()
        return {
            'name': 'PrestaShop Bindings',
            'type': 'ir.actions.act_window',
            'view_mode': 'tree,form',
            'res_model': 'prestashop.sale.order',
            'domain': [('odoo_id', '=', self.id)],
            'context': {'default_odoo_id': self.id},
        }

class PrestashopSaleOrder(models.Model):
    _name = 'prestashop.sale.order'
    _inherit = 'prestashop.binding'
    _inherits = {'sale.order': 'odoo_id'}
    _description = 'PrestaShop Sale Order Binding'

    odoo_id = fields.Many2one(
        'sale.order',
        string='Sale Order',
        required=True,
        ondelete='cascade'
    )
    prestashop_id = fields.Integer('PrestaShop ID', readonly=True)
    shop_id = fields.Many2one(
        'prestashop.shop',
        'PrestaShop Shop',
        required=True,
        readonly=True
    )
    prestashop_order_line_ids = fields.One2many(
        'prestashop.sale.order.line',
        'prestashop_order_id',
        string='PrestaShop Order Lines'
    )
    prestashop_payment = fields.Char('Payment Method')
    prestashop_payment_module = fields.Char('Payment Module')
    total_amount = fields.Float('Total Amount', digits='Product Price')
    total_amount_tax = fields.Float('Total Amount Tax', digits='Product Price')
    total_shipping_tax_included = fields.Float('Shipping Amount with Tax')
    total_shipping_tax_excluded = fields.Float('Shipping Amount without Tax')
    conversion_rate = fields.Float('Conversion Rate', default=1.0)
    date_add = fields.Datetime('Created At')
    date_upd = fields.Datetime('Updated At')

class PrestashopSaleOrderLine(models.Model):
    _name = 'prestashop.sale.order.line'
    _inherit = 'prestashop.binding'
    _inherits = {'sale.order.line': 'odoo_id'}
    _description = 'PrestaShop Sale Order Line Binding'

    odoo_id = fields.Many2one(
        'sale.order.line',
        string='Sale Order Line',
        required=True,
        ondelete='cascade'
    )
    prestashop_id = fields.Integer('PrestaShop ID', readonly=True)
    prestashop_order_id = fields.Many2one(
        'prestashop.sale.order',
        string='PrestaShop Sale Order',
        required=True,
        ondelete='cascade'
    )
    prestashop_product_id = fields.Many2one(
        'prestashop.product.template',
        string='PrestaShop Product'
    )