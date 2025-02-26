from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging
_logger = logging.getLogger(__name__)


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    main_reference = fields.Char('Main Reference', help='Reference code for product template')

    prestashop_bind_ids = fields.One2many(
        'prestashop.product.template',
        'odoo_id',
        string='PrestaShop Bindings'
    )

    prestashop_bind_count = fields.Integer(
        string='Number of PrestaShop Bindings',
        compute='_compute_prestashop_bind_count'
    )

    @api.model
    def create(self, vals):
        product = super().create(vals)

        # Tìm tất cả các shop PrestaShop
        prestashop_shops = self.env['prestashop.shop'].search([
            ('active', '=', True)
        ])

        for shop in prestashop_shops:
            try:
                # Tạo binding
                prestashop_products = self.env['prestashop.product.template'].search([
                    ('odoo_id', 'in', product.id),
                    ('shop_id', '=', shop.id)
                ])

                # Tạo job xuất sản phẩm
                # Sync từng sản phẩm cho shop
                for prestashop_product in prestashop_products:
                    try:
                        prestashop_product.with_delay(channel='root.prestashop').export_record()
                    except Exception as e:
                        _logger.error(
                            f"Error export product {prestashop_product.name} to shop {shop.name}: {str(e)}"
                        )
            except Exception as e:
                _logger.error(f"Lỗi tạo binding và xuất sản phẩm {product.name}: {str(e)}")

        return product

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
            'res_model': 'prestashop.product.template',
            'domain': [('odoo_id', '=', self.id)],
            'context': {'default_odoo_id': self.id},
        }


class PrestashopProductTemplate(models.Model):
    _name = 'prestashop.product.template'
    _inherit = 'prestashop.binding'
    _inherits = {'product.template': 'odoo_id'}
    _description = 'PrestaShop Product Template Binding'

    main_reference = fields.Char('Main Reference', readonly=True, help='Reference code for product template')

    odoo_id = fields.Many2one(
        'product.template',
        string='Product Template',
        required=True,
        readonly=True,
        ondelete='cascade',
        domain=[('active', 'in', [True, False])]
    )

    # Field để liên kết với các biến thể
    variant_bind_ids = fields.One2many(
        'prestashop.product.product',
        'prestashop_product_id',
        string='Variant Bindings'
    )

    # PrestaShop specific fields
    prestashop_id = fields.Integer('PrestaShop ID', readonly=True)

    price = fields.Float(
        string='PrestaShop Price',
        compute='_compute_prestashop_price',
        store=True,
        readonly=True,
        help='Giá sản phẩm được tính tự động dựa trên cấu hình bảng giá của shop'
    )
    date_add = fields.Datetime('Added on PrestaShop')
    date_upd = fields.Datetime('Updated on PrestaShop')

    qty_available = fields.Float(
        related='odoo_id.qty_available',
        string='Quantity On Hand',
        readonly=True,
        store=True
    )
    tax_id = fields.Many2one(
        'prestashop.tax.mapping',
        string='PrestaShop Tax Mapping',
        domain="[('shop_id', '=', shop_id)]",
        help='Thuế được áp dụng cho sản phẩm trên PrestaShop'
    )
    note = fields.Text('Notes', help='Internal notes about the product')

    @api.model
    def create(self, vals):
        if 'odoo_id' in vals:
            product = self.env['product.template'].browse(vals['odoo_id'])
            if not product.exists():
                raise ValidationError(_('Cannot create binding: Product Template does not exist.'))
        if vals.get('default_code'):
            vals['main_reference'] = vals['default_code']
        return super().create(vals)

    def write(self, vals):
        # Cập nhật main_reference nếu default_code thay đổi và không có biến thể
        if 'default_code' in vals and not self.attribute_line_ids:
            vals['main_reference'] = vals['default_code']
        return super().write(vals)

    @api.depends('shop_id', 'shop_id.pricelist_id', 'odoo_id')
    def _compute_prestashop_price(self):
        """
        Tính giá sản phẩm dựa trên bảng giá của shop
        """
        for record in self:
            record.price = record.list_price
            if record.shop_id and record.shop_id.pricelist_id:
                try:
                    product_variant = record.odoo_id.product_variant_ids[0]

                    price = record.shop_id.pricelist_id._get_product_price(
                        product=product_variant,
                        quantity=1.0,
                        partner=False,
                        date=fields.Date.today(),
                        uom_id=product_variant.uom_id
                    )

                    record.price = price
                except Exception as e:
                    _logger.error(f"Lỗi tính giá cho sản phẩm {record.name}: {str(e)}")
                    record.price = record.list_price

    def _sync_stock_to_prestashop(self):
        """Sync stock to PrestaShop"""
        self.ensure_one()
        if self.prestashop_id:
            with self.shop_id.backend_id.work_on(self._name) as work:
                exporter = work.component(usage='record.exporter')
                # exporter._update_stock(self)
                exporter.run(self)

    @api.model
    def import_record(self, backend, prestashop_id):
        """ Import a prestashop record """
        with backend.work_on(self._name) as work:
            importer = work.component(usage='record.importer')
            return importer.run(prestashop_id)

    @api.model
    def export_record(self):
        """ Export a prestashop record """
        self.ensure_one()
        with self.shop_id.backend_id.work_on(self._name) as work:
            exporter = work.component(usage='record.exporter')
            return exporter.run(self)

    @api.model
    def export_batch(self, domain=None):
        """ Export a batch of records

        Args:
            backend: prestashop.backend record
            domain: optional domain for searching records to export
        """
        domain = domain or []
        records = self.search(domain)
        for record in records:
            try:
                record.export_record()  # Call directly on the record
                # record.with_delay(channel='root.prestashop').export_record()  # Queue the job on the record itself
            except Exception as e:
                _logger.error(f"Error queuing export for record {record.id}: {str(e)}")


class StockMove(models.Model):
    _inherit = 'stock.move'

    def _action_done(self, **kwargs):
        """Override to trigger stock sync after move is done"""
        res = super()._action_done(**kwargs)

        # Lấy tất cả product templates liên quan
        product_tmpls = self.mapped('product_id.product_tmpl_id')

        if product_tmpls:
            # Lấy tất cả shop prestashop đang active
            prestashop_shops = self.env['prestashop.shop'].search([
                ('active', '=', True)
            ])

            for shop in prestashop_shops:
                # Tìm prestashop bindings cho các products trong shop này
                prestashop_products = self.env['prestashop.product.template'].search([
                    ('odoo_id', 'in', product_tmpls.ids),
                    ('shop_id', '=', shop.id)
                ])

                # Sync từng sản phẩm cho shop
                for prestashop_product in prestashop_products:
                    try:
                        prestashop_product.with_delay(channel='root.prestashop')._sync_stock_to_prestashop()
                        _logger.info(
                            f"Queued stock sync for product {prestashop_product.name} to shop {shop.name}"
                        )
                    except Exception as e:
                        _logger.error(
                            f"Error syncing stock for product {prestashop_product.name} to shop {shop.name}: {str(e)}"
                        )

        return res