/** @odoo-module **/
import { Component } from "@odoo/owl";
import { formatVND } from "../../utils";

export class Cart extends Component {
    static template = "mobile_portal.Cart";
    static props = {
        items:       Array,
        onUpdateQty: Function,
        onPlace:     Function,
        isPlacing:   Boolean,
    };

    // Getters — OWL accesses these as properties (ctx.total), no this-loss
    get total()          { return this.props.items.reduce((s, i) => s + i.price * i.qty, 0); }
    get totalFormatted() { return formatVND(this.total); }
    get totalQty()       { return this.props.items.reduce((s, i) => s + i.qty, 0); }
    get canOrder()       { return this.props.items.length > 0 && !this.props.isPlacing; }

    // Arrow function — called from template with arg
    lineTotal = (item) => formatVND(item.price * item.qty);
}
