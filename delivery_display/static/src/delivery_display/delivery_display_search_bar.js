/** @odoo-module **/

import { SearchBar } from "@web/search/search_bar/search_bar";

export class DeliveryDisplaySearchBar extends SearchBar {
    removeFacet(facet) {
        if (facet.color === "success") {
            this.env.searchModel.state.deliveryFilters.forEach((f) => {
                f.isActive = false;
            });
            return;
        } else if (facet.type === "favorite" && this.env.searchModel.deliveries) {
            for (const filter of this.env.searchModel.state.deliveryFilters) {
                filter.isActive = false;
            }
        }
        return super.removeFacet(facet);
    }
}
DeliveryDisplaySearchBar.template = "delivery_display.DeliveryDisplaySearchBar";
