/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { Component, onWillStart, onMounted, onWillUnmount, useState, useRef } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { DeliveryDisplayDriversPanel } from "@delivery_display/delivery_display/delivery_drivers_panel";

export class DeliveryDisplay extends Component {
    static template = "delivery_display.DeliveryDisplay";
    static components = {
        DeliveryDisplayDriversPanel,
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
                connected: [],  // Danh sách tài xế (hr.employee có is_driver=True)
                selected: null, // Tài xế đang được chọn
            },
            showAssignDialog: false,
            assignDialogData: {
                delivery: null,
                pinOrBarcode: "",  // PIN hoặc Barcode nhập vào
            },
            showCameraScanner: false,  // Camera scanner popup
            isScanning: false,          // Đang quét
            pollingInterval: null,      // Auto-refresh interval
            lastDeliveryCount: 0,       // Để detect delivery mới
        });

        this.rootRef = useRef("root");
        this.videoRef = useRef("video_scanner");

        onWillStart(async () => {
            await this.loadDrivers();
            await this.loadDeliveries();
        });

        onMounted(() => {
            this.startAutoRefresh();  // Bắt đầu auto-refresh
        });
        
        onWillUnmount(() => {
            this.stopAutoRefresh();   // Dừng auto-refresh
            this.stopCameraScanner(); // Dừng camera
        });
    }

    async loadDrivers() {
        // Load hr.employee có is_driver = True
        const employees = await this.orm.searchRead(
            "hr.employee",
            [
                ["active", "=", true],
                ["is_driver", "=", true],  // ← CHỈ drivers
            ],
            ["id", "name", "mobile_phone", "work_phone", "barcode", "driver_pin"],
            { 
                order: "name ASC",
            }
        );
        
        // Build driver list với thông tin số đơn
        const driversWithStats = await Promise.all(employees.map(async (employee) => {
            // Đếm số đơn đã giao
            const deliveredCount = await this.orm.searchCount(
                "stock.picking",
                [
                    ["driver_id", "=", employee.id],
                    ["state", "=", "done"],
                    ["picking_type_code", "=", "outgoing"],
                ]
            );
            
            // Đếm số đơn đang giao
            const inProgressCount = await this.orm.searchCount(
                "stock.picking",
                [
                    ["driver_id", "=", employee.id],
                    ["state", "in", ["confirmed", "assigned"]],
                    ["picking_type_code", "=", "outgoing"],
                ]
            );
            
            return {
                id: employee.id,
                name: employee.name,
                mobile_phone: employee.mobile_phone || "",
                work_phone: employee.work_phone || "",
                barcode: employee.barcode || "",
                driver_pin: employee.driver_pin || "",
                deliveredCount: deliveredCount,
                inProgressCount: inProgressCount,
            };
        }));
        
        this.state.drivers.connected = driversWithStats;
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
    }

    getActiveStates() {
        return ["assigned"];
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

    // Click vào delivery card -> Mở popup nhập PIN/Barcode
    async onDeliveryCardClick(delivery) {
        this.state.assignDialogData = {
            delivery: delivery,
            pinOrBarcode: "",
        };
        this.state.showAssignDialog = true;
        
        // Focus vào input sau khi dialog render
        setTimeout(() => {
            const input = document.querySelector('#pin_barcode_input');
            if (input) {
                input.focus();
            }
        }, 100);
    }

    // Đóng popup
    closeAssignDialog() {
        this.state.showAssignDialog = false;
        this.state.assignDialogData = {
            delivery: null,
            pinOrBarcode: "",
        };
    }

    // Update PIN/Barcode input
    updatePinOrBarcode(event) {
        this.state.assignDialogData.pinOrBarcode = event.target.value.trim();
    }

    // Handle Enter key in PIN input
    onPinInputKeyup(event) {
        if (event.key === 'Enter' || event.keyCode === 13) {
            this.confirmAssignDriver();
        }
    }

    // Xác nhận assign driver bằng PIN/Barcode
    async confirmAssignDriver() {
        const { delivery, pinOrBarcode } = this.state.assignDialogData;
        
        if (!pinOrBarcode) {
            this.notification.add(_t("Please enter PIN or scan barcode!"), {
                type: "warning",
            });
            return;
        }

        try {
            // Tìm employee theo PIN hoặc Barcode
            const employees = await this.orm.searchRead(
                "hr.employee",
                [
                    ["active", "=", true],
                    ["is_driver", "=", true],
                    "|",
                    ["driver_pin", "=", pinOrBarcode],
                    ["barcode", "=", pinOrBarcode],
                ],
                ["id", "name"],
                { limit: 1 }
            );

            if (!employees || employees.length === 0) {
                this.notification.add(
                    _t("Driver not found! Please check PIN or Barcode."),
                    { type: "warning" }
                );
                return;
            }

            const employee = employees[0];

            // 1. Assign driver
            await this.orm.write("stock.picking", [delivery.resId], {
                driver_id: employee.id,
            });

            // 2. Validate delivery (xuất kho)
            await this.orm.call(
                "stock.picking",
                "button_validate",
                [[delivery.resId]]
            );

            this.notification.add(
                _t("Delivery %s assigned to %s and validated!", delivery.data.name, employee.name),
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

    // Thêm tài xế mới (mở wizard chọn employees)
    async popupAddDriver() {
        await this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("Add Drivers"),
            res_model: "delivery.display.add.driver.wizard",
            views: [[false, "form"]],
            target: "new",
        });
        
        // Reload drivers
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

        // Set is_driver = False
        await this.orm.write("hr.employee", [driverId], {
            is_driver: false,
        });
        
        // Reload drivers
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

    // ============= AUTO-REFRESH FUNCTIONS =============
    
    startAutoRefresh() {
        // Poll mỗi 10 giây để check deliveries mới
        this.state.pollingInterval = setInterval(() => {
            this.checkNewDeliveries();
        }, 10000); // 10 seconds
        
        this.state.lastDeliveryCount = this.state.deliveries.length;
    }

    stopAutoRefresh() {
        if (this.state.pollingInterval) {
            clearInterval(this.state.pollingInterval);
            this.state.pollingInterval = null;
        }
    }

    async checkNewDeliveries() {
        try {
            const domain = this.props.domain.concat([
                ["state", "in", this.getActiveStates()],
                ["picking_type_code", "=", "outgoing"],
            ]);

            const newDeliveries = await this.orm.searchRead(
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

            // Build map of new deliveries for easy lookup
            const newDeliveriesMap = new Map(newDeliveries.map(d => [d.id, d]));
            const existingIds = new Set(this.state.deliveries.map(d => d.resId));
            
            let stateChangedCount = 0;
            let addedCount = 0;
            let removedCount = 0;

            // Check for state changes in existing deliveries
            for (const delivery of this.state.deliveries) {
                const newData = newDeliveriesMap.get(delivery.resId);
                
                if (!newData) {
                    // Delivery không còn trong list (đã done/cancelled)
                    removedCount++;
                } else if (newData.state !== delivery.data.state || 
                           newData.driver_id?.[0] !== delivery.data.driver_id?.[0]) {
                    // State hoặc driver đã thay đổi → Update
                    delivery.data = newData;
                    stateChangedCount++;
                }
            }

            // Check for new deliveries
            const addedDeliveries = newDeliveries
                .filter(d => !existingIds.has(d.id))
                .map(d => ({
                    resId: d.id,
                    data: d,
                }));

            if (addedDeliveries.length > 0) {
                // Thêm deliveries mới vào cuối
                this.state.deliveries.push(...addedDeliveries);
                addedCount = addedDeliveries.length;
            }

            // Remove deliveries that no longer match criteria
            if (removedCount > 0) {
                this.state.deliveries = this.state.deliveries.filter(d => 
                    newDeliveriesMap.has(d.resId)
                );
            }

            // Update count
            this.state.lastDeliveryCount = this.state.deliveries.length;

            // Show notifications
            if (addedCount > 0) {
                this.notification.add(
                    _t("%s new delivery(ies) added!", addedCount),
                    { type: "info" }
                );
            }
            
            if (stateChangedCount > 0) {
                this.notification.add(
                    _t("%s delivery(ies) updated!", stateChangedCount),
                    { type: "success" }
                );
            }

            if (removedCount > 0) {
                this.notification.add(
                    _t("%s delivery(ies) completed!", removedCount),
                    { type: "success" }
                );
            }

        } catch (error) {
            console.error("Error checking new deliveries:", error);
        }
    }

    // ============= CAMERA SCANNER FUNCTIONS =============
    
    openCameraScanner() {
        this.state.showCameraScanner = true;
        this.state.isScanning = false;
        
        // Start camera sau khi render
        setTimeout(() => {
            this.startCameraScanner();
        }, 100);
    }

    closeCameraScanner() {
        this.stopCameraScanner();
        this.state.showCameraScanner = false;
    }

    async startCameraScanner() {
        try {
            const video = this.videoRef.el;
            if (!video) {
                console.error("Video element not found");
                return;
            }

            // Request camera permission
            const stream = await navigator.mediaDevices.getUserMedia({
                video: { facingMode: "environment" } // Rear camera
            });

            video.srcObject = stream;
            video.play();
            this.state.isScanning = true;

            // Start scanning
            this.scanBarcodeFromVideo(video);
        } catch (error) {
            console.error("Camera error:", error);
            this.notification.add(
                _t("Cannot access camera: %s", error.message),
                { type: "danger" }
            );
        }
    }

    stopCameraScanner() {
        const video = this.videoRef.el;
        if (video && video.srcObject) {
            const stream = video.srcObject;
            const tracks = stream.getTracks();
            tracks.forEach(track => track.stop());
            video.srcObject = null;
        }
        this.state.isScanning = false;
    }

    async scanBarcodeFromVideo(video) {
        // Try native BarcodeDetector API first
        if ('BarcodeDetector' in window) {
            try {
                const barcodeDetector = new BarcodeDetector({
                    formats: ['code_128', 'code_39', 'code_93', 'ean_13', 'ean_8', 'qr_code']
                });

                const scanLoop = async () => {
                    if (!this.state.isScanning) return;

                    try {
                        const barcodes = await barcodeDetector.detect(video);
                        if (barcodes.length > 0) {
                            const barcode = barcodes[0].rawValue;
                            this.onBarcodeDetected(barcode);
                            return; // Stop scanning
                        }
                    } catch (error) {
                        // Continue silently
                    }

                    // Continue scanning
                    requestAnimationFrame(scanLoop);
                };

                scanLoop();
                return;
            } catch (error) {
                console.warn("BarcodeDetector failed, trying fallback:", error);
            }
        }

        // Fallback: Use ZXing library
        this.scanWithZXing(video);
    }

    async scanWithZXing(video) {
        // Load ZXing library dynamically
        if (!window.ZXing) {
            try {
                // Load from CDN
                await this.loadScript('https://unpkg.com/@zxing/library@latest/umd/index.min.js');
            } catch (error) {
                this.notification.add(
                    _t("Cannot load barcode scanner library. Please use manual input."),
                    { type: "warning" }
                );
                this.closeCameraScanner();
                return;
            }
        }

        try {
            const codeReader = new ZXing.BrowserMultiFormatReader();
            const result = await codeReader.decodeOnceFromVideoDevice(undefined, video);
            if (result) {
                this.onBarcodeDetected(result.text);
            }
        } catch (error) {
            if (this.state.isScanning) {
                // Try again
                setTimeout(() => {
                    if (this.state.isScanning) {
                        this.scanWithZXing(video);
                    }
                }, 100);
            }
        }
    }

    loadScript(src) {
        return new Promise((resolve, reject) => {
            const script = document.createElement('script');
            script.src = src;
            script.onload = resolve;
            script.onerror = reject;
            document.head.appendChild(script);
        });
    }

    onBarcodeDetected(barcode) {
        console.log("Barcode detected:", barcode);
        
        // Fill vào input
        this.state.assignDialogData.pinOrBarcode = barcode;
        
        // Close camera
        this.closeCameraScanner();
        
        // Notification
        this.notification.add(
            _t("Barcode scanned: %s", barcode),
            { type: "success" }
        );
        
        // Auto-submit nếu muốn
        // this.confirmAssignDriver();
    }
}
