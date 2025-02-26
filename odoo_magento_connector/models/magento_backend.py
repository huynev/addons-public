from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
import requests
import json

_logger = logging.getLogger(__name__)


class MagentoBackend(models.Model):
    _name = 'magento.backend'
    _description = 'Magento Backend'
    _inherit = 'connector.backend'

    name = fields.Char(string='Name', required=True)
    version = fields.Selection([
        ('2.0', 'Magento 2.0'),
        ('2.1', 'Magento 2.1'),
        ('2.2', 'Magento 2.2'),
        ('2.3', 'Magento 2.3'),
        ('2.4', 'Magento 2.4'),
    ], string='Version', required=True)
    location = fields.Char(
        string='Location',
        required=True,
        help="URL of the Magento instance. Example: https://mymagento.com"
    )
    access_token = fields.Char(
        string='Access Token',
        required=True,
        help="REST API access token"
    )
    default_lang_id = fields.Many2one(
        'res.lang',
        string='Default Language',
        required=True
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company
    )
    website_ids = fields.One2many(
        'magento.website',
        'backend_id',
        string='Websites'
    )
    import_products_from_date = fields.Datetime(
        string='Import Products from Date'
    )
    import_orders_from_date = fields.Datetime(
        string='Import Orders from Date'
    )
    active = fields.Boolean(
        string='Active',
        default=True
    )
    admin_notification_mail = fields.Char(
        string='E-mail for sync notifications',
        help="Where to send notifications about synchronization status"
    )

    def check_magento_connection(self):
        """Test the connection to Magento"""
        self.ensure_one()
        try:
            client = self._get_magento_client()
            # Test the connection by making a simple request
            response = client.get_websites()
            if response:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Connection Test'),
                        'message': _('Connection to Magento successful!'),
                        'sticky': True,
                        'type': 'danger',
                    }
                }
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Connection Test Failed'),
                    'message': _('Connection to Magento failed: %s') % str(e),
                    'sticky': True,
                    'type': 'danger',
                }
            }

    def import_websites(self):
        """Import all websites from Magento"""
        for backend in self:
            try:
                client = backend._get_magento_client()
                websites = client.get_websites()

                for website_data in websites:
                    website_id = website_data.get('id')
                    website_code = website_data.get('code')
                    website_name = website_data.get('name')

                    # Search for existing website
                    website = self.env['magento.website'].search([
                        ('backend_id', '=', backend.id),
                        ('external_id', '=', website_id)
                    ], limit=1)

                    if website:
                        # Update existing website
                        website.write({
                            'code': website_code,
                            'name': website_name,
                        })
                    else:
                        # Create new website
                        self.env['magento.website'].create({
                            'backend_id': backend.id,
                            'external_id': website_id,
                            'code': website_code,
                            'name': website_name,
                        })

                # Import stores for each website
                for website in backend.website_ids:
                    website.import_stores()

                notification = {
                    'type': 'success',
                    'title': _('Websites Imported'),
                    'message': _('Successfully imported %d websites from Magento') % len(websites),
                }
                return notification

            except Exception as e:
                title = _('Connection Test Failed')
                message = _('Connection to Magento failed: %s') % str(e)
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': title,
                        'message': message,
                        'sticky': True,
                        'type': 'danger',
                    }
                }

    def _scheduler_import_products(self):
        """Scheduler for importing products"""
        backends = self.search([('active', '=', True)])
        for backend in backends:
            backend.with_delay(channel='root.magento').import_products()

    def _scheduler_import_orders(self):
        """Scheduler for importing orders"""
        backends = self.search([('active', '=', True)])
        for backend in backends:
            backend.with_delay(channel='root.magento').import_orders()

    def _scheduler_update_stock(self):
        """Scheduler for exporting stock levels"""
        backends = self.search([('active', '=', True)])
        for backend in backends:
            backend.with_delay(channel='root.magento').export_stock_levels()

    def import_products(self):
        """Import products from Magento - delegated to each store"""
        self.ensure_one()
        for website in self.website_ids:
            for store in website.store_ids:
                store.with_delay(channel='root.magento.product').import_products()

    def import_orders(self):
        """Import orders from Magento - delegated to each store"""
        self.ensure_one()
        for website in self.website_ids:
            for store in website.store_ids:
                store.with_delay(channel='root.magento.sale').import_orders()

    def export_stock_levels(self):
        """Export stock levels to Magento"""
        self.ensure_one()
        product_bindings = self.env['magento.product.product'].search([
            ('magento_website_ids', 'in', self.website_ids.ids)
        ])
        for product_binding in product_bindings:
            product_binding.with_delay(
                channel='root.magento.stock'
            ).export_stock()

    def _get_magento_client(self):
        """Return a Magento API client"""
        self.ensure_one()
        return MagentoAPI(self.location, self.access_token, self.version)


class MagentoAPI:
    """Wrapper for Magento 2 REST API"""

    def __init__(self, url, access_token, version):
        self.url = url.rstrip('/')
        self.access_token = access_token
        self.version = version
        self.api_url = f"{self.url}/rest/V1"

    def _make_request(self, endpoint, method='GET', data=None, params=None):
        """Make a request to the Magento API"""
        url = f"{self.api_url}/{endpoint}"
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }

        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, params=params)
            elif method == 'POST':
                response = requests.post(url, headers=headers, data=json.dumps(data))
            elif method == 'PUT':
                response = requests.put(url, headers=headers, data=json.dumps(data))
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers)
            else:
                raise ValueError(f"Unsupported method: {method}")

            response.raise_for_status()
            return response.json() if response.content else None

        except requests.exceptions.HTTPError as e:
            _logger.error(f"HTTP Error: {e}")
            if e.response.content:
                try:
                    error_data = e.response.json()
                    error_message = error_data.get('message', str(e))
                    _logger.error(f"Magento API Error: {error_message}")
                    raise UserError(f"Magento API Error: {error_message}")
                except json.JSONDecodeError:
                    _logger.error(f"Error parsing response: {e.response.content}")
                    raise UserError(f"Error communicating with Magento: {str(e)}")
            raise UserError(f"Error communicating with Magento: {str(e)}")
        except requests.exceptions.ConnectionError as e:
            _logger.error(f"Connection Error: {e}")
            raise UserError(f"Could not connect to Magento: {str(e)}")
        except requests.exceptions.Timeout as e:
            _logger.error(f"Timeout Error: {e}")
            raise UserError(f"Timeout connecting to Magento: {str(e)}")
        except requests.exceptions.RequestException as e:
            _logger.error(f"Request Error: {e}")
            raise UserError(f"Error communicating with Magento: {str(e)}")
        except Exception as e:
            _logger.error(f"Unexpected Error: {e}")
            raise UserError(f"Unexpected error: {str(e)}")

    # Website related methods
    def get_websites(self):
        """Get all websites from Magento"""
        return self._make_request('store/websites')

    def get_stores(self, website_id=None):
        """Get all stores from Magento"""
        if website_id:
            # Filter stores by website ID through query parameters
            return self._make_request('store/storeGroups', params={'websiteId': website_id})
        return self._make_request('store/storeGroups')

    def get_store_views(self, store_id=None):
        """Get all storeviews from Magento"""
        if store_id:
            # Filter storeviews by store ID through query parameters
            return self._make_request('store/storeViews', params={'storeGroupId': store_id})
        return self._make_request('store/storeViews')

    # Product related methods
    def get_products(self, filters=None, page=1, limit=100):
        """Get products from Magento"""
        params = {
            'searchCriteria[currentPage]': page,
            'searchCriteria[pageSize]': limit,
        }

        # Add filters
        if filters:
            for i, (field, condition, value) in enumerate(filters):
                params[f'searchCriteria[filterGroups][0][filters][{i}][field]'] = field
                params[f'searchCriteria[filterGroups][0][filters][{i}][conditionType]'] = condition
                params[f'searchCriteria[filterGroups][0][filters][{i}][value]'] = value

        return self._make_request('products', params=params)

    def get_product(self, sku):
        """Get a specific product from Magento by SKU"""
        return self._make_request(f'products/{sku}')

    def create_product(self, product_data):
        """Create a product in Magento"""
        return self._make_request('products', method='POST', data={'product': product_data})

    def update_product(self, sku, product_data):
        """Update a product in Magento"""
        return self._make_request(f'products/{sku}', method='PUT', data={'product': product_data})

    def delete_product(self, sku):
        """Delete a product in Magento"""
        return self._make_request(f'products/{sku}', method='DELETE')

    # Stock related methods
    def get_stock_item(self, sku):
        """Get stock information for a product"""
        return self._make_request(f'stockItems/{sku}')

    def update_stock_item(self, sku, stock_data):
        """Update stock information for a product"""
        return self._make_request(f'products/{sku}/stockItems/{sku}', method='PUT', data={'stockItem': stock_data})

    # Order related methods
    def get_orders(self, filters=None, page=1, limit=100):
        """Get orders from Magento"""
        params = {
            'searchCriteria[currentPage]': page,
            'searchCriteria[pageSize]': limit,
        }

        # Add filters
        if filters:
            for i, (field, condition, value) in enumerate(filters):
                params[f'searchCriteria[filterGroups][0][filters][{i}][field]'] = field
                params[f'searchCriteria[filterGroups][0][filters][{i}][conditionType]'] = condition
                params[f'searchCriteria[filterGroups][0][filters][{i}][value]'] = value

        return self._make_request('orders', params=params)

    def get_order(self, order_id):
        """Get a specific order from Magento"""
        return self._make_request(f'orders/{order_id}')

    def create_order(self, order_data):
        """Create an order in Magento"""
        return self._make_request('orders', method='POST', data={'entity': order_data})
