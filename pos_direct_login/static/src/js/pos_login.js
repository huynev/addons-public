(function () {
    'use strict';

    document.addEventListener('DOMContentLoaded', function () {

        // ── Tab switching ──────────────────────────────────────────
        const tabAccount   = document.getElementById('tab-account');
        const tabPin       = document.getElementById('tab-pin');
        const panelAccount = document.getElementById('panel-account');
        const panelPin     = document.getElementById('panel-pin');

        function activateTab(tab) {
            if (tab === 'pin') {
                tabPin.classList.add('active');
                tabAccount.classList.remove('active');
                panelPin.style.display = 'block';
                panelAccount.style.display = 'none';
            } else {
                tabAccount.classList.add('active');
                tabPin.classList.remove('active');
                panelAccount.style.display = 'block';
                panelPin.style.display = 'none';
            }
        }

        tabAccount && tabAccount.addEventListener('click', () => activateTab('account'));
        tabPin     && tabPin.addEventListener('click',     () => activateTab('pin'));

        const urlParams = new URLSearchParams(window.location.search);
        if (urlParams.get('tab') === 'pin') activateTab('pin');

        // ── Load POS configs ───────────────────────────────────────
        function jsonRpc(url, params) {
            return fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ jsonrpc: '2.0', method: 'call', params: params || {} }),
            }).then(r => r.json()).then(d => d.result || {});
        }

        let allConfigs = [];

        function loadConfigs() {
            jsonRpc('/pos-login/get-configs').then(function (result) {
                allConfigs = result.configs || [];

                // ── Account tab: chỉ hiện nếu > 1 config ──
                const selAccount = document.getElementById('pos_config_id_account');
                const grpAccount = document.getElementById('config-group-account');
                if (allConfigs.length > 1 && selAccount) {
                    selAccount.innerHTML = '<option value="">-- Tự động chọn --</option>';
                    allConfigs.forEach(function (c) {
                        const opt = document.createElement('option');
                        opt.value = c.id;
                        opt.textContent = c.name;
                        selAccount.appendChild(opt);
                    });
                    grpAccount && (grpAccount.style.display = 'block');
                }

                // ── PIN tab: luôn hiện config selector ──
                const selPin = document.getElementById('pos_config_id_pin');
                const grpPin = document.getElementById('config-group-pin');
                if (selPin) {
                    if (allConfigs.length === 0) {
                        selPin.innerHTML = '<option value="">Không có cửa hàng nào</option>';
                    } else if (allConfigs.length === 1) {
                        // Chỉ 1 config → ẩn dropdown, tự động chọn ngầm
                        selPin.innerHTML = '<option value="' + allConfigs[0].id + '">' + allConfigs[0].name + '</option>';
                        grpPin && (grpPin.style.display = 'none');
                        // Load nhân viên ngay
                        loadEmployees(allConfigs[0].id);
                    } else {
                        selPin.innerHTML = '<option value="">-- Chọn cửa hàng --</option>';
                        allConfigs.forEach(function (c) {
                            const opt = document.createElement('option');
                            opt.value = c.id;
                            opt.textContent = c.name;
                            selPin.appendChild(opt);
                        });
                        grpPin && (grpPin.style.display = 'block');
                    }
                }

                // Nếu URL có param config (sau khi lỗi redirect về), restore lại
                const configParam = urlParams.get('config');
                if (configParam && selPin) {
                    selPin.value = configParam;
                    if (configParam) loadEmployees(parseInt(configParam));
                }
            });
        }

        loadConfigs();

        // ── Load employees cho config được chọn ───────────────────
        const selConfigPin = document.getElementById('pos_config_id_pin');
        selConfigPin && selConfigPin.addEventListener('change', function () {
            resetPin();
            if (this.value) {
                loadEmployees(parseInt(this.value));
            } else {
                setEmployeePlaceholder('-- Chọn cửa hàng trước --');
            }
        });

        function loadEmployees(configId) {
            const sel = document.getElementById('employee_id');
            if (!sel) return;

            sel.innerHTML = '<option value="">Đang tải nhân viên...</option>';
            sel.disabled = true;

            jsonRpc('/pos-login/get-employees', { pos_config_id: configId })
                .then(function (result) {
                    sel.disabled = false;
                    const employees = result.employees || [];

                    if (result.require_config) {
                        setEmployeePlaceholder('-- Chọn cửa hàng trước --');
                        return;
                    }
                    if (result.no_employees) {
                        setEmployeePlaceholder('Cửa hàng chưa có nhân viên nào');
                        return;
                    }
                    if (!employees.length) {
                        setEmployeePlaceholder('Không có nhân viên nào có PIN & tài khoản');
                        return;
                    }

                    sel.innerHTML = '<option value="">-- Chọn nhân viên --</option>';
                    employees.forEach(function (e) {
                        const opt = document.createElement('option');
                        opt.value = e.id;
                        opt.textContent = e.name;
                        sel.appendChild(opt);
                    });
                })
                .catch(function () {
                    sel.disabled = false;
                    setEmployeePlaceholder('Lỗi tải danh sách');
                });
        }

        function setEmployeePlaceholder(msg) {
            const sel = document.getElementById('employee_id');
            if (sel) sel.innerHTML = '<option value="">' + msg + '</option>';
        }

        // ── PIN numpad ─────────────────────────────────────────────
        let pinValue = '';
        const MAX_PIN  = 6;
        const pinInput = document.getElementById('pin-value');
        const submitBtn = document.getElementById('pin-submit-btn');
        const dots = document.querySelectorAll('.pin-dot');

        function updateDots() {
            dots.forEach(function (dot, i) {
                dot.classList.toggle('filled', i < pinValue.length);
            });
            const selEmp = document.getElementById('employee_id');
            const selCfg = document.getElementById('pos_config_id_pin');
            const hasEmployee = selEmp && selEmp.value;
            const hasConfig   = selCfg && selCfg.value;
            if (submitBtn) {
                submitBtn.disabled = !(hasEmployee && hasConfig && pinValue.length >= 4);
            }
            if (pinInput) pinInput.value = pinValue;
        }

        function resetPin() {
            pinValue = '';
            updateDots();
        }

        document.querySelectorAll('.numpad-key[data-val]').forEach(function (btn) {
            btn.addEventListener('click', function () {
                if (pinValue.length >= MAX_PIN) return;
                pinValue += this.dataset.val;
                updateDots();
                if (pinValue.length === MAX_PIN) {
                    const emp = document.getElementById('employee_id');
                    const cfg = document.getElementById('pos_config_id_pin');
                    if (emp && emp.value && cfg && cfg.value) {
                        setTimeout(submitPinForm, 200);
                    }
                }
            });
        });

        document.getElementById('numpad-del') &&
            document.getElementById('numpad-del').addEventListener('click', function () {
                pinValue = pinValue.slice(0, -1);
                updateDots();
            });

        document.getElementById('numpad-clear') &&
            document.getElementById('numpad-clear').addEventListener('click', resetPin);

        const selEmp = document.getElementById('employee_id');
        selEmp && selEmp.addEventListener('change', function () {
            resetPin();
            updateDots();
        });

        function submitPinForm() {
            const form = document.getElementById('form-pin');
            if (!form) return;
            if (submitBtn) { submitBtn.classList.add('loading'); submitBtn.disabled = true; }
            form.submit();
        }

        submitBtn && submitBtn.addEventListener('click', submitPinForm);

        // Keyboard support
        document.addEventListener('keydown', function (e) {
            if (panelPin && panelPin.style.display !== 'none') {
                if (/^\d$/.test(e.key) && pinValue.length < MAX_PIN) {
                    pinValue += e.key;
                    updateDots();
                } else if (e.key === 'Backspace') {
                    pinValue = pinValue.slice(0, -1);
                    updateDots();
                }
            }
        });

        updateDots();

        // ── Account form ───────────────────────────────────────────
        const formAccount = document.getElementById('form-account');
        formAccount && formAccount.addEventListener('submit', function () {
            const btn = this.querySelector('.pos-login-btn');
            if (btn) { btn.classList.add('loading'); btn.disabled = true; }
        });

        // ── Toggle password ────────────────────────────────────────
        const toggleBtn   = document.querySelector('.toggle-password');
        const passwordInp = document.getElementById('password');
        if (toggleBtn && passwordInp) {
            toggleBtn.addEventListener('click', function () {
                const isPass = passwordInp.type === 'password';
                passwordInp.type = isPass ? 'text' : 'password';
                this.querySelector('.eye-open').style.display  = isPass ? 'none'  : 'block';
                this.querySelector('.eye-closed').style.display = isPass ? 'block' : 'none';
            });
        }

        // ── Auto-focus ─────────────────────────────────────────────
        const loginInp = document.getElementById('login');
        if (loginInp && panelAccount.style.display !== 'none') loginInp.focus();

        // ── Particles ──────────────────────────────────────────────
        initParticles();
    });

    function initParticles() {
        const canvas = document.getElementById('pos-particles');
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        let W = canvas.width  = window.innerWidth;
        let H = canvas.height = window.innerHeight;
        window.addEventListener('resize', function () {
            W = canvas.width  = window.innerWidth;
            H = canvas.height = window.innerHeight;
        });
        const pts = Array.from({ length: 35 }, function () {
            return {
                x: Math.random() * W, y: Math.random() * H,
                r: Math.random() * 2 + .5,
                dx: (Math.random() - .5) * .4, dy: (Math.random() - .5) * .4,
                a: Math.random() * .3 + .08,
            };
        });
        (function loop() {
            ctx.clearRect(0, 0, W, H);
            pts.forEach(function (p) {
                ctx.beginPath();
                ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
                ctx.fillStyle = 'rgba(102,126,234,' + p.a + ')';
                ctx.fill();
                p.x += p.dx; p.y += p.dy;
                if (p.x < 0 || p.x > W) p.dx *= -1;
                if (p.y < 0 || p.y > H) p.dy *= -1;
            });
            requestAnimationFrame(loop);
        })();
    }
})();
