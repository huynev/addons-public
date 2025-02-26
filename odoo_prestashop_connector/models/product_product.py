from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class ProductProduct(models.Model):
    _inherit = 'product.product'

    prestashop_bind_ids = fields.One2many(
        'prestashop.product.product',
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
            'res_model': 'prestashop.product.product',
            'domain': [('odoo_id', '=', self.id)],
            'context': {'default_odoo_id': self.id},
        }


class PrestashopProductProduct(models.Model):
    _name = 'prestashop.product.product'
    _inherit = 'prestashop.binding'
    _inherits = {'product.product': 'odoo_id'}
    _description = 'PrestaShop Product Variant Binding'

    odoo_id = fields.Many2one(
        'product.product',
        string='Product Variant',
        required=True,
        readonly=True,
        ondelete='cascade',
        domain=[('active', 'in', [True, False])]
    )

    # PrestaShop specific fields
    prestashop_id = fields.Integer('PrestaShop Combination ID', readonly=True)
    prestashop_product_id = fields.Many2one(
        'prestashop.product.template',
        string='PrestaShop Product',
        required=True,
        ondelete='cascade'
    )

    reference = fields.Char('PrestaShop Reference', readonly=True)
    date_add = fields.Datetime('Added on PrestaShop')
    date_upd = fields.Datetime('Updated on PrestaShop')

    qty_available = fields.Float(
        related='odoo_id.qty_available',
        string='Quantity On Hand',
        readonly=True,
        store=True
    )

    note = fields.Text('Notes', help='Internal notes about the product variant')

    _sql_constraints = [
        ('prestashop_uniq', 'unique(shop_id, prestashop_id, prestashop_id!=0)',
         'A binding already exists with the same PrestaShop ID.'),
    ]

    @api.model
    def create(self, vals):
        if 'odoo_id' in vals and not vals.get('prestashop_product_id'):
            # Auto-link to parent product template binding if not specified
            product = self.env['product.product'].browse(vals['odoo_id'])
            if product.exists():
                template_binding = self.env['prestashop.product.template'].search([
                    ('odoo_id', '=', product.product_tmpl_id.id),
                    ('shop_id', '=', vals.get('shop_id'))
                ], limit=1)
                if template_binding:
                    vals['prestashop_product_id'] = template_binding.id

        if not vals.get('reference') and 'odoo_id' in vals:
            product = self.env['product.product'].browse(vals['odoo_id'])
            if product.exists() and product.default_code:
                vals['reference'] = product.default_code

        return super().create(vals)

    # def export_record(self):
    #     """ Export a prestashop combination """
    #     self.ensure_one()
    #     # Gọi export từ sản phẩm cha
    #     if self.prestashop_product_id:
    #         self.prestashop_product_id.with_context(variant_id=self.id).export_record()
    #     else:
    #         _logger.error(f"Cannot export variant {self.display_name}: No parent product binding")