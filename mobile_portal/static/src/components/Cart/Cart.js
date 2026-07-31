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

    // Tạm tính chưa VAT (dùng priceUntaxed — giá thật sự dùng làm price_unit khi đặt hàng)
    get subtotalUntaxed() {
        return this.props.items.reduce((s, i) => s + (i.priceUntaxed || i.price) * i.qty, 0);
    }
    get subtotalUntaxedFormatted() { return formatVND(this.subtotalUntaxed); }

    // Nhóm thuế theo % thuế suất (mỗi mức thuế suất khác nhau → 1 dòng riêng)
    // Không làm tròn thuế suất lẫn số tiền thuế — chỉ dùng key chuỗi cố định
    // số thập phân để gộp đúng các dòng cùng 1 mức thuế (tránh sai số dấu
    // phẩy động), số tiền cộng dồn giữ nguyên độ chính xác cho tới lúc format.
    get taxGroups() {
        const byRate = {};
        for (const i of this.props.items) {
            const rate = i.taxRate || 0;
            if (!rate) continue;
            const untaxed = (i.priceUntaxed ?? i.price) * i.qty;
            const taxed   = i.price * i.qty;
            const key = rate.toFixed(4);
            if (!byRate[key]) byRate[key] = { rate, amount: 0 };
            byRate[key].amount += (taxed - untaxed);
        }
        return Object.values(byRate)
            .sort((a, b) => a.rate - b.rate)
            .map(g => ({ label: `Thuế VAT ${this._fmtRate(g.rate)}%`, amountFmt: formatVND(g.amount) }));
    }

    // Hiển thị thuế suất đúng như cấu hình (vd. 8.5%), không ép về số nguyên
    _fmtRate = (rate) => Number(rate.toFixed(2));

    // Arrow function — called from template with arg
    lineTotal  = (item) => formatVND(item.price * item.qty);
    lineTaxTag = (item) => item.taxRate ? `(VAT ${this._fmtRate(item.taxRate)}%)` : '';
}
