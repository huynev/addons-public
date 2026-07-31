/** @odoo-module **/
import { Component, useState, onWillUpdateProps } from "@odoo/owl";
import { formatVND, pct } from "../../utils";
const ORDERS_PAGE_SIZE   = 6;
const PAYMENTS_PAGE_SIZE = 6;

export class DebtView extends Component {
    static template = "mobile_portal.DebtView";
    static props = {
        orders:       Array,
        debt:         Object,
        isLoading:    Boolean,
        onOpenDetail: Function,
        onFilter:     Function,
    };

    setup() {
        // Buffer cục bộ cho 2 ô ngày — chỉ đồng bộ lại từ props khi bộ lọc
        // thực sự được áp dụng (props.debt đổi), không đè lúc người dùng
        // đang gõ dở.
        this.local = useState({
            dateFrom: this.props.debt.dateFrom,
            dateTo:   this.props.debt.dateTo,
        });
        // "Chi tiết theo đơn hàng" + "Lịch sử thanh toán" — chỉ hiện dần từng
        // đợt, load thêm khi bấm nút "Xem thêm" (không tự cuộn)
        this.ui = useState({
            visibleOrders:   ORDERS_PAGE_SIZE,
            visiblePayments: PAYMENTS_PAGE_SIZE,
        });

        onWillUpdateProps((nextProps) => {
            this.local.dateFrom = nextProps.debt.dateFrom;
            this.local.dateTo   = nextProps.debt.dateTo;
            // Danh sách đơn hàng đổi (vd. vừa đặt đơn mới) → hiện lại từ đầu
            if (nextProps.orders !== this.props.orders) {
                this.ui.visibleOrders = ORDERS_PAGE_SIZE;
            }
            // Danh sách thanh toán đổi (vd. vừa lọc lại khoảng thời gian) → hiện lại từ đầu
            if (nextProps.debt.payments !== this.props.debt.payments) {
                this.ui.visiblePayments = PAYMENTS_PAGE_SIZE;
            }
        });
    }

    get visibleOrders()   { return this.props.orders.slice(0, this.ui.visibleOrders); }
    get hasMoreOrders()   { return this.ui.visibleOrders < this.props.orders.length; }
    get visiblePayments() { return this.props.debt.payments.slice(0, this.ui.visiblePayments); }
    get hasMorePayments() { return this.ui.visiblePayments < this.props.debt.payments.length; }

    // Load thêm khi bấm nút "Xem thêm" (không tự cuộn)
    loadMoreOrders   = () => { this.ui.visibleOrders   += ORDERS_PAGE_SIZE; };
    loadMorePayments = () => { this.ui.visiblePayments += PAYMENTS_PAGE_SIZE; };

    // ── Tổng quan công nợ (từ /my/shop/api/debt — logic đối soát thật) ─────────
    get paidAmountFmt()      { return formatVND(this.props.debt.paidAmount); }
    get remainingAmountFmt() { return formatVND(this.props.debt.remainingAmount); }
    get heldAmountFmt()      { return formatVND(this.props.debt.heldAmount); }
    get periodLabel() {
        const { dateFrom, dateTo } = this.props.debt;
        if (!dateFrom || !dateTo) return "";
        return `${this._fmtDate(dateFrom)} – ${this._fmtDate(dateTo)}`;
    }
    _fmtDate(isoStr) {
        const [y, m, d] = (isoStr || "").split("-");
        return y ? `${d}/${m}/${y}` : "";
    }

    // ── Bộ lọc khoảng thời gian ──────────────────────────────────────────────
    onDateFromInput = (ev) => { this.local.dateFrom = ev.target.value; };
    onDateToInput   = (ev) => { this.local.dateTo   = ev.target.value; };
    applyFilter     = () => this.props.onFilter(this.local.dateFrom, this.local.dateTo);

    // ── Lịch sử thanh toán (đã lọc theo khoảng thời gian) ───────────────────
    payAmtFmt  = (p) => formatVND(p.amount || 0);
    payHeldFmt = (p) => formatVND(p.held   || 0);

    // ── Chi tiết theo đơn hàng (giữ nguyên, phụ trợ trực quan) ──────────────
    orderPayInfo  = (order) => {
        if (order.status === 'cancel') return { cls: 'ps-na',      label: 'N/A',       color: '#aaa9a2' };
        if (order.paid >= order.total) return { cls: 'ps-paid',    label: 'Đã TT đủ',  color: '#F78614' };
        if (order.paid > 0)            return { cls: 'ps-partial', label: 'TT 1 phần', color: '#BA7517' };
        return                                { cls: 'ps-unpaid',  label: 'Chưa TT',   color: '#E24B4A' };
    };
    orderBarPct    = (order) => pct(order.paid || 0, order.total || 0);
    orderTotalFmt  = (order) => formatVND(order.total || 0);
    orderPaidFmt   = (order) => formatVND(order.paid  || 0);
    orderRemainFmt = (order) => formatVND((order.total || 0) - (order.paid || 0));
}
