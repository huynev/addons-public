from odoo import http
from odoo.http import request

class TikTokShopController(http.Controller):

    @http.route('/tiktok_shop/webhook', type='json', auth='public', methods=['POST'])
    def tiktok_shop_webhook(self):
        data = request.jsonrequest
        if data.get('event_type') == 'order_created':
            tiktok_shop = request.env['tiktok.shop'].sudo().search([], limit=1)
            if tiktok_shop:
                tiktok_shop.create_order_from_tiktok(data['order'])
        return {'status': 'success'}