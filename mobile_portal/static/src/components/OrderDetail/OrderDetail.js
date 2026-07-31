/** @odoo-module **/
import { Component } from "@odoo/owl";
import { formatVND, pct } from "../../utils";

export class OrderDetail extends Component {
    static template = "mobile_portal.OrderDetail";
    static props = {
        order:   { type: Object, optional: true },
        onClose: Function,
    };

    static TIMELINE     = ['Tạo đơn', 'Xác nhận', 'Giao hàng', 'Hoàn thành'];
    static TIMELINE_MAP = { draft: 0, confirmed: 1, delivery: 2, done: 3 };

    // Getters — safe (property access)
    get isVisible()  { return !!this.props.order; }
    get order()      { return this.props.order || {}; }
    get isCancelled(){ return this.order.status === 'cancel'; }
    get timeline()   { return OrderDetail.TIMELINE; }
    get timelineIndex() { return OrderDetail.TIMELINE_MAP[this.order.status] || 0; }

    get linesWithTotals() {
        return (this.order.lines || []).map(l => ({
            ...l,
            lineTotal:      formatVND(l.price * l.qty),
            priceFormatted: formatVND(l.price),
            qtyLabel:       `${l.qty} × ${formatVND(l.price)}`,
            // Hiện số lượng bao bì đã mua nếu dòng này có đóng gói (vd. "3 Thùng")
            pkgLabel: l.pkg_name ? `${Math.round(l.pkg_count)} ${l.pkg_name}` : '',
        }));
    }
    get orderTotal()  { return formatVND(this.order.total || 0); }
    // Chi tiết thanh toán kiểu Odoo: chưa VAT/chưa CK → sau CK → từng nhóm thuế → tổng
    get amountBeforeDiscount() { return formatVND(this.order.amount_before_discount || 0); }
    get amountUntaxed()        { return formatVND(this.order.amount_untaxed         || 0); }
    get amountTax()            { return formatVND(this.order.amount_tax             || 0); }
    // Tách riêng theo từng nhóm thuế (vd. Thuế GTGT) nếu đơn dùng nhiều nhóm thuế
    get taxGroupRows() {
        return (this.order.tax_groups || []).map(tg => ({
            name:      tg.name,
            amountFmt: formatVND(tg.amount),
        }));
    }
    get hasTax() { return (this.order.amount_tax || 0) > 0.005; }
    get paidAmount()  { return formatVND(this.order.paid  || 0); }
    get remainAmount(){ return formatVND((this.order.total || 0) - (this.order.paid || 0)); }
    get remainColor() { return (this.order.total || 0) > (this.order.paid || 0) ? '#A32D2D' : '#27500A'; }
    get payPct()      { return pct(this.order.paid || 0, this.order.total || 0); }
    get payClass()    {
        const paid = this.order.paid || 0, total = this.order.total || 0;
        if (paid >= total) return 'ps-paid';
        if (paid > 0)      return 'ps-partial';
        return 'ps-unpaid';
    }
    get payLabel()    {
        const paid = this.order.paid || 0, total = this.order.total || 0;
        if (paid >= total) return 'Đã thanh toán';
        if (paid > 0)      return `Thanh toán ${this.payPct}%`;
        return 'Chưa thanh toán';
    }
    get showPayProgress() {
        const paid = this.order.paid || 0, total = this.order.total || 0;
        return paid > 0 && paid < total;
    }

    // Arrow function — called from template with arg
    timelineStepClass = (i) => {
        const idx = this.timelineIndex;
        if (i < idx) return 'tlstep done';
        if (i === idx) return 'tlstep cur';
        return 'tlstep';
    };
}
