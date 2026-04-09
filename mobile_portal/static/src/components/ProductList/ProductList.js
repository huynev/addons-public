/** @odoo-module **/
import { Component } from "@odoo/owl";

export class ProductList extends Component {
    static template = "mobile_portal.ProductList";
    static props = {
        products:    Array,
        categories:  Array,
        filterCat:   String,
        filterQ:     String,
        cart:        Object,
        onOpenModal: Function,
        onFilterCat: Function,
        onFilterQ:   Function,
    };

    cartQty      = (productId) => { const i = this.props.cart[productId]; return i ? i.qty : 0; };
    onSearchInput = (ev) => this.props.onFilterQ(ev.target.value);
    onPillClick   = (cat) => this.props.onFilterCat(cat);
    onCardClick   = (product) => this.props.onOpenModal(product);
}
