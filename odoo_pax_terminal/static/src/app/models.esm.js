import { PaymentPax } from "@odoo_pax_terminal/app/payment_pax";
import { register_payment_method } from "@point_of_sale/app/store/pos_store";
//import { registry } from "@web/core/registry";

register_payment_method("pax", PaymentPax);

//// Đăng ký model pax.terminal để POS có thể truy cập
//registry.category("pos_models").add("pax.terminal", {
//    modelName: "pax.terminal",
//    fields: [
//        "name",
//        "ip_address",
//        "port",
//        "active",
//        "company_id",
//        "timeout",
//        "demo_mode",
//        "demo_success_rate",
//        "default_clerk_id",
//        "default_reference_prefix",
//    ],
//    loaded: async (self, terminals) => {
//        // Có thể xử lý gì đó nếu cần
//        return terminals;
//    },
//});
//
//// Đăng ký field pax_terminal_id cho model pos.payment.method
//registry.category("pos_models").add("pos.payment.method", {
//    fields: [
//        "name",
//        "use_payment_terminal",
//        "pax_terminal_id",  // Thêm field này
//        "pax_transaction_type",
//        "pax_capture_signature",
//        "pax_clerk_id",
//    ],
//});
