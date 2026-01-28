/** @odoo-module **/

import { Component } from "@odoo/owl";

export class DeliveryDisplayDriversPanel extends Component {
    static template = "delivery_display.DeliveryDisplayDriversPanel";
    static props = {
        drivers: { type: Object },
        setSessionDriver: { type: Function },
        popupAddDriver: { type: Function },
        logout: { type: Function },
    };
}
