/** @odoo-module **/
import { Component } from "@odoo/owl";
import { formatVND, pct } from "../../utils";

export class OrderList extends Component {
    static template = "mobile_portal.OrderList";
    static props = {
        orders:       Array,
        isLoading:    Boolean,
        onOpenDetail: Function,
    };

    // Arrow functions — called from template with arg
    payLabel      = (order) => {
        if (order.status === 'cancel') return { text: 'Đã hủy',         color: '#aaa9a2' };
        if (order.paid >= order.total) return { text: 'Đã TT đủ',       color: '#27500A' };
        if (order.paid > 0)            return { text: `TT ${pct(order.paid, order.total)}%`, color: '#854F0B' };
        return                                { text: 'Chưa thanh toán', color: '#A32D2D' };
    };
    orderSummary  = (order) => (order.lines || []).slice(0, 3).map(l => `${l.name} × ${l.qty}`).join(', ');
    totalFormatted = (order) => formatVND(order.total || 0);
    totalLines    = (order) => (order.lines || []).reduce((s, l) => s + l.qty, 0);
}
