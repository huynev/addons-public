/** @odoo-module **/
import { Component, useState, useRef, onMounted, onWillUnmount } from "@odoo/owl";

export class ProductList extends Component {
    static template = "mobile_portal.ProductList";
    static props = {
        products:    Array,
        categories:  Array,
        filterCat:   Array,
        filterQ:     String,
        cart:        Object,
        hasMore:      { type: Boolean, optional: true },
        loadingMore:  { type: Boolean, optional: true },
        reloadingGrid:{ type: Boolean, optional: true },
        onOpenModal: Function,
        onFilterCat: Function,
        onFilterQ:   Function,
        onLoadMore:  { type: Function, optional: true },
    };

    setup() {
        this.ui           = useState({ catsExpanded: false, showScrollTop: false });
        this.sentinelRef  = useRef("sentinel");
        this.catsWrapRef  = useRef("catsWrap");
        this._observer    = null;
        this._scrollEl    = null;
        this._onScroll    = () => {
            this.ui.showScrollTop = this._scrollEl.scrollTop > 500;
        };
        // Click ra ngoài vùng chọn danh mục (header + panel) → tự thu gọn lại
        this._onDocClick  = (ev) => {
            if (!this.ui.catsExpanded) return;
            const el = this.catsWrapRef.el;
            if (el && !el.contains(ev.target)) this.ui.catsExpanded = false;
        };

        onMounted(() => {
            this._observer = new IntersectionObserver(
                (entries) => {
                    if (entries[0].isIntersecting && this.props.onLoadMore) {
                        this.props.onLoadMore();
                    }
                },
                { threshold: 0.1 }
            );
            if (this.sentinelRef.el) {
                this._observer.observe(this.sentinelRef.el);
                // Sentinel là con trực tiếp của pane cuộn (mp-pane) → dùng làm scroll container
                this._scrollEl = this.sentinelRef.el.parentElement;
                if (this._scrollEl) {
                    this._scrollEl.addEventListener("scroll", this._onScroll, { passive: true });
                }
            }
            document.addEventListener("click", this._onDocClick, true);
        });

        onWillUnmount(() => {
            if (this._observer) {
                this._observer.disconnect();
                this._observer = null;
            }
            if (this._scrollEl) {
                this._scrollEl.removeEventListener("scroll", this._onScroll);
                this._scrollEl = null;
            }
            document.removeEventListener("click", this._onDocClick, true);
        });
    }

    get filterCatNames() {
        const names = [];
        const traverse = (cats) => {
            for (const cat of cats || []) {
                if (this.props.filterCat.includes(cat.id)) names.push(cat.name);
                if (cat.children && cat.children.length) traverse(cat.children);
            }
        };
        traverse(this.props.categories || []);
        return names;
    }

    toggleCats    = () => { this.ui.catsExpanded = !this.ui.catsExpanded; };
    // Tổng qty của tất cả variant thuộc cùng template
    cartQty = (productId) => Object.values(this.props.cart)
        .filter(i => i.tmpl_id === productId)
        .reduce((s, i) => s + i.qty, 0);
    onSearchInput = (ev) => this.props.onFilterQ(ev.target.value);
    onCatClick    = (catId) => this.props.onFilterCat(catId);
    onCardClick   = (product) => this.props.onOpenModal(product);

    scrollToTop = () => {
        if (this._scrollEl) this._scrollEl.scrollTo({ top: 0, behavior: "smooth" });
    };

    // Hide broken image → show letter fallback
    onImgError(ev, product) {
        const img = ev.target;
        img.style.display = "none";
        const fallback = img.nextElementSibling;
        if (fallback) fallback.style.display = "flex";
    }
}
