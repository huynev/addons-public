/** @odoo-module **/

import { AbstractAwaitablePopup } from "@point_of_sale/app/popup/abstract_awaitable_popup";
import { useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { usePos } from "@point_of_sale/app/store/pos_hook";

export class PosScanPopup extends AbstractAwaitablePopup {
    static template = "pos_scan_product.PosScanPopup";
    static defaultProps = {
        title: "Quét mã vạch/QR sản phẩm",
        confirmText: "Đóng",
        cancelText: "Hủy",
        body: "",
    };

    setup() {
        super.setup();
        this.posModel = usePos();
        this.notification = useService("notification");

        this.state = useState({
            showCamera: false,
            showFileUpload: false,
            cameraMessage: '',
            fileMessage: '',
            filePreview: null,
            scanning: false,
            lastScannedBarcode: null,
            lastScannedTime: 0
        });

        this.cameraStream = null;
        this.barcodeDetector = null;

        this.beepSound = new Audio("/pos_scan_product/static/src/sounds/beep.mp3");

        // Khởi tạo BarcodeDetector nếu trình duyệt hỗ trợ
        if ('BarcodeDetector' in window) {
            this.barcodeDetector = new BarcodeDetector({
                formats: ['qr_code', 'code_39', 'code_128', 'ean_13', 'ean_8', 'upc_a', 'upc_e']
            });
        }
    }

    openCamera() {
        this.state.showCamera = true;
        this.state.showFileUpload = false;
        this.state.cameraMessage = 'Đang khởi tạo camera...';
        this.state.lastScannedBarcode = null;
        this.state.lastScannedTime = 0;

        this._startCamera();
    }

    openFileUpload() {
        this.state.showCamera = false;
        this.state.showFileUpload = true;
        this.state.fileMessage = 'Vui lòng chọn ảnh chứa mã vạch hoặc QR code';

        // Đảm bảo đóng camera nếu đang mở
        this._stopCamera();
    }

    handleFileInput(event) {
        const file = event.target.files[0];
        if (!file) return;

        this.state.fileMessage = 'Đang xử lý ảnh...';

        // Hiển thị preview file
        const fileReader = new FileReader();
        fileReader.onload = (e) => {
            this.state.filePreview = e.target.result;

            // Xử lý quét mã vạch từ ảnh
            this._scanFromImage(e.target.result);
        };
        fileReader.readAsDataURL(file);
    }

    async _startCamera() {
        try {
            if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                this.state.cameraMessage = 'Trình duyệt của bạn không hỗ trợ truy cập camera';
                return;
            }

            // Yêu cầu quyền truy cập camera
            this.cameraStream = await navigator.mediaDevices.getUserMedia({
                video: { facingMode: 'environment' }
            });

            // Kết nối luồng video với thẻ video
            const videoElement = document.getElementById('preview');
            if (videoElement) {
                videoElement.srcObject = this.cameraStream;
                videoElement.play();
                this.state.cameraMessage = 'Đưa mã vạch/QR vào vùng quét';

                // Bắt đầu quét liên tục
                this._startScanningLoop(videoElement);
            }
        } catch (error) {
            console.error('Error accessing camera:', error);
            this.state.cameraMessage = 'Không thể truy cập camera: ' + (error.message || 'Lỗi không xác định');
        }
    }

    _stopCamera() {
        if (this.cameraStream) {
            this.cameraStream.getTracks().forEach(track => track.stop());
            this.cameraStream = null;
        }

        const videoElement = document.getElementById('preview');
        if (videoElement) {
            videoElement.srcObject = null;
        }

        this.state.scanning = false;
    }

    // Tìm orderline có chứa sản phẩm, nếu không có trả về null
    _findOrderline(order, product) {
        let orderlines = order.get_orderlines();
        for (let i = 0; i < orderlines.length; i++) {
            if (orderlines[i].get_product().id === product.id) {
                return orderlines[i];
            }
        }
        return null;
    }

    // Phát âm thanh beep
    _playBeepSound() {
        try {
            // Đặt lại thời gian để đảm bảo âm thanh phát từ đầu
            this.beepSound.currentTime = 0;
            this.beepSound.play().catch(error => {
                console.warn('Không thể phát âm thanh:', error);
            });
        } catch (error) {
            console.warn('Lỗi khi phát âm thanh:', error);
        }
    }

    // Thêm sản phẩm vào đơn hàng hoặc tăng số lượng nếu đã tồn tại
    _addOrUpdateProduct(product) {
        const order = this.posModel.get_order();
        if (!order) return false;

        const existing_orderline = this._findOrderline(order, product);

        if (existing_orderline) {
            // Nếu sản phẩm đã tồn tại, tăng số lượng lên 1
            existing_orderline.set_quantity(existing_orderline.get_quantity() + 1);
            this.notification.add(`Đã tăng số lượng ${product.display_name} (SL: ${existing_orderline.get_quantity()})`, {
                type: "success",
            });
        } else {
            // Nếu sản phẩm chưa tồn tại, thêm mới vào đơn hàng
            order.add_product(product);
            this.notification.add(`Đã thêm sản phẩm ${product.display_name} vào đơn hàng`, {
                type: "success",
            });
        }
        this._playBeepSound();

        return true;
    }

    async _startScanningLoop(videoElement) {
        if (!this.barcodeDetector) {
            this.state.cameraMessage = 'Trình duyệt của bạn không hỗ trợ BarcodeDetector';
            return;
        }

        this.state.scanning = true;

        const scanFrame = async () => {
            if (!this.state.scanning || !this.state.showCamera) return;

            try {
                const currentTime = Date.now();
                // Kiểm tra xem đã đủ 2 giây kể từ lần quét cuối chưa
                const shouldScan = currentTime - this.state.lastScannedTime >= 2000;

                if (shouldScan) {
                    const barcodes = await this.barcodeDetector.detect(videoElement);

                    if (barcodes.length > 0) {
                        // Lấy mã đầu tiên tìm thấy
                        const barcode = barcodes[0].rawValue;

                        // Xử lý mã vạch
                        const product = this.posModel.db.get_product_by_barcode(barcode);

                        if (product) {
                            // Cập nhật thời gian quét cuối
                            this.state.lastScannedTime = currentTime;
                            this.state.lastScannedBarcode = barcode;
                            this.state.cameraMessage = `Đã quét được mã: ${barcode}`;

                            // Thêm hoặc cập nhật sản phẩm trong đơn hàng
                            const success = this._addOrUpdateProduct(product);

                            if (!success) {
                                this.notification.add(`Không thể thêm sản phẩm vào đơn hàng`, {
                                    type: "warning",
                                });
                            }
                        } else {
                            this.notification.add(`Không tìm thấy sản phẩm với mã vạch: ${barcode}`, {
                                type: "warning",
                            });
                            this.state.lastScannedTime = currentTime; // Cập nhật thời gian để tránh quét liên tục
                        }
                    }
                }

                // Tiếp tục quét
                requestAnimationFrame(scanFrame);
            } catch (error) {
                console.error('Error scanning barcode:', error);
                this.state.cameraMessage = 'Lỗi khi quét: ' + (error.message || 'Lỗi không xác định');

                // Thử lại sau 1 giây
                setTimeout(() => {
                    if (this.state.scanning) {
                        requestAnimationFrame(scanFrame);
                    }
                }, 1000);
            }
        };

        // Bắt đầu vòng lặp quét
        requestAnimationFrame(scanFrame);
    }

    async _scanFromImage(imageDataUrl) {
        if (!this.barcodeDetector) {
            this.state.fileMessage = 'Trình duyệt của bạn không hỗ trợ BarcodeDetector';
            return;
        }

        try {
            // Tạo đối tượng Image để có thể phân tích
            const img = new Image();
            img.src = imageDataUrl;

            // Đợi ảnh tải xong
            await new Promise(resolve => {
                img.onload = resolve;
            });

            // Phát hiện mã vạch trong ảnh
            const barcodes = await this.barcodeDetector.detect(img);

            if (barcodes.length > 0) {
                // Lấy mã đầu tiên tìm thấy
                const barcode = barcodes[0].rawValue;
                this.state.fileMessage = 'Đã quét được mã: ' + barcode;

                // Xử lý mã vạch
                const product = this.posModel.db.get_product_by_barcode(barcode);

                if (product) {
                    // Thêm hoặc cập nhật sản phẩm trong đơn hàng
                    const success = this._addOrUpdateProduct(product);

                    if (!success) {
                        this.notification.add(`Không thể thêm sản phẩm vào đơn hàng`, {
                            type: "warning",
                        });
                    }
                } else {
                    this.notification.add(`Không tìm thấy sản phẩm với mã vạch: ${barcode}`, {
                        type: "warning",
                    });
                }
            } else {
                this.state.fileMessage = 'Không tìm thấy mã vạch hoặc QR code trong ảnh';
            }
        } catch (error) {
            console.error('Error scanning image:', error);
            this.state.fileMessage = 'Lỗi khi quét ảnh: ' + (error.message || 'Lỗi không xác định');
        }
    }

    getPayload() {
        return {};
    }

    cancel() {
        // Đảm bảo đóng camera khi đóng popup
        this._stopCamera();
        super.cancel();
    }

    confirm() {
        // Đảm bảo đóng camera khi đóng popup
        this._stopCamera();
        super.confirm();
    }
}