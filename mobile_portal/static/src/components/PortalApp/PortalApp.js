/** @odoo-module **/
import { Component, useState, onMounted, onWillUnmount } from "@odoo/owl";
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
        const root        = document.getElementById("mobile-portal-root");
        const isLoggedIn  = root?.dataset.isLoggedIn === "1";
        const partnerName = root?.dataset.partnerName || this.env.partnerName || "";
        const partnerId   = parseInt(root?.dataset.partnerId || "0", 10);

        this.state = useState({
            view:            isLoggedIn ? "app" : "login",
            userName:        partnerName,
            partnerId,
            currentTab:      "products",
            products:        [],
            categories:      [],
            filterCat:       [],
            filterQ:         "",
            loadingProducts: true,
            reloadingGrid:   false,
            productOffset:   0,
            productHasMore:  false,
            loadingMore:     false,
            cart:            {},
            orders:          [],
            loadingOrders:   true,
            debt: {
                dateFrom:        "",
                dateTo:          "",
                paidAmount:      0,
                remainingAmount: 0,
                heldAmount:      0,
                payments:        [],
            },
            debtLoaded:      false,
            loadingDebt:     true,
            showModal:         false,
            modalProduct:      null,
            modalQty:          1,
            modalVariant:      null,
            modalPkg:          null,
            modalHasPrior:     false,
            modalCartVariants: {},
            showDetail:      false,
            detailOrder:     null,
            toastMsg:        "",
            toastVisible:    false,
            isPlacing:       false,
            pendingOrders:   0,   // đơn hàng xếp hàng khi offline
        });

        this._onOnline = () => this._flushPendingOrders();

        this._onSwMessage = (ev) => {
            const msg = ev.detail;
            if (msg?.type === 'ORDER_SYNCED') {
                this._fetchOrders();
                this._showToast(`🎉 Đơn hàng đã được gửi! ${msg.order_ref || ''}`);
                this.state.pendingOrders = Math.max(0, this.state.pendingOrders - 1);
            }
        };

        onMounted(async () => {
            if (this.state.view === "app") {
                this._fetchProducts();
                this._fetchOrders();
                if (this.env.getPendingOrderCount) {
                    this.state.pendingOrders = await this.env.getPendingOrderCount();
                }
            }
            window.addEventListener('sw-message', this._onSwMessage);
            window.addEventListener('online', this._onOnline);
        });

        onWillUnmount(() => {
            window.removeEventListener('sw-message', this._onSwMessage);
            window.removeEventListener('online', this._onOnline);
            clearTimeout(this._toastTimer);
        });
    }

    // ─── Computed ─────────────────────────────────────────────────────────────
    get cartItems()  { return Object.values(this.state.cart); }
    // Badge giỏ hàng: cộng đúng số hiển thị giữa nút −/+ của từng dòng trong
    // giỏ (số kiện nếu có chọn bao bì, số lượng lẻ nếu không) — không phải
    // tổng số lượng quy đổi ra đơn vị lẻ.
    get cartCount() {
        return this.cartItems.reduce((s, i) => {
            const displayQty = i.selectedPkg ? Math.round(i.qty / i.selectedPkg.qty) : i.qty;
            return s + displayQty;
        }, 0);
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
            view: "login", cart: {}, orders: [], userName: "",
            debt: { dateFrom: "", dateTo: "", paidAmount: 0, remainingAmount: 0, heldAmount: 0, payments: [] },
            debtLoaded: false,
        });
    };

    // ─── Navigation ───────────────────────────────────────────────────────────
    // Luôn tải lại đơn hàng/công nợ mỗi khi vào tab — dữ liệu này có thể đổi
    // phía Odoo (nhân viên ghi nhận thanh toán, xác nhận đơn...) trong lúc
    // khách đang mở app, nên không được chỉ tải 1 lần rồi dùng mãi.
    switchTab = (tab) => {
        this.state.currentTab = tab;
        if (tab === "orders") this._fetchOrders();
        if (tab === "debt") {
            // "Chi tiết theo đơn hàng" trong tab Công nợ cũng cần state.orders
            this._fetchOrders();
            this._fetchDebt();
        }
    };

    // ─── Products ─────────────────────────────────────────────────────────────
    onFilterCat = async (catId) => {
        if (!catId) {
            this.state.filterCat = [];
        } else {
            const cur = this.state.filterCat;
            const idx = cur.indexOf(catId);
            this.state.filterCat = idx >= 0 ? cur.filter(c => c !== catId) : [...cur, catId];
        }
        this.state.products      = [];
        this.state.reloadingGrid = true;
        await this._fetchProducts(true);
    };
    // Tìm theo tên/mã sản phẩm/danh mục — debounce rồi tìm trên toàn bộ danh
    // mục sản phẩm ở backend (không chỉ lọc trong các trang đã tải sẵn).
    onFilterQ = (query) => {
        this.state.filterQ = query;
        clearTimeout(this._searchTimer);
        this._searchTimer = setTimeout(() => {
            this.state.products      = [];
            this.state.reloadingGrid = true;
            this._fetchProducts(true);
        }, 350);
    };

    onLoadMore = () => {
        if (!this.state.loadingMore && this.state.productHasMore)
            this._fetchProducts(false);
    };

    onOpenModal = (product) => {
        const cartVariants = {};
        for (const item of Object.values(this.state.cart)) {
            if (item.tmpl_id === product.id) cartVariants[item.id] = item;
        }

        // Nếu sản phẩm này đã có trong giỏ, khôi phục đúng lựa chọn cũ (biến
        // thể/bao bì/số lượng) thay vì luôn mở về mặc định.
        let existing = null;
        if (!product.variants || !product.variants.length) {
            // Không có biến thể → chỉ có 1 dòng giỏ hàng duy nhất cho sản phẩm này
            existing = cartVariants[product.variant_id] || null;
        } else {
            // Có biến thể → chỉ tự khôi phục khi giỏ hàng đang có ĐÚNG 1 biến
            // thể của sản phẩm này (nếu có nhiều biến thể, để khách tự chọn)
            const entries = Object.values(cartVariants);
            if (entries.length === 1) existing = entries[0];
        }

        this.state.modalProduct      = product;
        this.state.modalQty          = existing ? existing.qty            : 1;
        this.state.modalVariant      = existing ? existing.selectedVariant : null;
        this.state.modalPkg          = existing ? existing.selectedPkg    : null;
        this.state.modalHasPrior     = !!existing;
        this.state.modalCartVariants = cartVariants;
        this.state.showModal         = true;
    };
    onCloseModal = () => { this.state.showModal = false; this.state.modalProduct = null; };

    onAddToCart = (product, qty, selectedPkg = null, selectedVariant = null) => {
        // `price` = giá đã gồm thuế (hiển thị cho khách); `priceUntaxed` = giá
        // chưa thuế, dùng làm price_unit khi tạo đơn hàng — Odoo sẽ tự cộng
        // thuế của sản phẩm lên trên giá này, không được gửi giá đã gồm thuế
        // xuống backend kẻo bị tính thuế 2 lần.
        const price          = selectedVariant ? selectedVariant.price          : product.price;
        const priceUntaxed   = selectedVariant ? selectedVariant.price_untaxed  : product.price_untaxed;
        const taxRate        = selectedVariant ? selectedVariant.tax_rate       : product.tax_rate;
        const priceFormatted = selectedVariant ? formatVND(selectedVariant.price) : product.priceFormatted;
        const variant_id     = selectedVariant ? selectedVariant.id : product.variant_id;
        this.state.cart = {
            ...this.state.cart,
            [variant_id]: {
                id: variant_id, tmpl_id: product.id, variant_id,
                name: product.name,
                variant_name: selectedVariant ? selectedVariant.name : '',
                price, priceUntaxed, taxRate, priceFormatted,
                qty, unit: product.unit, bg: product.bg, tc: product.tc,
                letter: product.letter,
                selectedPkg:     selectedPkg     || null,
                selectedVariant: selectedVariant || null,
            },
        };
        this.state.showModal = false;
        const label = selectedVariant ? `${product.name} (${selectedVariant.name})` : product.name;
        this._showToast(`✓ Đã thêm ${label}`);
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

        const cartPayload = this.cartItems.map(i => ({
            product_id: i.id,
            variant_id: i.variant_id  || null,
            qty:        i.qty,
            price_unit: i.priceUntaxed, // giá chưa thuế — Odoo tự cộng thuế khi tạo đơn
            pkg_name:   i.selectedPkg ? i.selectedPkg.name : null,
            pkg_qty:    i.selectedPkg ? i.selectedPkg.qty  : null,
        }));

        try {
            const res = await this.env.rpc("/my/shop/api/place_order", { cart_items: cartPayload });
            if (res.error) { this._showToast(`Lỗi: ${res.error}`); return; }
            this.state.cart = {};
            await this._fetchOrders();
            this._showToast(`🎉 Đặt hàng thành công! ${res.order_ref}`);
            setTimeout(() => this.switchTab("orders"), 1200);
        } catch {
            // Offline → lưu vào IndexedDB, tự gửi khi có mạng
            if (!navigator.onLine && this.env.savePendingOrder) {
                try {
                    await this.env.savePendingOrder(cartPayload);
                    const reg = await this.env.swRegPromise;
                    if (reg && 'sync' in reg) await reg.sync.register('sync-orders');
                    this.state.cart = {};
                    this.state.pendingOrders++;
                    this._showToast("📶 Mất mạng — đơn hàng sẽ tự gửi khi có kết nối");
                } catch {
                    this._showToast("Đặt hàng thất bại, vui lòng thử lại");
                }
            } else {
                this._showToast("Đặt hàng thất bại, vui lòng thử lại");
            }
        } finally {
            this.state.isPlacing = false;
        }
    };

    // ─── Orders ───────────────────────────────────────────────────────────────
    onOpenDetail  = (order) => { this.state.detailOrder = order; this.state.showDetail = true; };
    onCloseDetail = ()      => { this.state.showDetail = false; this.state.detailOrder = null; };

    // ─── Internal ─────────────────────────────────────────────────────────────
    async _fetchProducts(reset = true) {
        const PAGE_SIZE = 20;
        if (reset) {
            if (!this.state.reloadingGrid) this.state.loadingProducts = true;
            this.state.productOffset = 0;
        } else {
            this.state.loadingMore = true;
        }
        try {
            const res = await this.env.rpc("/my/shop/api/products", {
                offset:  this.state.productOffset,
                limit:   PAGE_SIZE,
                cat_ids: this.state.filterCat,
                query:   this.state.filterQ,
            });
            const newProducts = (res.products || []).map(p => ({ ...p, priceFormatted: formatVND(p.price) }));
            this.state.products       = reset ? newProducts : [...this.state.products, ...newProducts];
            this.state.productOffset += newProducts.length;
            this.state.productHasMore = res.has_more || false;
            if (res.categories) this.state.categories = res.categories;
        } catch { this._showToast("Không thể tải sản phẩm"); }
        finally  {
            this.state.loadingProducts = false;
            this.state.reloadingGrid   = false;
            this.state.loadingMore     = false;
        }
    }

    async _fetchOrders() {
        // Chỉ hiện spinner toàn màn hình ở lần tải đầu tiên — các lần sau
        // (mỗi khi vào lại tab) chỉ âm thầm làm mới, tránh giật màn hình.
        if (!this.state.orders.length) this.state.loadingOrders = true;
        try {
            const res = await this.env.rpc("/my/shop/api/orders", {});
            this.state.orders = res.orders || [];
        } finally { this.state.loadingOrders = false; }
    }

    // ─── Công nợ ──────────────────────────────────────────────────────────────
    async _fetchDebt(dateFrom = null, dateTo = null) {
        if (!this.state.debtLoaded) this.state.loadingDebt = true;
        try {
            const res = await this.env.rpc("/my/shop/api/debt", {
                date_from: dateFrom || this.state.debt.dateFrom || null,
                date_to:   dateTo   || this.state.debt.dateTo   || null,
            });
            this.state.debt = {
                dateFrom:        res.date_from,
                dateTo:          res.date_to,
                paidAmount:      res.paid_amount      || 0,
                remainingAmount: res.remaining_amount || 0,
                heldAmount:      res.held_amount       || 0,
                payments:        res.payments          || [],
            };
            this.state.debtLoaded = true;
        } catch { this._showToast("Không thể tải công nợ"); }
        finally { this.state.loadingDebt = false; }
    }

    onDebtFilter = (dateFrom, dateTo) => this._fetchDebt(dateFrom, dateTo);

    async _flushPendingOrders() {
        if (!this.env.getAllPendingOrders || this.state.pendingOrders === 0) return;
        let synced = 0;
        try {
            const items = await this.env.getAllPendingOrders();
            for (const { key, value } of items) {
                try {
                    const res = await this.env.rpc('/my/shop/api/place_order', {
                        cart_items: value.cart_items,
                    });
                    if (!res.error) {
                        await this.env.deletePendingOrder(key);
                        synced++;
                    }
                } catch {
                    // vẫn còn lỗi mạng, thử lại lần sau
                }
            }
        } catch {}
        if (synced > 0) {
            this.state.pendingOrders = Math.max(0, this.state.pendingOrders - synced);
            await this._fetchOrders();
            this._showToast(`🎉 Đã gửi ${synced} đơn hàng`);
        }
    }

    _showToast(msg) {
        this.state.toastMsg = msg; this.state.toastVisible = true;
        clearTimeout(this._toastTimer);
        this._toastTimer = setTimeout(() => { this.state.toastVisible = false; }, 2400);
    }
}
