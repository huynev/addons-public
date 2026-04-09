/** @odoo-module **/
import { Component } from "@odoo/owl";
import { formatVND, pct } from "../../utils";

export class DebtView extends Component {
    static template = "mobile_portal.DebtView";
    static props = {
        orders:       Array,
        payments:     Array,
        isLoading:    Boolean,
        onOpenDetail: Function,
    };

    // Getters
    get activeOrders()   { return this.props.orders.filter(o => o.status !== 'cancel'); }
    get totalDebt()      { return this.activeOrders.reduce((s, o) => s + (o.total || 0), 0); }
    get totalPaid()      { return this.activeOrders.reduce((s, o) => s + (o.paid  || 0), 0); }
    get totalRemain()    { return this.totalDebt - this.totalPaid; }
    get totalDebtK()     { return Math.round(this.totalDebt   / 1000); }
    get totalPaidK()     { return Math.round(this.totalPaid   / 1000); }
    get totalRemainK()   { return Math.round(this.totalRemain / 1000); }
    get payPct()         { return pct(this.totalPaid, this.totalDebt); }
    get totalPaidFmt()   { return formatVND(this.totalPaid); }
    get totalRemainFmt() { return formatVND(this.totalRemain); }

    // Arrow functions — called from template with arg
    orderPayInfo  = (order) => {
        if (order.status === 'cancel') return { cls: 'ps-na',      label: 'N/A',       color: '#aaa9a2' };
        if (order.paid >= order.total) return { cls: 'ps-paid',    label: 'Đã TT đủ',  color: '#0F6E56' };
        if (order.paid > 0)            return { cls: 'ps-partial', label: 'TT 1 phần', color: '#BA7517' };
        return                                { cls: 'ps-unpaid',  label: 'Chưa TT',   color: '#E24B4A' };
    };
    orderBarPct   = (order) => pct(order.paid || 0, order.total || 0);
    orderTotalFmt  = (order) => formatVND(order.total || 0);
    orderPaidFmt   = (order) => formatVND(order.paid  || 0);
    orderRemainFmt = (order) => formatVND((order.total || 0) - (order.paid || 0));
    payAmtFmt      = (p)     => formatVND(p.amount || 0);
}
