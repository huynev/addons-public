# -*- coding: utf-8 -*-
import logging
from odoo import http
from odoo.http import request
from odoo.exceptions import AccessDenied

_logger = logging.getLogger(__name__)


class PosDirectLogin(http.Controller):

    # ─────────────────────────────────────────────────────────────
    # Pages
    # ─────────────────────────────────────────────────────────────

    @http.route('/pos-login', type='http', auth='none', website=False, sitemap=False)
    def pos_login_page(self, **kw):
        if request.session.uid:
            uid = request.session.uid
            env_user = request.env(user=uid)
            allowed_configs = self._get_allowed_configs(env_user)
            if not allowed_configs:
                request.session.logout(keep_db=True)
                return request.redirect('/pos-login?error=no_pos')
            return self._redirect_to_pos(env_user, allowed_configs)

        error_messages = {
            'wrong_login':    'Tên đăng nhập hoặc mật khẩu không đúng.',
            'inactive':       'Tài khoản này đã bị vô hiệu hóa.',
            'no_pos':         'Bạn không được phép mở bất kỳ cửa hàng POS nào.',
            'no_access':      'Bạn không có quyền truy cập Point of Sale.',
            'config_denied':  'Bạn không có quyền mở cửa hàng POS này.',
            'config_required': 'Vui lòng chọn cửa hàng POS trước.',
            'wrong_pin':      'Mã PIN không đúng. Vui lòng thử lại.',
            'no_employee':    'Không tìm thấy nhân viên. Liên hệ quản trị viên.',
            'pin_no_user':    'Nhân viên này chưa được liên kết với tài khoản Odoo.',
        }
        return request.render('pos_direct_login.pos_login_template', {
            'error': error_messages.get(kw.get('error', ''), ''),
            'tab':   kw.get('tab', 'account'),
        })

    # ─────────────────────────────────────────────────────────────
    # Auth: tài khoản Odoo
    # ─────────────────────────────────────────────────────────────

    @http.route(
        '/pos-login/authenticate',
        type='http', auth='none', methods=['POST'],
        csrf=True, website=False, sitemap=False,
    )
    def pos_login_authenticate(self, **kw):
        login         = kw.get('login', '').strip()
        password      = kw.get('password', '').strip()
        pos_config_id = kw.get('pos_config_id', '').strip()

        if not login or not password:
            return request.redirect('/pos-login?error=wrong_login')

        try:
            uid = request.session.authenticate(request.db, login, password)
            if not uid:
                return request.redirect('/pos-login?error=wrong_login')
        except AccessDenied:
            return request.redirect('/pos-login?error=wrong_login')
        except Exception:
            _logger.exception("POS Login: lỗi authenticate '%s'", login)
            return request.redirect('/pos-login?error=wrong_login')

        env_user = request.env(user=uid)
        allowed_configs = self._get_allowed_configs(env_user)
        if not allowed_configs:
            request.session.logout(keep_db=True)
            return request.redirect('/pos-login?error=no_pos')

        if pos_config_id:
            try:
                cid = int(pos_config_id)
            except (ValueError, TypeError):
                cid = None
            if cid and cid in allowed_configs.ids:
                return self._pos_url_redirect(allowed_configs.filtered(lambda c: c.id == cid))
            else:
                request.session.logout(keep_db=True)
                return request.redirect('/pos-login?error=config_denied')

        return self._redirect_to_pos(env_user, allowed_configs)

    # ─────────────────────────────────────────────────────────────
    # Auth: PIN nhân viên
    # ─────────────────────────────────────────────────────────────

    @http.route(
        '/pos-login/authenticate-pin',
        type='http', auth='none', methods=['POST'],
        csrf=True, website=False, sitemap=False,
    )
    def pos_login_authenticate_pin(self, **kw):
        employee_id   = kw.get('employee_id', '').strip()
        pin           = kw.get('pin', '').strip()
        pos_config_id = kw.get('pos_config_id', '').strip()

        # Bắt buộc phải chọn cửa hàng
        if not pos_config_id:
            return request.redirect('/pos-login?error=config_required&tab=pin')

        if not employee_id or not pin:
            return request.redirect(
                '/pos-login?error=wrong_pin&tab=pin&config=%s' % pos_config_id
            )

        env_sudo = request.env(user=request.env.ref('base.user_admin').id)

        try:
            eid = int(employee_id)
            cid = int(pos_config_id)
        except (ValueError, TypeError):
            return request.redirect('/pos-login?error=no_employee&tab=pin')

        # Tìm config
        config = env_sudo['pos.config'].browse(cid)
        if not config.exists():
            return request.redirect('/pos-login?error=config_denied&tab=pin')

        # Tìm employee
        employee = env_sudo['hr.employee'].browse(eid)
        if not employee.exists():
            return request.redirect(
                '/pos-login?error=no_employee&tab=pin&config=%s' % pos_config_id
            )

        # Kiểm tra nhân viên có thuộc đúng cửa hàng này không
        if not self._employee_allowed_in_config(config, employee):
            return request.redirect(
                '/pos-login?error=config_denied&tab=pin&config=%s' % pos_config_id
            )

        # Xác minh PIN
        if not employee.pin or employee.pin != pin:
            return request.redirect(
                '/pos-login?error=wrong_pin&tab=pin&config=%s' % pos_config_id
            )

        # Đọc user liên kết (sudo để bypass ir.rule của res.users)
        employee_sudo = employee.sudo()
        if not employee_sudo.user_id:
            return request.redirect(
                '/pos-login?error=pin_no_user&tab=pin&config=%s' % pos_config_id
            )

        uid       = employee_sudo.user_id.id
        user_sudo = employee_sudo.user_id.sudo()

        # Tạo session Odoo
        request.session.uid           = uid
        request.session.login         = user_sudo.login
        request.session.session_token = user_sudo._compute_session_token(
            request.session.sid
        )

        # Lưu employee_id vào HTTP session để POS patch tự động chọn cashier
        # (đọc 1 lần rồi xóa trong pos.config.get_direct_login_employee)
        request.session["pos_direct_login_employee_id"] = employee.id

        # Tạo pos.session trước nếu chưa có → POS mở thẳng, không hỏi lại
        env_user = request.env(user=uid)
        self._ensure_pos_session_opened(env_user, config)

        # Redirect thẳng vào đúng cửa hàng đã chọn
        return self._pos_url_redirect(config)

    # ─────────────────────────────────────────────────────────────
    # Authenticated routes
    # ─────────────────────────────────────────────────────────────

    @http.route('/pos-login/logout', type='http', auth='user', website=False, sitemap=False)
    def pos_logout(self, **kw):
        request.session.logout(keep_db=True)
        return request.redirect('/pos-login')

    # ─────────────────────────────────────────────────────────────
    # JSON APIs
    # ─────────────────────────────────────────────────────────────

    @http.route('/pos-login/get-configs', type='json', auth='none', methods=['POST'])
    def get_pos_configs(self, **kw):
        """Danh sách tất cả POS config đang active."""
        try:
            env_sudo = request.env(user=request.env.ref('base.user_admin').id)
            configs  = env_sudo['pos.config'].search([('active', '=', True)], order='name')
            return {'configs': [{'id': c.id, 'name': c.name} for c in configs]}
        except Exception:
            _logger.exception("get_pos_configs error")
            return {'configs': []}

    @http.route('/pos-login/get-employees', type='json', auth='none', methods=['POST'])
    def get_pos_employees(self, **kw):
        """Nhân viên được phép đăng nhập vào một cửa hàng POS cụ thể.

        Luôn yêu cầu pos_config_id. Trả về rỗng nếu không truyền.
        Lọc từ basic_employee_ids | advanced_employee_ids của config đó,
        chỉ giữ nhân viên: active + có PIN + có user Odoo liên kết.
        """
        pos_config_id = kw.get('pos_config_id')
        if not pos_config_id:
            return {'employees': [], 'require_config': True}

        try:
            env_sudo = request.env(user=request.env.ref('base.user_admin').id)
            config   = env_sudo['pos.config'].browse(int(pos_config_id))
            if not config.exists():
                return {'employees': []}

            employees = self._get_config_employees(config)

            # Chỉ lấy nhân viên trong config, không fallback
            # Nếu config không có nhân viên nào → trả về rỗng
            if not employees:
                return {'employees': [], 'no_employees': True}

            # Lọc: active + PIN + user Odoo liên kết (sudo để đọc user_id)
            employees = employees.filtered(
                lambda e: e.active and e.pin and e.sudo().user_id
            )

            return {
                'employees': [
                    {'id': e.id, 'name': e.name}
                    for e in employees.sorted('name')
                ]
            }
        except Exception:
            _logger.exception("get_pos_employees error")
            return {'employees': []}

    # ─────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────

    def _get_allowed_configs(self, env_user):
        """POS config user này có quyền truy cập (record rules tự lọc)."""
        return env_user['pos.config'].search([('active', '=', True)], order='id')

    def _get_config_employees(self, config):
        """Union basic_employee_ids + advanced_employee_ids cua config.

        Dung config._fields de kiem tra field ton tai tren model,
        chinh xac hon hasattr khi field chua duoc compute/load.
        """
        model_fields = config._fields
        empty        = config.env['hr.employee']
        basic    = config.basic_employee_ids    if 'basic_employee_ids'    in model_fields else empty
        advanced = config.advanced_employee_ids if 'advanced_employee_ids' in model_fields else empty
        combined = basic | advanced
        _logger.debug(
            "POS config '%s' (id=%d): basic=%d, advanced=%d, combined=%d",
            config.name, config.id, len(basic), len(advanced), len(combined),
        )
        return combined

    def _employee_allowed_in_config(self, config, employee):
        """True nếu nhân viên nằm trong basic_employee_ids | advanced_employee_ids.
        Nếu config không có nhân viên nào → không ai được vào.
        """
        allowed = self._get_config_employees(config)
        if not allowed:
            return False
        return employee.id in allowed.ids

    def _ensure_pos_session_opened(self, env_user, pos_config):
        """Đảm bảo pos.session đang ở trạng thái opened trước khi redirect.

        - Nếu đã có session opened → dùng lại, không tạo mới.
        - Nếu chưa → tạo mới (Odoo tự chuyển sang 'opening_control' rồi 'opened').
        Dùng sudo để đảm bảo có quyền tạo session.
        """
        try:
            existing = self._find_open_session(env_user, pos_config)
            if existing:
                return existing

            # Tạo session mới bằng sudo để tránh lỗi quyền
            new_session = env_user.sudo()['pos.session'].create({
                'config_id': pos_config.id,
            })
            _logger.info(
                "POS Direct Login: tạo pos.session id=%d cho config '%s'",
                new_session.id, pos_config.name,
            )
            return new_session
        except Exception:
            _logger.warning(
                "POS Direct Login: không thể tạo pos.session cho config '%s', "
                "POS sẽ tự xử lý khi load.",
                pos_config.name, exc_info=True,
            )
            return None

    def _find_open_session(self, env_user, pos_config):
        return env_user['pos.session'].search([
            ('config_id', '=', pos_config.id),
            ('state',     '=', 'opened'),
            ('rescue',    '=', False),
        ], limit=1, order='id desc')

    def _pos_url(self, pos_config):
        company_id = pos_config.company_id.id or request.env.company.id
        return '/pos/ui?config_id=%d#cids=%d' % (pos_config.id, company_id)

    def _pos_url_redirect(self, pos_config):
        return request.redirect(self._pos_url(pos_config))

    def _redirect_to_pos(self, env_user, allowed_configs):
        for cfg in allowed_configs:
            if self._find_open_session(env_user, cfg):
                return self._pos_url_redirect(cfg)
        first_config = allowed_configs[:1]
        if first_config:
            return self._pos_url_redirect(first_config)
        return request.redirect('/pos-login?error=no_pos')
