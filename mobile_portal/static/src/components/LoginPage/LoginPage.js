/** @odoo-module **/
import { Component, useState } from "@odoo/owl";

export class LoginPage extends Component {
    static template = "mobile_portal.LoginPage";
    static props = {
        onLoginSuccess: Function,
        onGoRegister:   Function,
    };

    setup() {
        // Field names match what LoginPage.xml binds: state.email, state.password, state.showPass
        this.state = useState({
            email:    "",
            password: "",
            showPass: false,
            error:    "",
            loading:  false,
        });
    }

    // Arrow functions — all called from template
    onEmailInput   = (ev) => { this.state.email    = ev.target.value; this.state.error = ""; };
    onPassInput    = (ev) => { this.state.password  = ev.target.value; this.state.error = ""; };
    toggleShowPass = ()   => { this.state.showPass  = !this.state.showPass; };

    onSubmit = async () => {
        const { email, password } = this.state;
        if (!email.trim() || !password) {
            this.state.error = "Vui lòng nhập email và mật khẩu";
            return;
        }
        this.state.loading = true;
        this.state.error   = "";
        try {
            const res = await this.env.rpc("/my/shop/api/login", {
                login:    email.trim(),
                password: password,
            });
            if (res.error) {
                this.state.error = res.error;
                return;
            }
            this.props.onLoginSuccess({
                partnerName: res.partner_name || email.split("@")[0],
                partnerId:   res.partner_id   || 0,
            });
        } catch {
            this.state.error = "Không thể kết nối, vui lòng thử lại";
        } finally {
            this.state.loading = false;
        }
    };

    onKeydown = (ev) => { if (ev.key === "Enter") this.onSubmit(); };
}
