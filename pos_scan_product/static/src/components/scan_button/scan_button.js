/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { useService } from "@web/core/utils/hooks";
import { Component } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { PosScanPopup } from "../scan_dialog/scan_dialog";

export class PosScanButton extends Component {
    static template = "pos_scan_product.PosScanButton";

    setup() {
        this.pos = usePos();
        this.popup = useService("popup");
    }

    async onClick() {
        const { confirmed } = await this.popup.add(PosScanPopup);

        if (confirmed) {
            // Xử lý khi người dùng ấn nút "Đóng" với thông báo thành công
            // Logic đã được xử lý trong PosScanPopup
        }
    }
}