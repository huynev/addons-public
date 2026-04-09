/** @odoo-module **/
import { Component, useState } from "@odoo/owl";

export class ProductModal extends Component {
    static template = "mobile_portal.ProductModal";
    static props = {
        product:    Object,
        onAdd:      Function,
        onClose:    Function,
        initialQty: { type: Number, optional: true },
    };
    static defaultProps = { initialQty: 1 };

    setup() {
        this.state = useState({ qty: this.props.initialQty || 1 });
    }

    decrement      = () => { if (this.state.qty > 1) this.state.qty--; };
    increment      = () => { this.state.qty++; };
    onAddClick     = () => this.props.onAdd(this.props.product, this.state.qty);
    onOverlayClick = (ev) => { if (ev.target === ev.currentTarget) this.props.onClose(); };
}
