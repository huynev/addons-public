from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class ProductCategory(models.Model):
    _inherit = 'product.category'

    prestashop_bind_ids = fields.One2many(
        'prestashop.product.category',
        'odoo_id',
        string='PrestaShop Bindings'
    )

class PrestashopProductCategory(models.Model):
    _name = 'prestashop.product.category'
    _inherit = 'prestashop.binding'
    _inherits = {'product.category': 'odoo_id'}
    _description = 'PrestaShop Category Binding'

    odoo_id = fields.Many2one(
        'product.category',
        string='Product Category',
        required=True,
        ondelete='cascade'
    )
    prestashop_id = fields.Integer('PrestaShop ID', readonly=True)
    shop_id = fields.Many2one(
        'prestashop.shop',
        'PrestaShop Shop',
        required=True,
        ondelete='cascade'
    )
    date_add = fields.Datetime('Added on PrestaShop')
    date_upd = fields.Datetime('Updated on PrestaShop')

    @api.model
    def export_record(self):
        """ Export a prestashop record """
        self.ensure_one()
        with self.shop_id.backend_id.work_on(self._name) as work:
            exporter = work.component(usage='record.exporter')
            return exporter.run(self)