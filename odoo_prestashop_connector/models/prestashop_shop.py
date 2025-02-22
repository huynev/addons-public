from odoo import models, fields, api
from odoo.exceptions import ValidationError

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

    _sql_constraints = [
        ('prestashop_uniq', 'unique(backend_id, prestashop_id)',
         'A PrestaShop shop with this ID already exists.'),
    ]


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