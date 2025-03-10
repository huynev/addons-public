from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    woo_bind_ids = fields.One2many(
        comodel_name='woo.sale.order',
        inverse_name='odoo_id',
        string='WooCommerce Bindings',
    )


class WooSaleOrder(models.Model):
    _name = 'woo.sale.order'
    _description = 'WooCommerce Sale Order'
    _inherit = 'woo.binding'
    _inherits = {'sale.order': 'odoo_id'}

    odoo_id = fields.Many2one(
        comodel_name='sale.order',
        string='Sale Order',
        required=True,
        ondelete='cascade'
    )

    woo_order_key = fields.Char(string='WooCommerce Order Key')
    woo_status = fields.Selection([
        ('pending', 'Pending Payment'),
        ('processing', 'Processing'),
        ('on-hold', 'On Hold'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded'),
        ('failed', 'Failed')
    ], string='WooCommerce Status')

    woo_customer_id = fields.Integer(string='WooCommerce Customer ID')

    @api.model
    def import_batch(self, backend, filters=None):
        """Import a batch of orders from WooCommerce"""
        with backend.work_on(self._name) as work:
            importer = work.component(usage='batch.importer')
            return importer.run(filters=filters)


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    woo_bind_ids = fields.One2many(
        comodel_name='woo.sale.order.line',
        inverse_name='odoo_id',
        string='WooCommerce Bindings',
    )


class WooSaleOrderLine(models.Model):
    _name = 'woo.sale.order.line'
    _description = 'WooCommerce Sale Order Line'
    _inherit = 'woo.binding'
    _inherits = {'sale.order.line': 'odoo_id'}

    odoo_id = fields.Many2one(
        comodel_name='sale.order.line',
        string='Sale Order Line',
        required=True,
        ondelete='cascade'
    )

    woo_order_id = fields.Many2one(
        comodel_name='woo.sale.order',
        string='WooCommerce Sale Order',
        required=True,
        ondelete='cascade',
    )