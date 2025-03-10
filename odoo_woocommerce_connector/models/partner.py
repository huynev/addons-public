from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    woo_bind_ids = fields.One2many(
        comodel_name='woo.res.partner',
        inverse_name='odoo_id',
        string='WooCommerce Bindings',
    )


class WooResPartner(models.Model):
    _name = 'woo.res.partner'
    _description = 'WooCommerce Partner'
    _inherit = 'woo.binding'
    _inherits = {'res.partner': 'odoo_id'}

    odoo_id = fields.Many2one(
        comodel_name='res.partner',
        string='Partner',
        required=True,
        ondelete='cascade'
    )

    woo_email = fields.Char(string='WooCommerce Email')
    woo_username = fields.Char(string='WooCommerce Username')