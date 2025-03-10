from odoo import models, fields, api


class WooBinding(models.AbstractModel):
    """Abstract model for all WooCommerce bindings"""
    _name = 'woo.binding'
    _description = 'WooCommerce Binding (abstract)'
    _inherit = 'external.binding'

    backend_id = fields.Many2one(
        comodel_name='woo.backend',
        string='WooCommerce Backend',
        required=True,
        ondelete='restrict',
    )

    woo_id = fields.Char(string='WooCommerce ID', index=True)

    _sql_constraints = [
        ('woo_uniq', 'unique(backend_id, woo_id)',
         'A binding already exists with the same WooCommerce ID.'),
    ]