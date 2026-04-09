/** @odoo-module **/
import { Component } from "@odoo/owl";

export class BottomNav extends Component {
    static template = "mobile_portal.BottomNav";
    static props = {
        currentTab: String,
        cartCount:  Number,
        onSwitch:   Function,
    };

    // Arrow functions — called from template expressions → must capture `this`
    isActive  = (tabId) => this.props.currentTab === tabId;
    onTabClick = (tabId) => this.props.onSwitch(tabId);
}
