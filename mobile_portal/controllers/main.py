# -*- coding: utf-8 -*-
import logging
from odoo import http, release
from odoo.http import request
from odoo.addons.web.controllers.utils import ensure_db
from odoo.exceptions import AccessDenied

_logger = logging.getLogger(__name__)

# Detect Odoo major version once at module load time
_ODOO_MAJOR = int(release.version_info[0])


class MobilePortalController(http.Controller):

    # ── SPA Shell ─────────────────────────────────────────────────────────────
    @http.route('/my/shop', type='http', auth='public', website=False, sitemap=False)
    def mobile_shop(self, **kw):
        uid         = request.session.uid
        partner_name = ""
        partner_id   = 0
        is_logged_in = 0
        if uid:
            try:
                user = request.env['res.users'].sudo().browse(uid)
                partner_name = user.name or ""
                partner_id   = user.partner_id.id if user.partner_id else 0
                is_logged_in = 1
            except Exception:
                pass
        return request.render('mobile_portal.portal_app_shell', {
            'partner_name':  partner_name,
            'partner_id':    partner_id,
            'is_logged_in':  is_logged_in,
        })

    # ── Login ─────────────────────────────────────────────────────────────────
    @http.route('/my/shop/api/login', type='json', auth='none', methods=['POST'], csrf=False)
    def api_login(self, login='', password='', **kw):
        if not login or not password:
            return {'error': 'Vui lòng nhập email và mật khẩu'}

        # 1. Xác định database (Giống như ensure_db trong signin)
        # Nếu request.session.db không có, Odoo 18 sẽ bị lỗi kết nối
        dbname = request.session.db or http.db_list()[0]  # Lấy db hiện tại hoặc db đầu tiên
        ensure_db(db=dbname)

        try:
            # Odoo 18 hỗ trợ truyền dictionary vào authenticate
            if release.version_info[0] >= 18:
                credential = {'login': login, 'password': password, 'type': 'password'}
                # Gọi với dbname rõ ràng để tránh Odoo nhầm login làm dbname
                auth_info = request.session.authenticate(dbname, credential)
                uid = auth_info.get('uid')
            else:
                # Tương thích ngược Odoo 17
                uid = request.session.authenticate(dbname, login, password)

        except AccessDenied:
            return {'error': 'Email hoặc mật khẩu không chính xác'}
        except Exception as e:
            _logger.error("api_login error: %s", e)
            return {'error': 'Lỗi hệ thống khi đăng nhập'}

        if not uid:
            return {'error': 'Không thể xác thực người dùng'}

        user = request.env['res.users'].sudo().browse(uid)
        return {
            'success': True,
            'uid': uid,
            'partner_name': user.name,
            'partner_id': user.partner_id.id,
            'session_id': request.session.sid,
        }

    # ── Logout ────────────────────────────────────────────────────────────────
    @http.route('/my/shop/api/logout', type='json', auth='public', methods=['POST'], csrf=False)
    def api_logout(self, **kw):
        request.session.logout(keep_db=True)
        return {'success': True}

    # ── Register ──────────────────────────────────────────────────────────────
    @http.route('/my/shop/api/register', type='json', auth='public', methods=['POST'], csrf=False)
    def api_register(self, name='', email='', password='', phone='', **kw):
        if not name or not email or not password:
            return {'error': 'Vui lòng điền đầy đủ thông tin bắt buộc'}
        if len(password) < 6:
            return {'error': 'Mật khẩu phải có ít nhất 6 ký tự'}

        Users = request.env['res.users'].sudo()
        if Users.search([('login', '=', email)], limit=1):
            return {'error': 'Email này đã được đăng ký. Vui lòng đăng nhập.'}

        try:
            portal_group = request.env.ref('base.group_portal')
            partner = request.env['res.partner'].sudo().create({
                'name': name, 'email': email,
                'phone': phone or False, 'type': 'contact',
            })
            user = Users.create({
                'name': name, 'login': email, 'email': email,
                'partner_id': partner.id,
                'groups_id': [(6, 0, [portal_group.id])],
            })
            user.with_context(no_reset_password=True).write({'password': password})
            return {'success': True, 'user_id': user.id}
        except Exception as e:
            request.env.cr.rollback()
            msg = str(e)
            if 'unique' in msg.lower() or 'duplicate' in msg.lower():
                return {'error': 'Email này đã tồn tại trong hệ thống'}
            _logger.error("api_register error: %s", e, exc_info=True)
            return {'error': f'Đăng ký thất bại: {e}'}

    # ── Products ──────────────────────────────────────────────────────────────
    @http.route('/my/shop/api/products', type='json', auth='user', methods=['POST'])
    def api_get_products(self, **kw):
        products = request.env['product.template'].sudo().search_read(
            [('sale_ok', '=', True), ('active', '=', True)],
            fields=['id', 'name', 'list_price', 'uom_id', 'categ_id'],
            limit=100, order='name asc',
        )
        PALETTES = [
            ('#E1F5EE','#085041'),('#FAECE7','#712B13'),('#FAEEDA','#633806'),
            ('#FBEAF0','#72243E'),('#EAF3DE','#27500A'),('#E6F1FB','#0C447C'),
        ]
        categ_map, idx = {}, 0
        result = []
        for p in products:
            cat = p['categ_id'][1] if p.get('categ_id') else 'Khác'
            if cat not in categ_map:
                categ_map[cat] = PALETTES[idx % len(PALETTES)]
                idx += 1
            bg, tc = categ_map[cat]
            result.append({
                'id': p['id'], 'name': p['name'],
                'price': p['list_price'],
                'unit': p['uom_id'][1] if p.get('uom_id') else '',
                'cat': cat, 'bg': bg, 'tc': tc,
                'letter': p['name'][0].upper() if p['name'] else '?',
            })
        return {'products': result, 'categories': ['Tất cả'] + sorted(categ_map.keys())}

    # ── Orders ────────────────────────────────────────────────────────────────
    @http.route('/my/shop/api/orders', type='json', auth='user', methods=['POST'])
    def api_get_orders(self, **kw):
        partner    = request.env.user.partner_id
        STATUS_MAP = {
            'draft':  ('draft',     'Nháp'),
            'sent':   ('confirmed', 'Đã gửi'),
            'sale':   ('confirmed', 'Đã xác nhận'),
            'done':   ('done',      'Hoàn thành'),
            'cancel': ('cancel',    'Đã hủy'),
        }
        PALETTES = [
            ('#E1F5EE','#085041'),('#FAECE7','#712B13'),('#FAEEDA','#633806'),
            ('#FBEAF0','#72243E'),('#EAF3DE','#27500A'),('#E6F1FB','#0C447C'),
        ]
        orders = request.env['sale.order'].sudo().search(
            [('partner_id', '=', partner.id)], order='date_order desc', limit=50,
        )
        result = []
        for o in orders:
            st_key, st_label = STATUS_MAP.get(o.state, ('draft', o.state))
            pickings = o.picking_ids.filtered(lambda p: p.state not in ('cancel', 'done'))
            if pickings and o.state == 'sale':
                st_key, st_label = 'delivery', 'Đang giao'
            lines = []
            for i, l in enumerate(o.order_line[:10]):
                bg, tc = PALETTES[i % len(PALETTES)]
                lines.append({
                    'name': l.product_id.name, 'qty': l.product_uom_qty,
                    'price': l.price_unit, 'bg': bg, 'tc': tc,
                    'letter': l.product_id.name[0].upper() if l.product_id.name else '?',
                })
            paid = sum(
                m.amount_total for m in o.invoice_ids
                if m.state == 'posted' and m.payment_state in ('paid', 'in_payment', 'partial')
            )
            result.append({
                'id': o.id, 'ref': o.name,
                'date': o.date_order.strftime('%d/%m/%Y') if o.date_order else '',
                'status': st_key, 'label': st_label, 'lines': lines,
                'total': o.amount_total, 'paid': min(paid, o.amount_total), 'note': o.note or '',
            })
        payments = request.env['account.payment'].sudo().search(
            [('partner_id', '=', partner.id), ('state', '=', 'posted')],
            order='date desc', limit=20,
        )
        pay_result = [{
            'ref': p.name, 'date': p.date.strftime('%d/%m/%Y') if p.date else '',
            'amount': p.amount, 'method': p.journal_id.name or '', 'orderRef': p.ref or '',
        } for p in payments]
        return {'orders': result, 'payments': pay_result}

    # ── Place Order ───────────────────────────────────────────────────────────
    @http.route('/my/shop/api/place_order', type='json', auth='user', methods=['POST'])
    def api_place_order(self, cart_items=None, **kw):
        if not cart_items:
            return {'error': 'Giỏ hàng trống'}

        # Lấy thông tin partner từ user hiện tại
        partner = request.env.user.partner_id

        # LẤY BẢNG GIÁ:
        # Ưu tiên lấy bảng giá được thiết lập riêng cho khách hàng này,
        # nếu không có thì Odoo sẽ tự lấy bảng giá mặc định của hệ thống.
        pricelist = partner.property_product_pricelist

        lines = []
        for item in cart_items:
            product = request.env['product.product'].sudo().browse(item['product_id'])
            if not product.exists():
                continue

            price_unit = item.get('price_unit')
            if not price_unit:
                price_unit = pricelist._get_product_price(product, item['qty'], partner=partner)

            lines.append((0, 0, {
                'product_id': product.id,
                'product_uom_qty': item['qty'],
                'price_unit': price_unit,
                'product_uom': product.uom_id.id,
            }))

        if not lines:
            return {'error': 'Không có sản phẩm hợp lệ'}

        order_vals = {
            'partner_id': partner.id,
            'pricelist_id': pricelist.id,  # Bổ sung dòng này để hết lỗi KeyError
            'order_line': lines,
        }

        # Sử dụng sudo() để đảm bảo quyền tạo đơn hàng từ Portal
        order = request.env['sale.order'].sudo().create(order_vals)

        return {
            'success': True,
            'order_id': order.id,
            'order_ref': order.name,
        }

    # ── Barcode ───────────────────────────────────────────────────────────────
    @http.route('/my/shop/api/barcode', type='json', auth='user', methods=['POST'])
    def api_barcode(self, barcode='', **kw):
        if not barcode:
            return {'error': 'Barcode trống'}
        product = request.env['product.product'].sudo().search(
            ['|', ('barcode', '=', barcode), ('default_code', '=', barcode)], limit=1,
        )
        if not product:
            return {'error': f'Không tìm thấy: {barcode}'}
        return {
            'found': True,
            'product': {
                'id': product.product_tmpl_id.id, 'product_id': product.id,
                'name': product.name, 'price': product.lst_price,
                'unit': product.uom_id.name if product.uom_id else '',
                'cat':  product.product_tmpl_id.categ_id.name if product.product_tmpl_id.categ_id else '',
                'bg': '#E1F5EE', 'tc': '#085041',
                'letter': product.name[0].upper() if product.name else '?',
            }
        }
