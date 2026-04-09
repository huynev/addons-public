/** @odoo-module **/
import { Component, useState } from "@odoo/owl";

export class RegisterPage extends Component {
    static template = "mobile_portal.RegisterPage";
    static props = {
        onRegisterSuccess: Function,
        onGoLogin:         Function,
    };

    setup() {
        this.state = useState({
            name: "", email: "", password: "", confirm: "", phone: "",
            showPass: false, showConfirm: false,
            error: "", loading: false,
        });
    }

    onInput = (field) => (ev) => {
        this.state[field] = ev.target.value;
        this.state.error  = "";
    };

    get passwordMismatch() {
        return this.state.confirm.length > 0 && this.state.password !== this.state.confirm;
    }
    get canSubmit() {
        return this.state.name.trim() && this.state.email.trim() &&
               this.state.password.length >= 6 && !this.passwordMismatch;
    }

    onSubmit = async () => {
        if (!this.canSubmit || this.state.loading) return;
        this.state.loading = true;
        this.state.error   = "";
        try {
            const res = await this.env.rpc("/my/shop/api/register", {
                name:     this.state.name.trim(),
                email:    this.state.email.trim(),
                password: this.state.password,
                phone:    this.state.phone.trim(),
            });
            if (res.error) { this.state.error = res.error; return; }

            // Auto-login after register
            const loginRes = await this.env.rpc("/my/shop/api/login", {
                login:    this.state.email.trim(),
                password: this.state.password,
            });
            this.props.onRegisterSuccess({
                partnerName: loginRes.partner_name || this.state.name,
                partnerId:   loginRes.partner_id   || 0,
            });
        } catch {
            this.state.error = "Đăng ký thất bại, vui lòng thử lại";
        } finally {
            this.state.loading = false;
        }
    };
}
