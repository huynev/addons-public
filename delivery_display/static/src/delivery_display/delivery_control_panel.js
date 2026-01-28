/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { Component } from "@odoo/owl";

export class DeliveryControlPanelButtons extends Component {
    static template = "delivery_display.DeliveryControlPanelButtons";
    static props = {
        activeFilter: [Boolean, String, Number],
        deliveryCount: Number,
        selectFilter: Function,
        toggleFilter: Function,
        warehouses: Array,
        routes: Array,
        deliveries: Array,
        relevantCount: Number,
        myDeliveries: Array,
        hideNewFilterButton: Boolean,
    };

    get filterButtons() {
        const filterButtons = {};
        let deliveryCount = this.props.deliveryCount;
        let warehouseCount = {};
        // Initialize warehouse buttons
        for (const { id, display_name } of this.props.warehouses) {
            warehouseCount[`wh_${id}`] = { count: 0, name: display_name, type: 'warehouse' };
        }

        return [
            ["0", { count: deliveryCount, name: _t("All Deliveries"), type: 'all' }],
//            ...Object.entries(warehouseCount),
        ];
    }
}
