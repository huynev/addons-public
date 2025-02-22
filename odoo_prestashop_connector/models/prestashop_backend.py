from odoo import models, fields, api
from prestapyt import PrestaShopWebService
from ..lib.prestashop_lib import PrestaShopWebService
import logging

_logger = logging.getLogger(__name__)

class PrestashopBackend(models.Model):
    _name = 'prestashop.backend'
    _inherit = 'connector.backend'
    _description = 'PrestaShop Backend Configuration'

    name = fields.Char(required=True)
    url = fields.Char('PrestaShop URL', required=True)
    webservice_key = fields.Char('Webservice Key', required=True)
    version = fields.Selection([
        ('1.7.8.9', 'Version 1.7.8.9'),
        ('8.0', 'Version 8.0'),
    ], string='Version', required=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company',
        'Company',
        required=True,
        default=lambda self: self.env.company
    )
    warehouse_id = fields.Many2one(
        'stock.warehouse',
        'Warehouse',
        required=True
    )
    import_products_since = fields.Datetime('Import Products Since')
    import_orders_since = fields.Datetime('Import Orders Since')

    # Synchronization settings
    sync_orders = fields.Boolean('Sync Orders', default=False)
    sync_products = fields.Boolean('Sync Products', default=False)
    sync_customers = fields.Boolean('Sync Customers', default=False)

    # Synchronization intervals
    order_sync_interval = fields.Integer('Order Sync Interval (minutes)', default=30)
    product_sync_interval = fields.Integer('Product Sync Interval (minutes)', default=60)
    customer_sync_interval = fields.Integer('Customer Sync Interval (minutes)', default=60)

    def test_connection(self):
        self.ensure_one()
        try:
            prestashop = PrestaShopWebService(
                self.url,
                self.webservice_key
            )
            prestashop.head('')
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Success',
                    'message': 'Connection test successful',
                    'type': 'success',
                }
            }
        except Exception as e:
            _logger.error('PrestaShop connection error: %s', str(e))
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error',
                    'message': str(e),
                    'type': 'danger',
                }
            }

    def _get_prestashop_client(self):
        self.ensure_one()
        try:
            return PrestaShopWebService(
                self.url,
                self.webservice_key
            )
        except Exception as e:
            _logger.error('PrestaShop connection error: %s', str(e))
            raise

    def create_synchronization_cron_jobs(self):
        """
        Create scheduled actions for synchronization based on backend settings
        """
        # Create cron for order synchronization
        if self.sync_orders:
            self.env['ir.cron'].create({
                'name': f'Sync Orders - {self.name}',
                'model_id': self.env.ref('odoo_prestashop_connector.model_prestashop_order_sync_service').id,
                'state': 'code',
                'code': f'model.manual_order_sync({self.id})',
                'interval_number': self.order_sync_interval,
                'interval_type': 'minutes',
                'numbercall': -1,
                'doall': False,
            })

        # Similar cron jobs can be created for products and customers
        # Implement product and customer synchronization similarly