/** @odoo-module **/

import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { registry } from "@web/core/registry";
import { patch } from "@web/core/utils/patch";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { useService } from "@web/core/utils/hooks";

// Import các component từ module này
import { PosScanButton } from "./scan_button/scan_button";
import { PosScanPopup } from "./scan_dialog/scan_dialog";

// Đăng ký popup vào registry
const popupRegistry = registry.category("pos_popups");
popupRegistry.add("PosScanPopup", PosScanPopup);

// Đăng ký nút vào ProductScreen
patch(ProductScreen.prototype, {
    setup() {
        super.setup();
        this.scanButton = PosScanButton;
    }
});

// Thêm nút vào danh sách các control buttons
ProductScreen.addControlButton({
    component: PosScanButton,
    condition: function() {
        return true;
    },
    position: ['before', 'PaymentButton'],
});

// Thêm các phương thức mới vào POS service
const posService = {
    name: "pos_scan_product",
    dependencies: ["pos"],
    start(env, { pos }) {
        // Mở rộng pos service với các phương thức mới
        const originalPosService = pos;

        // Thêm các phương thức mới
        pos.getProductByBarcode = async function(barcode) {
            try {
                // Truy cập POS Global State thông qua service
                const posModel = originalPosService.get();

                // Tìm sản phẩm theo barcode từ các sản phẩm đã được tải
                const product = posModel.db.get_product_by_barcode(barcode);
                if (product) {
                    return product;
                }

                // Nếu không tìm thấy, thử tải từ server
                const products = await this.env.services.rpc({
                    model: 'product.product',
                    method: 'search_read',
                    args: [[['barcode', '=', barcode], ['available_in_pos', '=', true]], ['id', 'display_name', 'barcode', 'lst_price', 'taxes_id']],
                    context: this.env.session.user_context,
                });

                if (products.length > 0) {
                    // Thêm sản phẩm vào cơ sở dữ liệu cục bộ
                    posModel._loadProductProduct([products[0]]);
                    return posModel.db.get_product_by_barcode(barcode);
                }

                return null;
            } catch (error) {
                this.env.services.popup.add(ErrorPopup, {
                    title: this.env._t('Không thể kết nối đến máy chủ'),
                    body: this.env._t('Vui lòng kiểm tra kết nối mạng và thử lại.'),
                });
                return null;
            }
        };

        pos.addProductByBarcode = async function(barcode) {
            const posModel = originalPosService.get();
            const product = await this.getProductByBarcode(barcode);

            if (!product) {
                this.env.services.popup.add(ErrorPopup, {
                    title: this.env._t('Không tìm thấy sản phẩm'),
                    body: this.env._t('Không tìm thấy sản phẩm với mã vạch: ') + barcode,
                });
                return false;
            }

            // Thêm sản phẩm vào đơn hàng hiện tại
            const order = posModel.get_order();
            if (order) {
                order.add_product(product);
                return true;
            }
            return false;
        };

        return pos;
    }
};

// Đăng ký service
registry.category("services").add(posService.name, posService);