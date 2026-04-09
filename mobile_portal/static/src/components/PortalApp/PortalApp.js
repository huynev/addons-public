/** @odoo-module **/
import { Component, useState, onMounted } from "@odoo/owl";
import { formatVND } from "../../utils";

import { LoginPage }    from "../LoginPage/LoginPage";
import { RegisterPage } from "../RegisterPage/RegisterPage";
import { BottomNav }    from "../BottomNav/BottomNav";
import { ProductList }  from "../ProductList/ProductList";
import { ProductModal } from "../ProductModal/ProductModal";
import { Cart }         from "../Cart/Cart";
import { OrderList }    from "../OrderList/OrderList";
import { OrderDetail }  from "../OrderDetail/OrderDetail";
import { DebtView }     from "../DebtView/DebtView";

export class PortalApp extends Component {
    static template = "mobile_portal.PortalApp";
    static components = {
        LoginPage, RegisterPage,
        BottomNav, ProductList, ProductModal,
        Cart, OrderList, OrderDetail, DebtView,
    };

    setup() {
        const root = document.getElementById("mobile-portal-root");
        const isLoggedIn  = root?.dataset.isLoggedIn === "1";
        const partnerName = root?.dataset.partnerName || this.env.partnerName || "";
        const partnerId   = parseInt(root?.dataset.partnerId || "0", 10);

        this.state = useState({
            view:            isLoggedIn ? "app" : "login",
            userName:        partnerName,
            partnerId,
            currentTab:      "products",
            products:        [],
            categories:      ["Tất cả"],
            filterCat:       "",
            filterQ:         "",
            loadingProducts: true,
            cart:            {},
            orders:          [],
            payments:        [],
            loadingOrders:   true,
            showModal:       false,
            modalProduct:    null,
            modalQty:        1,
            showDetail:      false,
            detailOrder:     null,
            toastMsg:        "",
            toastVisible:    false,
            isPlacing:       false,
        });

        onMounted(() => {
            if (this.state.view === "app") {
                this._fetchProducts();
                this._fetchOrders();
            }
        });
    }

    // ─── Computed ─────────────────────────────────────────────────────────────
    get cartItems()  { return Object.values(this.state.cart); }
    get cartCount()  { return this.cartItems.reduce((s, i) => s + i.qty, 0); }
    get filteredProducts() {
        const { products, filterCat, filterQ } = this.state;
        return products.filter(p =>
            (!filterCat || p.cat === filterCat) &&
            (!filterQ   || p.name.toLowerCase().includes(filterQ.toLowerCase()))
        );
    }

    // ─── Auth ─────────────────────────────────────────────────────────────────
    onLoginSuccess = ({ partnerName, partnerId }) => {
        this.state.userName  = partnerName;
        this.state.partnerId = partnerId;
        this.state.view      = "app";
        this._fetchProducts();
        this._fetchOrders();
    };

    onRegisterSuccess = ({ partnerName, partnerId }) => {
        this.state.userName  = partnerName;
        this.state.partnerId = partnerId;
        this.state.view      = "app";
        this._fetchProducts();
        this._fetchOrders();
        this._showToast("🎉 Tài khoản đã được tạo!");
    };

    goToRegister = () => { this.state.view = "register"; };
    goToLogin    = () => { this.state.view = "login"; };

    onLogout = async () => {
        try { await this.env.rpc("/my/shop/api/logout", {}); } catch {}
        Object.assign(this.state, {
            view: "login", cart: {}, orders: [], payments: [], userName: "",
        });
    };

    // ─── Navigation ───────────────────────────────────────────────────────────
    switchTab = (tab) => {
        this.state.currentTab = tab;
        if ((tab === "orders" || tab === "debt") && this.state.loadingOrders)
            this._fetchOrders();
    };

    // ─── Products ─────────────────────────────────────────────────────────────
    onFilterCat = (cat)   => { this.state.filterCat = cat; };
    onFilterQ   = (query) => { this.state.filterQ   = query; };

    onOpenModal = (product) => {
        const existing = this.state.cart[product.id];
        this.state.modalProduct = product;
        this.state.modalQty     = existing ? existing.qty : 1;
        this.state.showModal    = true;
    };
    onCloseModal = () => { this.state.showModal = false; this.state.modalProduct = null; };

    onAddToCart = (product, qty) => {
        this.state.cart = {
            ...this.state.cart,
            [product.id]: {
                id: product.id, name: product.name, price: product.price,
                qty, unit: product.unit, bg: product.bg, tc: product.tc,
                letter: product.letter, priceFormatted: product.priceFormatted,
            },
        };
        this.state.showModal = false;
        this._showToast(`✓ Đã thêm ${product.name}`);
    };

    // ─── Cart ─────────────────────────────────────────────────────────────────
    onUpdateCartQty = (productId, delta) => {
        const cart = { ...this.state.cart };
        if (!cart[productId]) return;
        const newQty = cart[productId].qty + delta;
        if (newQty <= 0) delete cart[productId];
        else cart[productId] = { ...cart[productId], qty: newQty };
        this.state.cart = cart;
    };

    onPlaceOrder = async () => {
        if (!this.cartItems.length || this.state.isPlacing) return;
        this.state.isPlacing = true;
        try {
            const res = await this.env.rpc("/my/shop/api/place_order", {
                cart_items: this.cartItems.map(i => ({ product_id: i.id, qty: i.qty, price_unit: i.price })),
            });
            if (res.error) { this._showToast(`Lỗi: ${res.error}`); return; }
            this.state.cart = {};
            await this._fetchOrders();
            this._showToast(`🎉 Đặt hàng thành công! ${res.order_ref}`);
            setTimeout(() => this.switchTab("orders"), 1200);
        } catch { this._showToast("Đặt hàng thất bại, vui lòng thử lại"); }
        finally  { this.state.isPlacing = false; }
    };

    // ─── Orders ───────────────────────────────────────────────────────────────
    onOpenDetail  = (order) => { this.state.detailOrder = order; this.state.showDetail = true; };
    onCloseDetail = ()      => { this.state.showDetail = false; this.state.detailOrder = null; };

    // ─── Internal ─────────────────────────────────────────────────────────────
    async _fetchProducts() {
        this.state.loadingProducts = true;
        try {
            const res = await this.env.rpc("/my/shop/api/products", {});
            this.state.products   = (res.products || []).map(p => ({ ...p, priceFormatted: formatVND(p.price) }));
            this.state.categories = res.categories || ["Tất cả"];
        } catch { this._showToast("Không thể tải sản phẩm"); }
        finally  { this.state.loadingProducts = false; }
    }

    async _fetchOrders() {
        this.state.loadingOrders = true;
        try {
            const res = await this.env.rpc("/my/shop/api/orders", {});
            this.state.orders   = res.orders   || [];
            this.state.payments = res.payments || [];
        } finally { this.state.loadingOrders = false; }
    }

    _showToast(msg) {
        this.state.toastMsg = msg; this.state.toastVisible = true;
        clearTimeout(this._toastTimer);
        this._toastTimer = setTimeout(() => { this.state.toastVisible = false; }, 2400);
    }
}
