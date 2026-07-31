/** @odoo-module **/
import { Component, useState } from "@odoo/owl";
import { formatVND } from "../../utils";

export class ProductModal extends Component {
    static template = "mobile_portal.ProductModal";
    static props = {
        product:           Object,
        onAdd:             Function,
        onClose:           Function,
        initialQty:        { type: Number,  optional: true },
        initialVariant:    { type: Object,  optional: true },
        initialPkg:        { type: Object,  optional: true },
        hasPriorSelection: { type: Boolean, optional: true },
        cartVariants:      { type: Object,  optional: true },
    };
    static defaultProps = {
        initialQty: 1, initialVariant: null, initialPkg: null, hasPriorSelection: false,
    };

    setup() {
        // Nếu sản phẩm/biến thể này đã có trong giỏ, khôi phục ĐÚNG bao bì đã
        // chọn trước đó (kể cả mua lẻ = null) thay vì luôn mặc định bao bì đầu
        // tiên. Chỉ áp dụng mặc định "chọn sẵn bao bì đầu" cho lựa chọn mới.
        let defaultPkg;
        if (this.props.hasPriorSelection) {
            defaultPkg = this.props.initialPkg || null;
        } else {
            const pkgs = this.props.initialVariant?.packagings ?? this.props.product.packagings ?? [];
            defaultPkg = pkgs.length > 0 ? pkgs[0] : null;
        }
        const qty = this.props.hasPriorSelection
            ? (this.props.initialQty || 1)
            : (defaultPkg ? defaultPkg.qty : (this.props.initialQty || 1));

        this.state = useState({
            qty,
            selectedVariant: this.props.initialVariant || null,
            selectedPkg:     defaultPkg,
        });
    }

    // Expose utility để template gọi được
    formatVND = formatVND;

    // ── Computed ──────────────────────────────────────────────────────────────
    get currentPrice()          { return this.state.selectedVariant?.price      ?? this.props.product.price; }
    get currentPriceFormatted() { return formatVND(this.currentPrice); }
    get currentTaxRate()        { return this.state.selectedVariant?.tax_rate   ?? this.props.product.tax_rate; }
    get currentPackagings()     { return this.state.selectedVariant?.packagings ?? this.props.product.packagings ?? []; }
    get step()                  { return this.state.selectedPkg ? this.state.selectedPkg.qty : 1; }
    get pkgCount()              { return this.state.selectedPkg ? Math.round(this.state.qty / this.state.selectedPkg.qty) : 0; }

    // ── Variant ───────────────────────────────────────────────────────────────
    selectVariant = (variant) => {
        const same = this.state.selectedVariant?.id === variant.id;
        this.state.selectedVariant = same ? null : variant;

        // Nếu biến thể này đã có trong giỏ, khôi phục đúng bao bì + số lượng
        // đã chọn trước đó (kể cả mua lẻ). Chỉ mặc định bao bì đầu tiên khi
        // đây là lựa chọn mới, chưa từng có trong giỏ.
        const inCart = !same && this.props.cartVariants?.[variant.id];
        if (inCart) {
            this.state.selectedPkg = inCart.selectedPkg || null;
            this.state.qty         = inCart.qty;
        } else {
            const pkgs       = same ? (this.props.product.packagings ?? []) : (variant.packagings ?? []);
            const defaultPkg = pkgs.length > 0 ? pkgs[0] : null;
            this.state.selectedPkg = defaultPkg;
            this.state.qty          = defaultPkg ? defaultPkg.qty : 1;
        }
    };

    // Qty của variant trong giỏ (dùng trong template)
    cartQtyOf = (variantId) => this.props.cartVariants?.[variantId]?.qty || 0;

    // ── Packaging ─────────────────────────────────────────────────────────────
    selectPkg = (pkg) => {
        this.state.selectedPkg = pkg;
        this.state.qty = pkg.qty;
    };

    // Mua lẻ theo đơn vị tính (không theo bao bì) — luôn hiện như 1 lựa chọn
    // riêng cạnh các bao bì, thay vì phải bấm lại vào bao bì đang chọn để bỏ chọn.
    selectRetail = () => {
        this.state.selectedPkg = null;
        this.state.qty = 1;
    };

    // ── Qty ───────────────────────────────────────────────────────────────────
    decrement = () => { if (this.state.qty > this.step) this.state.qty -= this.step; };
    increment = () => { this.state.qty += this.step; };

    // Nhập tay số lượng (khi không chọn bao bì → nhập trực tiếp qty)
    onQtyInput = (ev) => {
        const val = parseInt(ev.target.value, 10);
        if (Number.isFinite(val) && val > 0) this.state.qty = val;
    };
    onQtyBlur = (ev) => {
        const val = parseInt(ev.target.value, 10);
        if (!Number.isFinite(val) || val < 1) this.state.qty = 1;
        ev.target.value = this.state.qty;
    };

    // Nhập tay số lượng (khi có chọn bao bì → nhập số kiện, quy đổi ra qty)
    onPkgCountInput = (ev) => {
        const val = parseInt(ev.target.value, 10);
        if (Number.isFinite(val) && val > 0) this.state.qty = val * this.state.selectedPkg.qty;
    };
    onPkgCountBlur = (ev) => {
        const val = parseInt(ev.target.value, 10);
        if (!Number.isFinite(val) || val < 1) this.state.qty = this.state.selectedPkg.qty;
        ev.target.value = this.pkgCount;
    };

    // ── Actions ───────────────────────────────────────────────────────────────
    onAddClick = () => this.props.onAdd(
        this.props.product,
        this.state.qty,
        this.state.selectedPkg,
        this.state.selectedVariant,
    );
    onOverlayClick = (ev) => { if (ev.target === ev.currentTarget) this.props.onClose(); };

    onImgError(ev) {
        ev.target.style.display = "none";
        const fallback = ev.target.nextElementSibling;
        if (fallback) fallback.style.display = "flex";
    }
}
