# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import json
import logging

_logger = logging.getLogger(__name__)


class WooCommerceController(http.Controller):
    """
    This controller handles webhooks from WooCommerce.
    Configure your WooCommerce store to send webhooks to:
    https://your-odoo-server.com/woo_connector/webhook/<backend_id>
    """

    @http.route('/woo_connector/webhook/<int:backend_id>', type='json', auth='public', csrf=False)
    def webhook(self, backend_id, **kwargs):
        """
        Handle WooCommerce webhooks
        """
        _logger.info("WooCommerce webhook received for backend %s", backend_id)

        # Get the backend
        backend = request.env['woo.backend'].sudo().browse(backend_id)
        if not backend.exists():
            _logger.error("WooCommerce webhook: Backend %s not found", backend_id)
            return json.dumps({'error': 'Backend not found'})

        if backend.state != 'active':
            _logger.error("WooCommerce webhook: Backend %s is not active", backend_id)
            return json.dumps({'error': 'Backend not active'})

        # Get the webhook data
        webhook_data = request.jsonrequest

        # Check the topic
        topic = request.httprequest.headers.get('X-WC-Webhook-Topic')
        if not topic:
            _logger.error("WooCommerce webhook: No topic provided")
            return json.dumps({'error': 'No topic provided'})

        # Process the webhook
        if topic.startswith('product'):
            self._process_product_webhook(backend, topic, webhook_data)
        elif topic.startswith('order'):
            self._process_order_webhook(backend, topic, webhook_data)
        elif topic.startswith('customer'):
            self._process_customer_webhook(backend, topic, webhook_data)

        return json.dumps({'success': True})

    def _process_product_webhook(self, backend, topic, data):
        """Process product webhook"""
        if topic == 'product.created' or topic == 'product.updated':
            # Queue a job to import/update this product
            product_id = data.get('id')
            if product_id:
                request.env['woo.product.template'].with_delay().import_record(
                    backend, product_id
                )
                _logger.info("WooCommerce webhook: Product %s queued for import", product_id)
        elif topic == 'product.deleted':
            # Deactivate the product
            product_id = data.get('id')
            if product_id:
                binding = request.env['woo.product.template'].sudo().search([
                    ('backend_id', '=', backend.id),
                    ('woo_id', '=', str(product_id))
                ], limit=1)
                if binding:
                    binding.odoo_id.active = False
                    _logger.info("WooCommerce webhook: Product %s deactivated", product_id)

    def _process_order_webhook(self, backend, topic, data):
        """Process order webhook"""
        if topic == 'order.created' or topic == 'order.updated':
            # Queue a job to import/update this order
            order_id = data.get('id')
            if order_id:
                request.env['woo.sale.order'].with_delay().import_record(
                    backend, order_id
                )
                _logger.info("WooCommerce webhook: Order %s queued for import", order_id)

    def _process_customer_webhook(self, backend, topic, data):
        """Process customer webhook"""
        if topic == 'customer.created' or topic == 'customer.updated':
            # Queue a job to import/update this customer
            customer_id = data.get('id')
            if customer_id:
                request.env['woo.res.partner'].with_delay().import_record(
                    backend, customer_id
                )
                _logger.info("WooCommerce webhook: Customer %s queued for import", customer_id)