/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { LoginScreen } from "@pos_hr/app/login_screen/login_screen";

/**
 * POS Direct Login — Patch LoginScreen
 *
 * Sau khi user đăng nhập qua /pos-login bằng PIN nhân viên,
 * controller lưu employee_id vào HTTP session.
 *
 * Patch này:
 *   1. Gọi RPC lấy employee_id (server tự xóa sau khi đọc)
 *   2. Tìm employee trong pos.employees (array đúng của pos_hr)
 *   3. Set cashier trực tiếp — không cần check PIN lại (đã verify server-side)
 *   4. Gọi this.back() để đóng LoginScreen và vào POS ngay
 */
patch(LoginScreen.prototype, {
    async setup() {
        super.setup(...arguments);
        // Chạy async sau khi component mount xong
        this._autoLoginFromDirectLogin();
    },

    async _autoLoginFromDirectLogin() {
        try {
            const result = await this.env.services.orm.call(
                "pos.config",
                "get_direct_login_employee",
                [],
                {}
            );

            if (!result || !result.employee_id) {
                return; // Không phải direct login → hiển thị LoginScreen bình thường
            }

            const employeeId = result.employee_id;

            // pos.employees là array được dùng trong pos_hr (xem useCashierSelector)
            const employee = this.pos.employees.find((e) => e.id === employeeId);

            if (!employee) {
                console.warn(
                    "[POS Direct Login] Employee id=%d không có trong pos.employees",
                    employeeId
                );
                return;
            }

            // Set cashier — bỏ qua check PIN vì đã xác thực server-side
            this.pos.set_cashier(employee);
            console.info("[POS Direct Login] Auto-selected cashier:", employee.name);

            // Đóng LoginScreen: đúng theo logic của LoginScreen.back()
            this.back();

        } catch (e) {
            console.warn("[POS Direct Login] _autoLoginFromDirectLogin error:", e);
        }
    },
});
