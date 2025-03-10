from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)


class ProductCategory(models.Model):
    _inherit = 'product.category'

    woo_bind_ids = fields.One2many(
        comodel_name='woo.product.category',
        inverse_name='odoo_id',
        string='WooCommerce Bindings',
    )


class WooProductCategory(models.Model):
    _name = 'woo.product.category'
    _description = 'WooCommerce Product Category'
    _inherit = 'woo.binding'
    _inherits = {'product.category': 'odoo_id'}

    odoo_id = fields.Many2one(
        comodel_name='product.category',
        string='Product Category',
        required=True,
        ondelete='cascade'
    )

    woo_parent_id = fields.Many2one(
        comodel_name='woo.product.category',
        string='WooCommerce Parent Category',
        ondelete='set null',
    )