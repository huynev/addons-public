# Copyright 2024 Wokwy - quochuy.software@gmail.com
from odoo import models, fields, api

class ZaloZnsConfig(models.Model):
    _name = 'zalo.zns.config'
    _description = 'Zalo ZNS Configuration'

    name = fields.Char(string='Configuration Name', required=True, default='Default Configuration')
    api_url = fields.Char(string='API URL', required=True)
    access_token = fields.Char(string='Access Token', required=True)

    @api.model
    def get_config(self):
        config = self.search([], limit=1)
        if not config:
            config = self.create({
                'name': 'Default Configuration',
                'api_url': 'https://business.openapi.zalo.me/message/template',
                'access_token': 'Default Token'
            })
        return config