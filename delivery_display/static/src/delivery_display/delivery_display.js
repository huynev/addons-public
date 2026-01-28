/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { Component, onWillStart, onMounted, useState, useRef } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { DeliveryDisplaySearchBar } from "@delivery_display/delivery_display/delivery_display_search_bar";
import { DeliveryDisplayDriversPanel } from "@delivery_display/delivery_display/delivery_drivers_panel";
import { DeliveryControlPanelButtons } from "@delivery_display/delivery_display/delivery_control_panel";

export class DeliveryDisplay extends Component {
    static template = "delivery_display.DeliveryDisplay";
    static components = {
        DeliveryDisplaySearchBar,
        DeliveryDisplayDriversPanel,
        DeliveryControlPanelButtons,
    };
    static props = {
        models: Array,
        resModel: String,
        action: Object,
        context: Object,
        domain: Array,
        groupBy: Array,
        orderBy: Array,
        comparison: [Object, { value: null }],
        display: Object,
    };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.dialog = useService("dialog");
        
        this.state = useState({
            deliveries: [],
            drivers: {
                connected: [],  // Danh sách tất cả tài xế
                selected: null, // Tài xế đang được chọn
            },
            warehouses: [],
            routes: [],
            activeFilter: "0",
            showAssignDialog: false,
            assignDialogData: {
                delivery: null,
                selectedDriverId: null,
            },
        });

        this.rootRef = useRef("root");

        onWillStart(async () => {
            await this.loadDrivers();
            await this.loadDeliveries();
            await this.loadWarehouses();
            await this.loadRoutes();
        });

        onMounted(() => {
            this.updateDeliveryList();
        });
    }

    async loadDrivers() {
        // Load partners marked as drivers (is_driver = True)
        const drivers = await this.orm.searchRead(
            "res.partner",
            [
                ["active", "=", true],
                ["is_driver", "=", true],  // ← CHỈ load partners có is_driver=True
            ],
            ["id", "name", "phone", "email"],
            { 
                order: "name ASC",
            }
        );
        
        // Build driver list với thông tin số đơn
        const driversWithStats = await Promise.all(drivers.map(async (driver) => {
            // Đếm số đơn đã giao
            const deliveredCount = await this.orm.searchCount(
                "stock.picking",
                [
                    ["driver_id", "=", driver.id],
                    ["state", "=", "done"],
                    ["picking_type_code", "=", "outgoing"],
                ]
            );
            
            // Đếm số đơn đang giao
            const inProgressCount = await this.orm.searchCount(
                "stock.picking",
                [
                    ["driver_id", "=", driver.id],
                    ["state", "in", ["confirmed", "assigned"]],
                    ["picking_type_code", "=", "outgoing"],
                ]
            );
            
            return {
                id: driver.id,
                name: driver.name,
                phone: driver.phone || "",
                email: driver.email || "",
                deliveredCount: deliveredCount,
                inProgressCount: inProgressCount,
            };
        }));
        
        this.state.drivers.connected = driversWithStats;
    }

    /**
     * Getter: Trả về danh sách đơn hàng thuộc về tài xế đang được chọn.
     * Đây là phần quan trọng để sửa lỗi "myDeliveries is undefined"
     */
    get myDeliveries() {
        if (!this.state.drivers.selected) {
            return [];
        }
        return this.state.deliveries.filter(d =>
            d.data.driver_id && d.data.driver_id[0] === this.state.drivers.selected
        );
    }

    async loadInitialData() {
        await Promise.all([
            this.loadDeliveries(),
            this.loadDrivers(),
            this.loadWarehouses(),
            this.loadRoutes(),
        ]);
    }

    async loadDeliveries() {
        const domain = this.props.domain.concat([
            ["state", "in", this.getActiveStates()],
            ["picking_type_code", "=", "outgoing"],
        ]);

        const deliveries = await this.orm.searchRead(
            this.props.resModel,
            domain,
            [
                "name",
                "partner_id",
                "scheduled_date",
                "date_done",
                "state",
                "picking_type_id",
                "driver_id",
                "priority",
                "origin",
            ],
            {
                order: this.props.orderBy.map(o => `${o.name} ${o.asc ? 'ASC' : 'DESC'}`).join(','),
            }
        );

        this.state.deliveries = deliveries.map(d => ({
            resId: d.id,
            data: d,
        }));
        
        this.updateDeliveryList();
    }

    async loadWarehouses() {
        const warehouses = await this.orm.searchRead(
            "stock.warehouse",
            [],
            ["id", "name", "code"],
            { order: "name ASC" }
        );
        this.state.warehouses = warehouses.map(w => ({
            id: w.id,
            display_name: w.name,
            code: w.code,
        }));
    }

    async loadRoutes() {
        try {
            const routes = await this.orm.searchRead(
                "stock.route",
                [["active", "=", true]],
                ["id", "name"],
                { order: "name ASC" }
            );
            this.state.routes = routes.map(r => ({
                id: r.id,
                display_name: r.name,
            }));
        } catch (error) {
            this.state.routes = [];
        }
    }

    getActiveStates() {
        const activeFilters = this.env.searchModel.state.deliveryFilters
            .filter(f => f.isActive)
            .map(f => f.name);
        
        // Default: confirmed, assigned (đơn cần giao)
        return activeFilters.length > 0 ? activeFilters : ["confirmed", "assigned"];
    }

    selectFilter(filterId) {
        this.state.activeFilter = filterId;
        this.updateDeliveryList();
    }

    toggleFilter() {
        this.notification.add(_t("Filter management coming soon!"), {
            type: "info",
        });
    }

    updateDeliveryList() {
        let filteredDeliveries = [...this.state.deliveries];

        // Filter logic
        if (this.state.activeFilter.startsWith("wh_")) {
            const warehouseId = parseInt(this.state.activeFilter.substring(3));
            filteredDeliveries = filteredDeliveries.filter(d =>
                d.data.picking_type_id && d.data.picking_type_id[0] === warehouseId
            );
        } else if (this.state.activeFilter.startsWith("rt_")) {
            const routeId = parseInt(this.state.activeFilter.substring(3));
            filteredDeliveries = filteredDeliveries.filter(d =>
                d.data.delivery_route_id && d.data.delivery_route_id[0] === routeId
            );
        }

        this.state.filteredDeliveries = filteredDeliveries;
    }

    // Click chọn tài xế trong panel
    setSessionDriver(driverId) {
        this.state.drivers.selected = driverId;
        const driver = this.state.drivers.connected.find(d => d.id === driverId);
        this.notification.add(
            _t("Selected driver: ") + (driver ? driver.name : ''),
            { type: "info" }
        );
    }

    // Click vào delivery card -> Mở popup assign driver
    async onDeliveryCardClick(delivery) {
        this.state.assignDialogData = {
            delivery: delivery,
            selectedDriverId: this.state.drivers.selected || null,
        };
        this.state.showAssignDialog = true;
    }

    // Đóng popup
    closeAssignDialog() {
        this.state.showAssignDialog = false;
        this.state.assignDialogData = {
            delivery: null,
            selectedDriverId: null,
        };
    }

    // Select driver trong popup
    selectDriverInDialog(driverId) {
        this.state.assignDialogData.selectedDriverId = driverId;
    }

    // Xác nhận assign + validate
    async confirmAssignDriver() {
        const { delivery, selectedDriverId } = this.state.assignDialogData;
        
        if (!selectedDriverId) {
            this.notification.add(_t("Please select a driver!"), {
                type: "warning",
            });
            return;
        }

        try {
            // 1. Assign driver
            await this.orm.write("stock.picking", [delivery.resId], {
                driver_id: selectedDriverId,
            });

            // 2. Validate delivery (xuất kho)
            await this.orm.call(
                "stock.picking",
                "button_validate",
                [[delivery.resId]]
            );

            const driver = this.state.drivers.connected.find(d => d.id === selectedDriverId);
            this.notification.add(
                _t("Delivery %s assigned to %s and validated!", delivery.data.name, driver ? driver.name : ''),
                { type: "success" }
            );

            // 3. Reload data
            await this.loadDeliveries();
            await this.loadDrivers();
            
            // 4. Close dialog
            this.closeAssignDialog();

        } catch (error) {
            console.error("Error:", error);
            this.notification.add(
                _t("Error: ") + (error.data?.message || error.message || "Unknown error"),
                { type: "danger" }
            );
        }
    }

    // Thêm tài xế mới
    async popupAddDriver() {
        // Mở wizard add drivers
        await this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("Add Drivers"),
            res_model: "delivery.display.add.driver.wizard",
            views: [[false, "form"]],
            target: "new",
        });
        
        // Reload drivers sau khi đóng wizard
        await this.loadDrivers();
    }

    // Xóa tài xế (set is_driver = False)
    async logout(driverId) {
        const inProgressCount = await this.orm.searchCount(
            "stock.picking",
            [
                ["driver_id", "=", driverId],
                ["state", "in", ["confirmed", "assigned"]],
            ]
        );

        if (inProgressCount > 0) {
            this.notification.add(
                _t("Cannot remove driver with deliveries in progress!"),
                { type: "warning" }
            );
            return;
        }

        // Set is_driver = False thay vì xóa khỏi list
        await this.orm.write("res.partner", [driverId], {
            is_driver: false,
        });
        
        // Reload drivers để update UI
        await this.loadDrivers();
        
        if (this.state.drivers.selected === driverId) {
            this.state.drivers.selected = null;
        }

        this.notification.add(_t("Driver removed"), { type: "success" });
    }

    getDeliveryStateColor(state) {
        const colors = {
            draft: "secondary",
            waiting: "warning",
            confirmed: "info",
            assigned: "primary",
            done: "success",
            cancel: "danger",
        };
        return colors[state] || "secondary";
    }

    getPriorityIcon(priority) {
        if (priority === "2") return "fa-angle-double-up text-danger";
        if (priority === "1") return "fa-angle-up text-warning";
        return "fa-minus text-muted";
    }
}
