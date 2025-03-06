from odoo import api, fields, models


class ShopeeCategory(models.Model):
    _name = 'shopee.category'
    _description = 'Shopee Category'
    _inherit = 'shopee.binding'

    name = fields.Char('Name', required=True)
    shopee_category_id = fields.Char('Shopee Category ID', required=True)
    parent_id = fields.Many2one('shopee.category', 'Parent Category')
    child_ids = fields.One2many('shopee.category', 'parent_id', 'Child Categories')
    product_count = fields.Integer('Product Count', compute='_compute_product_count')
    product_category_id = fields.Many2one('product.category', 'Odoo Product Category',
                                          help='Map this Shopee category to an Odoo product category')
    is_leaf = fields.Boolean('Is Leaf Category', default=False)
    active = fields.Boolean('Active', default=True)

    _sql_constraints = [
        ('shopee_category_uniq', 'unique(backend_id, shopee_category_id)',
         'A Shopee category with this ID already exists for this backend!')
    ]

    @api.depends('shopee_category_id')
    def _compute_product_count(self):
        """Compute the number of products in this category"""
        for category in self:
            category.product_count = self.env['shopee.product.template'].search_count([
                ('shopee_category_id', '=', category.shopee_category_id)
            ])

    def action_view_products(self):
        """View products in this category"""
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("odoo_shopee_connector.action_shopee_product_template")
        action['domain'] = [('shopee_category_id', '=', self.shopee_category_id)]
        action['context'] = {'default_shopee_category_id': self.shopee_category_id}
        return action

    def name_get(self):
        """Custom name display to show category hierarchy"""
        result = []
        for category in self:
            name_parts = []
            current = category

            while current:
                name_parts.insert(0, current.name)
                current = current.parent_id

            full_name = " / ".join(name_parts)
            result.append((category.id, full_name))
        return result

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        if args is None:
            args = []

        if name:
            categories = self.search([
                                         '|',
                                         ('name', operator, name),
                                         ('parent_id.name', operator, name)
                                     ] + args, limit=limit)

            return categories.name_get()

        # Nếu không có tên, thực hiện tìm kiếm bình thường
        return super().name_search(name, args, operator, limit)

    @api.model
    def import_batch(self, backend, force=False):
        """Import categories from Shopee"""
        with backend.work_on(self._name) as work:
            importer = work.component(usage='category.batch.importer')
            return importer.run(force=force)