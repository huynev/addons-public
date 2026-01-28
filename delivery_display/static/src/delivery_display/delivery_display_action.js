/** @odoo-module */

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { WithSearch } from "@web/search/with_search/with_search";
import { DeliveryDisplay } from "@delivery_display/delivery_display/delivery_display";
import { Component, onWillStart, useSubEnv } from "@odoo/owl";
import { DeliveryDisplaySearchModel } from "@delivery_display/delivery_display/delivery_display_search_model";

// from record.js
const defaultActiveField = { attrs: {}, options: {}, domain: "[]", string: "" };

export class DeliveryDisplayAction extends Component {
    static template = "delivery_display.DeliveryDisplayAction";
    static components = { WithSearch, DeliveryDisplay };
    static props = {
        "*": true,
    };

    get fieldsStructure() {
        return {
            "stock.picking": [
                "id",
                "name",
                "display_name",
                "partner_id",
                "scheduled_date",
                "date_done",
                "state",
                "picking_type_id",
                "location_id",
                "location_dest_id",
                "move_ids",
                "move_line_ids",
                "origin",
                "backorder_id",
                "driver_id",
                "shipping_weight",
                "delivery_route_id",
                "priority",
                "note",
            ],
            "stock.move": [
                "id",
                "name",
                "product_id",
                "product_uom",
                "product_uom_qty",
                "quantity",
                "reserved_availability",
                "picking_id",
                "location_id",
                "location_dest_id",
                "state",
                "description_picking",
            ],
            "stock.move.line": [
                "id",
                "picking_id",
                "product_id",
                "product_uom_id",
                "quantity",
                "qty_done",
                "lot_id",
                "lot_name",
                "package_id",
                "result_package_id",
                "location_id",
                "location_dest_id",
                "state",
            ],
            "res.partner": [
                "id",
                "name",
                "display_name",
                "street",
                "street2",
                "city",
                "state_id",
                "zip",
                "country_id",
                "phone",
                "mobile",
                "email",
            ],
        };
    }

    get fieldsManuallyFetched() {
        return {
            "stock.picking": [
                {"note": "html"},
            ],
        };
    }
    
    setup() {
        this.viewService = useService("view");
        this.fieldService = useService("field");
        this.orm = useService("orm");
        this.userService = useService("user");
        this.resModel = "stock.picking";
        this.models = [];
        const { context } = this.props.action;
        
        // Domain cho delivery orders
        const domain = [
            ["picking_type_id.code", "=", "outgoing"],
            ["state", "in", ["draft", "waiting", "confirmed", "assigned", "done"]],
        ];
        
        let pickingTypeId = false;
        if (context.active_model === "stock.picking.type" && context.active_id) {
            domain.push(["picking_type_id", "=", context.active_id]);
            pickingTypeId = context.active_id;
        }
        
        useSubEnv({
            localStorageName: `delivery_display.db_${this.userService.db.name}.user_${this.userService.userId}.picking_type_${pickingTypeId}`,
        });
        
        onWillStart(async () => {
            for (const [resModel, fieldNames] of Object.entries(this.fieldsStructure)) {
                const fields = await this.fieldService.loadFields(resModel, { fieldNames });
                for (const [fName, fInfo] of Object.entries(fields)) {
                    fields[fName] = { ...defaultActiveField, ...fInfo };
                    delete fields[fName].context;
                }

                if (this.fieldsManuallyFetched[resModel]) {
                    this.fieldsManuallyFetched[resModel].forEach(field => {
                        for (const [fieldName, fieldType] of Object.entries(field)) {
                            fields[fieldName] = { type : fieldType };
                        }
                    });
                }

                this.models.push({ fields, resModel });
            }
            
            const searchViews = await this.viewService.loadViews(
                {
                    resModel: this.resModel,
                    views: [[false, "search"]],
                },
                {
                    load_filters: true,
                    action_id: this.props.action.id,
                }
            );
            
            this.withSearchProps = {
                resModel: this.resModel,
                searchViewArch: searchViews.views.search.arch,
                searchViewId: searchViews.views.search.id,
                searchViewFields: searchViews.fields,
                searchMenuTypes: ["filter", "favorite"],
                irFilters: searchViews.views.search.irFilters,
                context,
                domain,
                orderBy: [
                    { name: "priority", asc: false },
                    { name: "scheduled_date", asc: true },
                    { name: "name", asc: true },
                ],
                SearchModel: DeliveryDisplaySearchModel,
                searchModelArgs: {
                    ...context,
                    loadedWarehouses:
                        JSON.parse(localStorage.getItem(this.env.localStorageName + '_warehouses')) || [],
                    enableWarehouseFilter:
                        !context.warehouse_id &&
                        (await this.userService.hasGroup("stock.group_stock_multi_locations")),
                },
                loadIrFilters: true,
            };
        });
    }
}

registry.category("actions").add("delivery_display", DeliveryDisplayAction);
