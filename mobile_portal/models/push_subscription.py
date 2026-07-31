# -*- coding: utf-8 -*-
import json
import logging

from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class MobilePortalPushSubscription(models.Model):
    _name        = 'mobile.portal.push.subscription'
    _description = 'PWA Push Subscription'
    _rec_name    = 'endpoint'

    partner_id = fields.Many2one('res.partner', required=True, ondelete='cascade', index=True)
    endpoint   = fields.Text('Endpoint', required=True)
    auth       = fields.Char('Auth Key',   required=True)
    p256dh     = fields.Char('P256DH Key', required=True)
    active     = fields.Boolean(default=True)

    _sql_constraints = [
        ('endpoint_uniq', 'UNIQUE(endpoint)', 'Push endpoint already registered'),
    ]

    @api.model
    def notify_partner(self, partner_id, title, body, url='/my/shop', tag='default'):
        """
        Send push notification to all active subscriptions of a partner.
        Requires: pip install pywebpush
        """
        subs = self.search([('partner_id', '=', partner_id), ('active', '=', True)])
        for sub in subs:
            sub._send(title=title, body=body, url=url, tag=tag)

    def _send(self, title, body, url='/my/shop', tag='default'):
        """Send push to this subscription."""
        ICP         = self.env['ir.config_parameter'].sudo()
        private_key = ICP.get_param('mobile_portal.vapid_private')
        email       = ICP.get_param('mobile_portal.vapid_email', 'noreply@example.com')

        if not private_key:
            _logger.warning('[mobile_portal] VAPID private key not configured.')
            return

        try:
            from pywebpush import webpush, WebPushException
        except ImportError:
            _logger.error(
                '[mobile_portal] Push notifications require pywebpush. '
                'Run: pip install pywebpush'
            )
            return

        payload = json.dumps({'title': title, 'body': body, 'url': url, 'tag': tag})
        try:
            webpush(
                subscription_info={
                    'endpoint': self.endpoint,
                    'keys': {'auth': self.auth, 'p256dh': self.p256dh},
                },
                data=payload,
                vapid_private_key=private_key,
                vapid_claims={'sub': f'mailto:{email}'},
            )
        except Exception as e:
            response = getattr(e, 'response', None)
            if response is not None and response.status_code in (404, 410):
                # Subscription expired or revoked by the browser
                self.active = False
            else:
                _logger.warning('[mobile_portal] Push send error: %s', e)
