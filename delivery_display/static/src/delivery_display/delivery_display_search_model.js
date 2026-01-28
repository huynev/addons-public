/** @odoo-module **/
import { _t } from "@web/core/l10n/translation";
import { SearchModel } from "@web/search/search_model";
import { useState } from "@odoo/owl";

export class DeliveryDisplaySearchModel extends SearchModel {
    setup(services, args) {
        super.setup(services);
        this.state = useState({
            deliveryFilters: [
                {
                    name: "draft",
                    string: _t("Draft"),
                    isActive: false,
                },
                {
                    name: "waiting",
                    string: _t("Waiting"),
                    isActive: false,
                },
                {
                    name: "confirmed",
                    string: _t("Confirmed"),
                    isActive: !args.show_assigned_only,
                },
                {
                    name: "assigned",
                    string: _t("Ready"),
                    isActive: !args.show_confirmed_only,
                },
                {
                    name: "done",
                    string: _t("Done"),
                    isActive: false,
                },
            ],
        });
        this.recordCache = { ids: [] };
        this.deliveries = true;
        this.loadedWarehouses = args.loadedWarehouses;
        this.enableWarehouseFilter = args.enableWarehouseFilter;
    }

    removeRecordFromCache(id) {
        this.recordCache.ids.splice(this.recordCache.ids.indexOf(id), 1);
    }

    invalidateRecordCache() {
        this.recordCache.ids = [];
    }

    async _notify() {
        this.invalidateRecordCache();
        super._notify();
    }

    _getFacets() {
        // Add delivery filter facet to the search bar if applicable
        const facets = super._getFacets();
        if (this.deliveries && !facets.some((f) => f.type === "favorite")) {
            const values = this.state.deliveryFilters.reduce(
                (acc, i) => (i.isActive ? [...acc, i.string] : acc),
                []
            );
            if (values.length) {
                facets.push({
                    groupId: 0,
                    type: "filter",
                    values: values,
                    separator: "or",
                    icon: "fa fa-filter",
                    color: "success",
                });
            }
        }
        return facets;
    }

    _getIrFilterDescription(params = {}) {
        // Save delivery filters in favorite context
        const { irFilter, preFavorite } = super._getIrFilterDescription(params);
        if (this.deliveries) {
            const activeFilterIds = this.state.deliveryFilters.reduce(
                (acc, i) => (i.isActive ? [...acc, i.name] : acc),
                []
            );
            irFilter.context.delivery_active_filters = activeFilterIds;
            preFavorite.context.delivery_active_filters = activeFilterIds;
        }
        return { preFavorite, irFilter };
    }

    toggleSearchItem(searchItemId) {
        // Retrieve saved delivery filters from context or reset filters when enabling/disabling a favorite respectively
        const { type, context } = this.searchItems[searchItemId];
        if (this.deliveries && type === "favorite") {
            const { delivery_active_filters } = context;
            const removeFavorite =
                !delivery_active_filters ||
                this.query.some((queryElem) => queryElem.searchItemId === searchItemId);
            for (const filter of this.state.deliveryFilters) {
                filter.isActive = !removeFavorite && delivery_active_filters.includes(filter.name);
            }
        }
        return super.toggleSearchItem(searchItemId);
    }

    async deleteFavorite(favoriteId) {
        // Reset delivery filters when deleting a currently enabled favorite
        if (
            this.deliveries &&
            this.query.some((queryElem) => queryElem.searchItemId === favoriteId)
        ) {
            for (const filter of this.state.deliveryFilters) {
                filter.isActive = false;
            }
        }
        return super.deleteFavorite(favoriteId);
    }

    setWarehouseFilter(warehouses) {
        const filter = Object.values(this.searchItems).find(
            (si) => si.name === "delivery_this_warehouse"
        );
        if (!filter) {
            return; // Avoid crashing when 'This Warehouse' filter not installed.
        }
        filter.domain =
            "[['picking_type_id.warehouse_id', 'in', [" +
            warehouses.map((wh) => wh.id).join(",") +
            "]]]";
        if (this.query.find((queryElem) => queryElem.searchItemId === filter.id)) {
            this._notify();
        } else {
            this.toggleSearchItem(filter.id);
        }
    }

    _activateDefaultSearchItems(defaultFavoriteId) {
        super._activateDefaultSearchItems(defaultFavoriteId);
        if (this.enableWarehouseFilter) {
            this.setWarehouseFilter(this.loadedWarehouses);
        }
    }
}
