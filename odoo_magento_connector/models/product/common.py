from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class MagentoProductTemplate(models.Model):
    _name = 'magento.product.template'
    _description = 'Magento Product Template'
    _inherit = 'magento.binding'
    _inherits = {'product.template': 'odoo_id'}

    odoo_id = fields.Many2one(
        'product.template',
        string='Product Template',
        required=True,
        ondelete='cascade'
    )
    backend_id = fields.Many2one(
        'magento.backend',
        string='Magento Backend',
        required=True,
        ondelete='cascade'
    )
    external_id = fields.Char(string='Magento ID')
    magento_website_ids = fields.Many2many(
        'magento.website',
        string='Magento Websites',
        help='Websites where this product is available'
    )
    magento_sku = fields.Char(string='Magento SKU')
    sync_date = fields.Datetime(string='Last Synchronization')
    sync_status = fields.Selection([
        ('draft', 'Not Exported'),
        ('exporting', 'Exporting'),
        ('synced', 'Synchronized'),
        ('error', 'Error'),
    ], string='Sync Status', default='draft')
    url_key = fields.Char(string='URL Key')
    magento_attribute_set_id = fields.Many2one(
        'magento.attribute.set',
        string='Attribute Set'
    )

    _sql_constraints = [
        ('magento_sku_uniq', 'unique(backend_id, magento_sku)',
         'A product binding with the same Magento SKU already exists.'),
    ]

    @api.model
    def create(self, vals):
        """Override to handle default values and generate SKU if needed"""
        if 'magento_sku' not in vals and 'odoo_id' in vals:
            product = self.env['product.template'].browse(vals['odoo_id'])
            vals['magento_sku'] = product.default_code or f'odoo-{product.id}'

        return super().create(vals)

    def export_record(self):
        """Export product to Magento"""
        for binding in self:
            binding.with_delay(
                channel='root.magento.product'
            ).export_product()
        return True

    def export_product(self):
        """Export product to Magento - to be called with with_delay()"""
        self.ensure_one()
        exporter = self.env.context.get('connector_exporter', False)
        if not exporter:
            exporter = self.env['magento.product.exporter'].new({
                'backend_record': self.backend_id,
                'model': self._name,
            })
        return exporter.run(self)


class MagentoProductProduct(models.Model):
    _name = 'magento.product.product'
    _description = 'Magento Product Variant'
    _inherit = 'magento.binding'
    _inherits = {'product.product': 'odoo_id'}

    odoo_id = fields.Many2one(
        'product.product',
        string='Product',
        required=True,
        ondelete='cascade'
    )
    backend_id = fields.Many2one(
        'magento.backend',
        string='Magento Backend',
        required=True,
        ondelete='cascade'
    )
    external_id = fields.Char(string='Magento ID')
    magento_sku = fields.Char(string='Magento SKU')
    sync_date = fields.Datetime(string='Last Synchronization')
    sync_status = fields.Selection([
        ('draft', 'Not Exported'),
        ('exporting', 'Exporting'),
        ('synced', 'Synchronized'),
        ('error', 'Error'),
    ], string='Sync Status', default='draft')
    magento_website_ids = fields.Many2many(
        'magento.website',
        string='Magento Websites',
        help='Websites where this product is available'
    )

    _sql_constraints = [
        ('magento_sku_uniq', 'unique(backend_id, magento_sku)',
         'A product binding with the same Magento SKU already exists.'),
    ]

    @api.model
    def create(self, vals):
        """Override to handle default values and generate SKU if needed"""
        if 'magento_sku' not in vals and 'odoo_id' in vals:
            product = self.env['product.product'].browse(vals['odoo_id'])
            vals['magento_sku'] = product.default_code or f'odoo-{product.id}'

        return super().create(vals)

    def export_stock(self):
        """Export stock information to Magento"""
        for binding in self:
            binding.with_delay(
                channel='root.magento.stock'
            ).export_stock_item()
        return True

    def export_stock_item(self):
        """Export stock information to Magento - to be called with with_delay()"""
        self.ensure_one()
        exporter = self.env['magento.product.stock.exporter'].new({
            'backend_record': self.backend_id,
            'model': self._name,
        })
        return exporter.run(self)


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    magento_bind_ids = fields.One2many(
        'magento.product.template',
        'odoo_id',
        string='Magento Bindings'
    )

    def create_magento_bindings(self):
        """Create bindings for selected products on all active backends"""
        backends = self.env['magento.backend'].search([('active', '=', True)])
        if not backends:
            raise UserError(_("No active Magento backend found."))

        for backend in backends:
            for template in self:
                binding = self.env['magento.product.template'].search([
                    ('backend_id', '=', backend.id),
                    ('odoo_id', '=', template.id)
                ], limit=1)

                if not binding:
                    self.env['magento.product.template'].create({
                        'backend_id': backend.id,
                        'odoo_id': template.id,
                        'magento_sku': template.default_code or f'odoo-{template.id}',
                    })
                    _logger.info(f"Created Magento binding for product {template.name} on backend {backend.name}")

        # Create bindings for all variants
        for template in self:
            for variant in template.product_variant_ids:
                variant.create_magento_bindings()

        return True


class ProductProduct(models.Model):
    _inherit = 'product.product'

    magento_bind_ids = fields.One2many(
        'magento.product.product',
        'odoo_id',
        string='Magento Bindings'
    )

    def create_magento_bindings(self):
        """Create bindings for selected variants on all active backends"""
        backends = self.env['magento.backend'].search([('active', '=', True)])
        if not backends:
            raise UserError(_("No active Magento backend found."))

        for backend in backends:
            for variant in self:
                binding = self.env['magento.product.product'].search([
                    ('backend_id', '=', backend.id),
                    ('odoo_id', '=', variant.id)
                ], limit=1)

                if not binding:
                    # Check if we already have a template binding
                    template_binding = self.env['magento.product.template'].search([
                        ('backend_id', '=', backend.id),
                        ('odoo_id', '=', variant.product_tmpl_id.id)
                    ], limit=1)

                    # Create template binding if it doesn't exist
                    if not template_binding:
                        template_binding = self.env['magento.product.template'].create({
                            'backend_id': backend.id,
                            'odoo_id': variant.product_tmpl_id.id,
                            'magento_sku': variant.product_tmpl_id.default_code or f'odoo-{variant.product_tmpl_id.id}',
                        })

                    # Create variant binding
                    self.env['magento.product.product'].create({
                        'backend_id': backend.id,
                        'odoo_id': variant.id,
                        'magento_sku': variant.default_code or f'odoo-{variant.id}',
                    })
                    _logger.info(
                        f"Created Magento binding for variant {variant.display_name} on backend {backend.name}")

        return True