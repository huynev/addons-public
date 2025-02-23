from odoo import models, fields, api
from odoo.exceptions import ValidationError
import logging
_logger = logging.getLogger(__name__)

class PrestashopShop(models.Model):
    _name = 'prestashop.shop'
    _inherit = 'prestashop.binding'
    _description = 'PrestaShop Shop'

    name = fields.Char('Name', required=True)
    shop_group_id = fields.Many2one(
        'prestashop.shop.group',
        'Shop Group',
        required=True,
        ondelete='cascade'
    )

    tax_mapping_ids = fields.One2many(
        'prestashop.tax.mapping',
        'shop_id',
        string='Tax Mappings'
    )

    backend_id = fields.Many2one(
        comodel_name='prestashop.backend',
        string='PrestaShop Backend',
        required=True,
        ondelete='restrict'
    )

    prestashop_id = fields.Integer('PrestaShop ID', readonly=True)
    shop_url = fields.Char('Shop URL', required=True)
    default_category_id = fields.Many2one(
        'product.category',
        'Default Product Category',
        required=True
    )
    active = fields.Boolean('Active', default=True)

    pricelist_id = fields.Many2one(
        'product.pricelist',
        string='Bảng Giá Mặc Định',
        required=True,
        help='Bảng giá được sử dụng để xuất giá sản phẩm sang PrestaShop'
    )

    _sql_constraints = [
        ('prestashop_uniq', 'unique(backend_id, prestashop_id)',
         'A PrestaShop shop with this ID already exists.'),
    ]

    @api.onchange('pricelist_id')
    def _onchange_pricelist_id(self):
        """
        Khi thay đổi bảng giá, reset giá của các sản phẩm liên kết
        """
        if self.pricelist_id:
            # Tìm tất cả các product template binding của shop này
            products = self.env['prestashop.product.template'].search([
                ('shop_id', '=', self.id)
            ])

            # Trigger recompute giá
            products._compute_prestashop_price()

    @api.constrains('backend_id', 'shop_group_id')
    def _check_backend_consistency(self):
        for record in self:
            if record.shop_group_id and record.backend_id != record.shop_group_id.backend_id:
                raise ValidationError(
                    'The shop must have the same backend as its shop group.'
                )

    def action_import_tax_rules_groups(self):
        """Import tax rules groups from PrestaShop"""
        self.ensure_one()
        prestashop = self.backend_id._get_prestashop_client()

        try:
            tax_groups = prestashop.get('tax_rule_groups', options={'display': 'full'})

            for tax_group in tax_groups.findall('.//tax_rule_group'):
                tax_group_id = tax_group.find('id').text
                name = tax_group.find('name').text

                # Tìm mapping tồn tại
                mapping = self.env['prestashop.tax.mapping'].search([
                    ('shop_id', '=', self.id),
                    ('prestashop_tax_group_id', '=', int(tax_group_id))
                ], limit=1)

                vals = {
                    'shop_id': self.id,
                    'prestashop_tax_group_id': int(tax_group_id),
                    'prestashop_tax_name': name,
                }

                if mapping:
                    mapping.write(vals)
                else:
                    self.env['prestashop.tax.mapping'].create(vals)

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Success',
                    'message': 'Tax rules groups imported successfully',
                    'type': 'success',
                }
            }

        except Exception as e:
            _logger.error(f"Error importing tax rules groups: {str(e)}")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error',
                    'message': str(e),
                    'type': 'danger',
                }
            }





class PrestashopShopGroup(models.Model):
    _name = 'prestashop.shop.group'
    _inherit = 'prestashop.binding'
    _description = 'PrestaShop Shop Group'

    name = fields.Char('Name', required=True)
    backend_id = fields.Many2one(
        comodel_name='prestashop.backend',
        string='PrestaShop Backend',
        required=True,
        ondelete='restrict'
    )
    shop_ids = fields.One2many(
        'prestashop.shop',
        'shop_group_id',
        'Shops'
    )
    prestashop_id = fields.Integer('PrestaShop ID', readonly=True)
    active = fields.Boolean('Active', default=True)

    @api.constrains('backend_id')
    def _check_shops_backend(self):
        for record in self:
            if record.shop_ids and any(shop.backend_id != record.backend_id for shop in record.shop_ids):
                raise ValidationError(
                    'All shops must have the same backend as their shop group.'
                )

    _sql_constraints = [
        ('prestashop_uniq', 'unique(backend_id, prestashop_id)',
         'A PrestaShop shop group with this ID already exists.'),
    ]

class PrestashopTaxMapping(models.Model):
    _name = 'prestashop.tax.mapping'
    _description = 'PrestaShop Tax Mapping'

    shop_id = fields.Many2one(
        'prestashop.shop',
        string='PrestaShop Shop',
        required=True
    )
    tax_id = fields.Many2one(
        'account.tax',
        string='Odoo Tax',
        domain=[('type_tax_use', '=', 'sale')]
    )
    prestashop_tax_group_id = fields.Integer(
        string='PrestaShop Tax Rules Group ID',
        required=True
    )
    prestashop_tax_name = fields.Char(
        string='PrestaShop Tax Name',
        help='Name of tax rules group on PrestaShop'
    )

    _sql_constraints = [
        ('unique_tax_mapping',
         'unique(shop_id, tax_id, prestashop_tax_group_id)',
         'A mapping for this tax and PrestaShop tax group already exists!')
    ]