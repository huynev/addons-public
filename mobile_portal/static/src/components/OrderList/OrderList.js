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
    // cls dùng chung style oval .psbadge (giống DebtView) — bg + màu chữ theo trạng thái
    payLabel      = (order) => {
        if (order.status === 'cancel') return { text: 'Đã hủy',          cls: 'ps-na' };
        if (order.paid >= order.total) return { text: 'Đã TT đủ',        cls: 'ps-paid' };
        if (order.paid > 0)            return { text: `TT ${pct(order.paid, order.total)}%`, cls: 'ps-partial' };
        return                                { text: 'Chưa thanh toán', cls: 'ps-unpaid' };
    };
    orderSummary   = (order) => (order.lines || []).slice(0, 3).map(l => `${l.name} × ${l.qty}`).join(', ');
    totalFormatted = (order) => formatVND(order.total || 0);
}
