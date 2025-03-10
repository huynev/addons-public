from odoo import models, fields, api, _
from odoo.addons.component.core import Component
import logging

_logger = logging.getLogger(__name__)


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    woo_bind_ids = fields.One2many(
        comodel_name='woo.product.template',
        inverse_name='odoo_id',
        string='WooCommerce Bindings',
    )

    @api.model
    def create(self, vals):
        """Create product and export it to WooCommerce if needed"""
        product = super().create(vals)
        if 'woo_bind_ids' not in vals and self.env.context.get('connector_no_export'):
            backend_ids = self.env['woo.backend'].search([('state', '=', 'active')])
            for backend in backend_ids:
                if self.env.context.get('auto_export_to_woo', True):
                    self.env['woo.product.template'].with_delay().export_record(product, backend)
        return product


class WooProductTemplate(models.Model):
    _name = 'woo.product.template'
    _description = 'WooCommerce Product'
    _inherit = 'woo.binding'
    _inherits = {'product.template': 'odoo_id'}
    _rec_name = 'name'

    odoo_id = fields.Many2one(
        comodel_name='product.template',
        string='Product Template',
        required=True,
        ondelete='cascade'
    )

    woo_updated_at = fields.Datetime(string='Last Update in WooCommerce')

    woo_status = fields.Selection([
        ('draft', 'Draft'),
        ('pending', 'Pending'),
        ('private', 'Private'),
        ('publish', 'Published')
    ], string='WooCommerce Status', default='publish')

    @api.model
    def import_batch(self, backend, filters=None):
        """Import a batch of products from WooCommerce"""
        with backend.work_on(self._name) as work:
            importer = work.component(usage='batch.importer')
            return importer.run(filters=filters)

    def export_stock(self):
        """Export the stock quantities to WooCommerce"""
        with self.backend_id.work_on(self._name) as work:
            exporter = work.component(usage='stock.exporter')
            return exporter.run(self)

    @api.model
    def export_record(self, product, backend):
        """Export a product to WooCommerce"""
        with backend.work_on(self._name) as work:
            binder = work.component(usage='binder')
            binding = binder.to_internal(product, wrap=True)
            if binding:
                exporter = work.component(usage='record.exporter')
                return exporter.run(binding)
        return None