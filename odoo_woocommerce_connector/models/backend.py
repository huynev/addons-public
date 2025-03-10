from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
from woocommerce import API

_logger = logging.getLogger(__name__)


class WooCommerceBackend(models.Model):
    _name = 'woo.backend'
    _description = 'WooCommerce Backend Configuration'
    _inherit = 'connector.backend'

    @api.model
    def _select_state(self):
        """Available states for this backend"""
        return [('draft', 'Not Started'),
                ('active', 'Active'),
                ('inactive', 'Inactive')]

    name = fields.Char(string='Name', required=True)
    woo_url = fields.Char(string='URL', required=True, help='WooCommerce URL (e.g. https://example.com)')
    woo_consumer_key = fields.Char(string='Consumer Key', required=True)
    woo_consumer_secret = fields.Char(string='Consumer Secret', required=True)
    woo_version = fields.Selection([
        ('v3', 'Version 3'),
        ('wp-api-v1', 'WP API v1'),
        ('wc/v2', 'WP API v2')
    ], string='API Version', default='wp-api-v2', required=True)
    is_ssl_verify = fields.Boolean(string='Verify SSL', default=True)
    state = fields.Selection(selection='_select_state', default='draft')

    # Synchronization options
    product_import_batch_size = fields.Integer(string='Products Batch Size', default=100)
    order_import_batch_size = fields.Integer(string='Orders Batch Size', default=100)

    # Date filters for import
    import_products_from_date = fields.Datetime(string='Import Products From')
    import_orders_from_date = fields.Datetime(string='Import Orders From')

    # Import statuses
    last_product_import_date = fields.Datetime(string='Last Product Import')
    last_order_import_date = fields.Datetime(string='Last Order Import')
    last_stock_export_date = fields.Datetime(string='Last Stock Export')

    # Import rules
    product_import_rule = fields.Selection([
        ('all', 'All Products'),
        ('published', 'Only Published Products')
    ], string='Product Import Rule', default='published')
    order_import_rule = fields.Selection([
        ('all', 'All Orders'),
        ('processing', 'Only Processing Orders')
    ], string='Order Import Rule', default='processing')

    # Default mapping values
    default_category_id = fields.Many2one('product.category', string='Default Product Category')
    default_customer_user_id = fields.Many2one('res.users', string='Default Salesperson',
                                               default=lambda self: self.env.user)

    default_payment_term_id = fields.Many2one(
        'account.payment.term',
        string='Default Payment Term',
        default=lambda self: self.env.ref('account.account_payment_term_immediate', False)
    )

    def test_connection(self):
        """Test the connection to WooCommerce"""
        self.ensure_one()
        try:
            wcapi = self._get_woo_api()
            result = wcapi.get("products", params={"per_page": 1})
            if result.status_code == 200:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Connection Test'),
                        'message': _('Connection successful!'),
                        'type': 'success',
                        'sticky': False,
                    }
                }
            else:
                raise UserError(_('Connection failed! Status code: %s, Error: %s') % (result.status_code, result.text))
        except Exception as e:
            raise UserError(_('Connection failed! Error: %s') % str(e))

    def _get_woo_api(self):
        """Return a WooCommerce API object"""
        self.ensure_one()
        return API(
            url=self.woo_url,
            consumer_key=self.woo_consumer_key,
            consumer_secret=self.woo_consumer_secret,
            version=self.woo_version,
            verify_ssl=self.is_ssl_verify,
            wp_api=True,
            timeout=40,
            query_string_auth=True,
        )


    def _get_backend_adapter(self, model_name):
        """Return an adapter for the model"""
        with self.env['woo.backend'].work_on(model_name, backend_record=self) as work:
            return work.component(usage='backend.adapter')

    @api.model
    def _scheduler_import_products(self, backend_id=None):
        """Schedule the import of products from WooCommerce"""
        backends = self
        if backend_id:
            backends = self.browse(backend_id)
        else:
            backends = self.search([('state', '=', 'active')])

        for backend in backends:
            backend.import_products()
        return True

    @api.model
    def _scheduler_import_orders(self, backend_id=None):
        """Schedule the import of orders from WooCommerce"""
        backends = self
        if backend_id:
            backends = self.browse(backend_id)
        else:
            backends = self.search([('state', '=', 'active')])

        for backend in backends:
            backend.import_orders()
        return True

    @api.model
    def _scheduler_export_stock(self, backend_id=None):
        """Schedule the export of stock to WooCommerce"""
        backends = self
        if backend_id:
            backends = self.browse(backend_id)
        else:
            backends = self.search([('state', '=', 'active')])

        for backend in backends:
            backend.export_stock()
        return True

    def import_products(self):
        """Queue the import of products from WooCommerce"""
        self.ensure_one()
        if self.state != 'active':
            return _("Backend %s is not active") % self.name

        from_date = self.last_product_import_date or self.import_products_from_date
        filters = {}
        if from_date:
            filters.update({'modified_after': from_date.isoformat()})

        if self.product_import_rule == 'published':
            filters.update({'status': 'publish'})

        self.env['woo.product.template'].with_delay(priority=10).import_batch(
            backend=self, filters=filters
        )
        return _("Product import jobs created")

    def import_orders(self):
        """Queue the import of orders from WooCommerce"""
        self.ensure_one()
        if self.state != 'active':
            return _("Backend %s is not active") % self.name

        from_date = self.last_order_import_date or self.import_orders_from_date
        filters = {}
        if from_date:
            filters.update({'modified_after': from_date.isoformat()})

        if self.order_import_rule == 'processing':
            filters.update({'status': 'processing'})

        self.env['woo.sale.order'].with_delay(priority=20).import_batch(
            backend=self, filters=filters
        )
        return _("Order import jobs created")

    def export_stock(self):
        """Queue the export of stock to WooCommerce"""
        self.ensure_one()
        if self.state != 'active':
            return _("Backend %s is not active") % self.name

        product_bindings = self.env['woo.product.template'].search([
            ('backend_id', '=', self.id)
        ])

        for binding in product_bindings:
            binding.with_delay(priority=15).export_stock()

        self.last_stock_export_date = fields.Datetime.now()
        return _("Stock export jobs created")