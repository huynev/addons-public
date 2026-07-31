# -*- coding: utf-8 -*-
import logging
from datetime import datetime
from odoo import http, release, fields
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
        uid          = request.session.uid
        partner_name = ""
        partner_id   = 0
        is_logged_in = 0
        if uid:
            try:
                user         = request.env['res.users'].sudo().browse(uid)
                partner_name = user.name or ""
                partner_id   = user.partner_id.id if user.partner_id else 0
                is_logged_in = 1
            except Exception:
                pass
        return request.render('mobile_portal.portal_app_shell', {
            'partner_name': partner_name,
            'partner_id':   partner_id,
            'is_logged_in': is_logged_in,
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

    # ── Service Worker ────────────────────────────────────────────────────────
    @http.route('/my/shop/sw.js', type='http', auth='public', website=False, sitemap=False)
    def pwa_sw(self, **kw):
        import os
        sw_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'static', 'src', 'sw.js',
        )
        try:
            with open(sw_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except OSError:
            return request.not_found()
        return request.make_response(content, headers=[
            ('Content-Type',          'application/javascript'),
            ('Service-Worker-Allowed', '/'),        # Allow SW to control entire /my/shop scope
            ('Cache-Control',          'no-store'), # Always serve fresh SW
        ])

    # ── PWA Manifest ──────────────────────────────────────────────────────────
    @http.route('/my/shop/manifest.json', type='http', auth='public', website=False, sitemap=False)
    def pwa_manifest(self, **kw):
        import json
        import os
        # Gắn thêm ?v=<mtime file logo> vào URL icon — mỗi khi thay file logo,
        # URL đổi theo nên Safari/Chrome coi là ảnh MỚI, tự tải lại thay vì
        # dùng bản đã cache cũ (không phải sửa lần này mới cần, áp dụng luôn
        # cho các lần đổi icon sau này).
        logo_path = os.path.normpath(os.path.join(
            os.path.dirname(__file__), '..', 'static', 'description', 'qh.png'))
        try:
            icon_version = int(os.path.getmtime(logo_path))
        except OSError:
            icon_version = 1

        manifest = {
            "name": "Cổng Khách Hàng",
            "short_name": "Shop",
            "start_url": "/my/shop",
            "scope": "/my/shop",
            "display": "standalone",
            "orientation": "portrait",
            "theme_color": "#F78614",
            "background_color": "#f4f3ee",
            "lang": "vi",
            "icons": [
                {"src": "/my/shop/icon/192?v=%s" % icon_version, "sizes": "192x192", "type": "image/png", "purpose": "any maskable"},
                {"src": "/my/shop/icon/512?v=%s" % icon_version, "sizes": "512x512", "type": "image/png", "purpose": "any maskable"},
            ],
        }
        return request.make_response(
            json.dumps(manifest),
            headers=[
                ('Content-Type', 'application/manifest+json'),
                ('Cache-Control', 'public, max-age=3600'),
            ]
        )

    # ── PWA Icon ────────────────────────────────────────────────────────────
    # Trước đây icon chỉ là 1 khối màu cam đặc, không có hình vẽ gì bên trong —
    # đó là lý do khi "Add to Home Screen" trên iPhone chỉ thấy 1 ô màu cam
    # trơn, không có logo. Giờ dùng logo thật (static/description/qh.png,
    # QH Trading & I.T. Services) bằng Pillow; nếu môi trường thiếu Pillow
    # hoặc thiếu file logo thì tự động rơi về màu cam trơn như cũ (không lỗi 500).
    @http.route('/my/shop/icon/<int:size>', type='http', auth='public', website=False, sitemap=False)
    def pwa_icon(self, size=192, **kw):
        size = min(max(size, 16), 1024)
        try:
            png = self._pwa_icon_png(size)
        except (ImportError, OSError):
            png = self._pwa_icon_solid_png(size)

        return request.make_response(
            png,
            headers=[
                ('Content-Type', 'image/png'),
                ('Cache-Control', 'public, max-age=86400'),
                ('Content-Length', str(len(png))),
            ]
        )

    def _pwa_icon_png(self, size):
        import io
        import os
        from PIL import Image

        logo_path = os.path.join(os.path.dirname(__file__), '..', 'static', 'description', 'qh.png')
        logo = Image.open(os.path.normpath(logo_path)).convert('RGBA')

        # Cắt bỏ phần chữ "TRADING & I.T. SERVICES" bên dưới — chỉ giữ lại
        # biểu tượng (chữ QH + vệt sóng cam) vì chữ nhỏ sẽ không đọc được ở
        # kích thước icon (192/512px).
        w, h = logo.size
        mark = logo.crop((0, 0, w, int(h * 0.85)))

        # Canvas vuông nền trắng, chừa lề ~12% mỗi bên để icon "maskable"
        # (iOS/Android có thể cắt viền tròn) không bị mất nội dung.
        canvas = Image.new('RGBA', (size, size), '#ffffff')
        pad = size * 0.12
        avail = size - 2 * pad
        mw, mh = mark.size
        scale = min(avail / mw, avail / mh)
        new_w, new_h = max(1, int(mw * scale)), max(1, int(mh * scale))
        mark = mark.resize((new_w, new_h), Image.LANCZOS)
        offset = (int((size - new_w) / 2), int((size - new_h) / 2))
        canvas.paste(mark, offset, mark)

        buf = io.BytesIO()
        canvas.convert('RGB').save(buf, format='PNG')
        return buf.getvalue()

    def _pwa_icon_solid_png(self, size):
        import struct, zlib
        r, g, b = 247, 134, 20   # #F78614

        row = bytes([0]) + bytes([r, g, b] * size)
        raw = row * size
        idat_data = zlib.compress(raw, 9)

        def png_chunk(tag, data):
            length = struct.pack('>I', len(data))
            body   = tag + data
            crc    = struct.pack('>I', zlib.crc32(body) & 0xFFFFFFFF)
            return length + body + crc

        ihdr = struct.pack('>IIBBBBB', size, size, 8, 2, 0, 0, 0)
        return (b'\x89PNG\r\n\x1a\n'
                + png_chunk(b'IHDR', ihdr)
                + png_chunk(b'IDAT', idat_data)
                + png_chunk(b'IEND', b''))

    # ── Product image (portal-safe, bypass product.template access check) ────
    @http.route('/my/shop/img/<int:tmpl_id>', type='http', auth='public', website=False, sitemap=False)
    def product_image(self, tmpl_id, **kw):
        import base64
        product = request.env['product.template'].sudo().browse(tmpl_id)
        if not product.exists():
            return request.not_found()

        image_b64 = product.image_256 or product.image_128 or product.image_512
        if not image_b64:
            return request.not_found()

        image_data = base64.b64decode(image_b64)

        # Nhận diện định dạng ảnh từ header bytes
        if image_data[:8] == b'\x89PNG\r\n\x1a\n':
            mimetype = 'image/png'
        elif image_data[:3] == b'\xff\xd8\xff':
            mimetype = 'image/jpeg'
        elif image_data[:6] in (b'GIF87a', b'GIF89a'):
            mimetype = 'image/gif'
        elif image_data[:4] == b'RIFF' and image_data[8:12] == b'WEBP':
            mimetype = 'image/webp'
        else:
            mimetype = 'image/png'

        return request.make_response(
            image_data,
            headers=[
                ('Content-Type', mimetype),
                ('Cache-Control', 'public, max-age=86400'),
                ('Content-Length', str(len(image_data))),
            ]
        )

    # ── Products ──────────────────────────────────────────────────────────────
    @http.route('/my/shop/api/products', type='json', auth='user', methods=['POST'])
    def api_get_products(self, offset=0, limit=20, cat_ids=None, query='', **kw):
        PALETTES = [
            ('#FEF3E8','#6F3C09'),('#FAECE7','#712B13'),('#FAEEDA','#633806'),
            ('#FBEAF0','#72243E'),('#EAF3DE','#27500A'),('#E6F1FB','#0C447C'),
        ]

        partner         = request.env.user.partner_id
        pricelist       = partner.property_product_pricelist
        fiscal_position = request.env['account.fiscal.position'].sudo()._get_fiscal_position(partner)

        base_domain = [('sale_ok', '=', True), ('active', '=', True)]
        domain = list(base_domain)
        if cat_ids:
            domain.append(('categ_id', 'child_of', [int(i) for i in cat_ids]))
        if query:
            # Tìm theo tên sản phẩm, mã sản phẩm (default_code/barcode) hoặc tên danh mục
            domain += [
                '|', '|', '|',
                ('name', 'ilike', query),
                ('default_code', 'ilike', query),
                ('barcode', 'ilike', query),
                ('categ_id.name', 'ilike', query),
            ]

        total = request.env['product.template'].sudo().search_count(domain)
        products = request.env['product.template'].sudo().search_read(
            domain,
            fields=['id', 'name', 'default_code', 'list_price', 'uom_id', 'categ_id'],
            limit=limit, offset=offset, order='name asc',
        )

        # Build a stable palette per category (fetch all categ names for consistent colors)
        all_cats = request.env['product.template'].sudo().search_read(
            base_domain, fields=['categ_id'], order='name asc',
        )
        categ_map = {}
        for p in all_cats:
            c = p['categ_id'][1] if p.get('categ_id') else 'Khác'
            if c not in categ_map:
                categ_map[c] = PALETTES[len(categ_map) % len(PALETTES)]

        # ── Lấy tất cả variants cho các template trong trang ─────────────────
        tmpl_ids    = [p['id'] for p in products]
        all_variants = request.env['product.product'].sudo().search(
            [('product_tmpl_id', 'in', tmpl_ids), ('active', '=', True)],
            order='id asc',
        )
        tmpl_variants = {}   # tmpl_id → [product.product]
        for v in all_variants:
            tmpl_variants.setdefault(v.product_tmpl_id.id, []).append(v)

        def _price_untaxed(variant):
            if pricelist:
                try:
                    return pricelist._get_product_price(variant, 1.0, partner=partner)
                except Exception:
                    pass
            return variant.lst_price

        def _price_tax_incl(variant, price_untaxed):
            taxes = variant.taxes_id.filtered(lambda t: t.company_id == request.env.company)
            if fiscal_position:
                taxes = fiscal_position.map_tax(taxes)
            if not taxes:
                return price_untaxed
            tax_res = taxes.compute_all(
                price_untaxed, currency=request.env.company.currency_id,
                quantity=1.0, product=variant, partner=partner,
            )
            return tax_res['total_included']

        def _tax_rate(variant):
            # Thuế suất hiển thị cho khách — chỉ cộng các thuế dạng % (bỏ qua
            # thuế cố định vì không có "thuế suất" để hiển thị). flatten_taxes_hierarchy
            # để xử lý cả trường hợp thuế được cấu hình dạng "group" (gộp nhiều thuế con).
            taxes = variant.taxes_id.filtered(lambda t: t.company_id == request.env.company)
            if fiscal_position:
                taxes = fiscal_position.map_tax(taxes)
            flattened = taxes.flatten_taxes_hierarchy()
            return sum(t.amount for t in flattened if t.amount_type == 'percent')

        def _pkgs(variant):
            return [
                {'name': pk.name, 'qty': pk.qty}
                for pk in variant.packaging_ids.sorted('qty')
            ]

        result = []
        for p in products:
            tmpl_id  = p['id']
            cat_name = p['categ_id'][1] if p.get('categ_id') else 'Khác'
            bg, tc   = categ_map.get(cat_name, PALETTES[0])

            vlist            = tmpl_variants.get(tmpl_id, [])
            default_variant  = vlist[0] if vlist else None
            price_untaxed    = _price_untaxed(default_variant) if default_variant else p['list_price']
            price            = _price_tax_incl(default_variant, price_untaxed) if default_variant else price_untaxed
            default_pkgs     = _pkgs(default_variant) if default_variant else []

            # Biến thể: chỉ trả về nếu sản phẩm có nhiều hơn 1 variant
            variants_data = []
            if len(vlist) > 1:
                for v in vlist:
                    attr_name = ' / '.join(
                        av.name for av in v.product_template_attribute_value_ids
                    ) or v.display_name
                    v_price_untaxed = _price_untaxed(v)
                    variants_data.append({
                        'id':            v.id,
                        'name':          attr_name,
                        'price':         _price_tax_incl(v, v_price_untaxed),
                        'price_untaxed': v_price_untaxed,
                        'tax_rate':      _tax_rate(v),
                        'packagings':    _pkgs(v),
                    })

            result.append({
                'id':            tmpl_id,
                'variant_id':    default_variant.id if default_variant else None,
                'name':          p['name'],
                'code':          p.get('default_code') or '',
                'price':         price,
                'price_untaxed': price_untaxed,
                'tax_rate':      _tax_rate(default_variant) if default_variant else 0.0,
                'unit':          p['uom_id'][1] if p.get('uom_id') else '',
                'cat':        cat_name, 'bg': bg, 'tc': tc,
                'letter':     p['name'][0].upper() if p['name'] else '?',
                'packagings': default_pkgs,
                'variants':   variants_data,
            })

        res = {
            'products': result,
            'has_more': (offset + limit) < total,
        }
        # Only send categories on first page load
        if offset == 0:
            used_cat_ids = {p['categ_id'][0] for p in all_cats if p.get('categ_id')}
            all_relevant_ids = set()
            cat_recs = request.env['product.category'].sudo().browse(list(used_cat_ids))
            for cat in cat_recs:
                c = cat
                while c:
                    all_relevant_ids.add(c.id)
                    c = c.parent_id if c.parent_id else None
            all_cat_recs = list(request.env['product.category'].sudo().browse(list(all_relevant_ids)))

            def _build_tree(parent_id, cats):
                tree = []
                for cat in sorted(cats, key=lambda x: x.name):
                    p_id = cat.parent_id.id if cat.parent_id else None
                    if p_id == parent_id:
                        tree.append({
                            'id':       cat.id,
                            'name':     cat.name,
                            'children': _build_tree(cat.id, cats),
                        })
                return tree

            res['categories'] = _build_tree(None, all_cat_recs)
        return res

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
            ('#FEF3E8','#6F3C09'),('#FAECE7','#712B13'),('#FAEEDA','#633806'),
            ('#FBEAF0','#72243E'),('#EAF3DE','#27500A'),('#E6F1FB','#0C447C'),
        ]
        orders = request.env['sale.order'].sudo().search(
            [('partner_id', '=', partner.id)], order='date_order desc', limit=50,
        )

        def _tax_breakdown(order):
            """Gộp thuế theo NHÓM thuế (tax group, vd. 'Thuế GTGT') — dùng
            đúng field tax_totals mà Odoo tự tính cho đơn hàng, đảm bảo khớp
            100% với amount_tax (không tự recompute lại thuế)."""
            totals = order.tax_totals or {}
            rows = []
            for groups in (totals.get('groups_by_subtotal') or {}).values():
                for g in groups:
                    rows.append({'name': g['tax_group_name'], 'amount': g['tax_group_amount']})
            return rows

        result = []
        for o in orders:
            st_key, st_label = STATUS_MAP.get(o.state, ('draft', o.state))
            pickings = o.picking_ids.filtered(lambda p: p.state not in ('cancel', 'done'))
            if pickings and o.state == 'sale':
                st_key, st_label = 'delivery', 'Đang giao'
            lines = []
            for i, l in enumerate(o.order_line[:10]):
                bg, tc = PALETTES[i % len(PALETTES)]
                pkg = l.product_packaging_id
                lines.append({
                    'name': l.product_id.name, 'qty': l.product_uom_qty,
                    'price': l.price_reduce_taxinc, 'bg': bg, 'tc': tc,
                    'letter': l.product_id.name[0].upper() if l.product_id.name else '?',
                    'pkg_name':  pkg.name if pkg else '',
                    'pkg_count': l.product_packaging_qty if pkg else 0,
                    'pkg_size':  pkg.qty if pkg else 0,
                })
            # Số tiền ĐÃ thanh toán thực tế trên các hoá đơn của đơn hàng này.
            # BUG cũ: cộng nguyên amount_total của hoá đơn khi payment_state
            # là 'partial' → hiện sai thành "đã TT đủ" dù hoá đơn mới trả 1
            # phần. Phải dùng (amount_total - amount_residual) — đúng số tiền
            # đã trả trên từng hoá đơn, bất kể payment_state.
            paid = sum(
                (m.amount_total - m.amount_residual) for m in o.invoice_ids
                if m.state == 'posted'
            )
            # Tổng tiền trước chiết khấu (chưa VAT, chưa CK) — Odoo không lưu
            # sẵn field này, cộng dồn price_unit * qty của từng dòng.
            amount_before_discount = sum(
                l.price_unit * l.product_uom_qty for l in o.order_line
            )
            result.append({
                'id': o.id, 'ref': o.name,
                'date': o.date_order.strftime('%d/%m/%Y') if o.date_order else '',
                'status': st_key, 'label': st_label, 'lines': lines,
                'amount_before_discount': amount_before_discount,
                'amount_untaxed':         o.amount_untaxed,
                'tax_groups':             _tax_breakdown(o),
                'amount_tax':             o.amount_tax,
                'total': o.amount_total, 'paid': min(paid, o.amount_total), 'note': o.note or '',
            })
        return {'orders': result}

    # ── Công nợ (theo logic đối soát/phân bổ của addon payment_allocation) ──────
    @http.route('/my/shop/api/debt', type='json', auth='user', methods=['POST'])
    def api_get_debt(self, date_from=None, date_to=None, **kw):
        partner = request.env.user.partner_id
        today = fields.Date.context_today(request.env['res.partner'])

        try:
            date_to_d = datetime.strptime(date_to, '%Y-%m-%d').date() if date_to else today
        except ValueError:
            date_to_d = today
        try:
            date_from_d = datetime.strptime(date_from, '%Y-%m-%d').date() if date_from else date_to_d.replace(day=1)
        except ValueError:
            date_from_d = date_to_d.replace(day=1)

        Payment  = request.env['account.payment'].sudo()
        MoveLine = request.env['account.move.line'].sudo()

        # Đã thanh toán trong khoảng thời gian đã chọn — sắp xếp ngày giảm dần,
        # kèm id desc để các khoản cùng ngày cũng hiện khoản mới nhất trước.
        paid_payments = Payment.search([
            ('partner_id', '=', partner.id),
            ('payment_type', '=', 'inbound'),
            ('state', '=', 'posted'),
            ('date', '>=', date_from_d),
            ('date', '<=', date_to_d),
        ], order='date desc, id desc')
        paid_amount = sum(paid_payments.mapped('amount'))

        # Tổng tiền còn thiếu — số dư thực tế trên công nợ phải thu, tính đến
        # hiện tại (không giới hạn theo khoảng ngày lọc)
        residual_lines = MoveLine.search([
            ('partner_id', '=', partner.id),
            ('move_id.move_type', 'in', ('out_invoice', 'out_refund')),
            ('move_id.state', '=', 'posted'),
            ('account_id.account_type', '=', 'asset_receivable'),
            ('reconciled', '=', False),
        ])
        remaining_amount = sum(residual_lines.mapped('amount_residual'))

        # Tổng tiền công ty đang giữ — khách đã chuyển (payment Posted) nhưng
        # chưa được đối soát/phân bổ vào hoá đơn nào (vd. trả dư, trả trước
        # khi chưa có hoá đơn). Dùng field unallocated_amount của addon
        # payment_allocation, tính đến hiện tại.
        all_posted_payments = Payment.search([
            ('partner_id', '=', partner.id),
            ('payment_type', '=', 'inbound'),
            ('state', '=', 'posted'),
        ])
        held_amount = sum(all_posted_payments.mapped('unallocated_amount'))

        payments_result = [{
            'id':     p.id,
            'ref':    p.name,
            'date':   p.date.strftime('%d/%m/%Y') if p.date else '',
            'amount': p.amount,
            'method': p.journal_id.name or '',
            'memo':   p.ref or '',
            'held':   p.unallocated_amount,
        } for p in paid_payments]

        return {
            'date_from':        date_from_d.strftime('%Y-%m-%d'),
            'date_to':          date_to_d.strftime('%Y-%m-%d'),
            'paid_amount':      paid_amount,
            'remaining_amount': remaining_amount,
            'held_amount':      held_amount,
            'payments':         payments_result,
        }

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
            # Ưu tiên dùng variant_id (product.product); fallback lấy variant mặc định của template
            variant_id = item.get('variant_id')
            if variant_id:
                product = request.env['product.product'].sudo().browse(variant_id)
            else:
                tmpl = request.env['product.template'].sudo().browse(item['product_id'])
                product = tmpl.product_variant_id
            if not product.exists():
                continue

            price_unit = item.get('price_unit')
            if not price_unit:
                price_unit = pricelist._get_product_price(product, item['qty'], partner=partner)

            line_vals = {
                'product_id':      product.id,
                'product_uom_qty': item['qty'],
                'price_unit':      price_unit,
                'product_uom':     product.uom_id.id,
            }

            # Gán bao bì nếu người dùng đã chọn
            pkg_name = item.get('pkg_name')
            pkg_qty  = item.get('pkg_qty')
            if pkg_name and pkg_qty:
                packaging = request.env['product.packaging'].sudo().search([
                    ('product_id', '=', product.id),
                    ('name', '=', pkg_name),
                ], limit=1)
                if packaging:
                    line_vals['product_packaging_id']  = packaging.id
                    line_vals['product_packaging_qty'] = item['qty'] / pkg_qty

            lines.append((0, 0, line_vals))

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
            'success':   True,
            'order_id':  order.id,
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
                'bg': '#FEF3E8', 'tc': '#6F3C09',
                'letter': product.name[0].upper() if product.name else '?',
            }
        }
