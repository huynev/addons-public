/** @odoo-module **/

import { AbstractAwaitablePopup } from "@point_of_sale/app/popup/abstract_awaitable_popup";
import { useState, onWillStart, onWillUnmount } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { loadJS } from "@web/core/assets";

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

        // Phát hiện iOS
        this.isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;
        this.isPWA = window.matchMedia('(display-mode: standalone)').matches;

        this.state = useState({
            showCamera: false,
            showFileUpload: false,
            cameraMessage: '',
            fileMessage: '',
            filePreview: null,
            scanning: false,
            lastScannedBarcode: null,
            lastScannedTime: 0,
            showIOSWarning: this.isIOS && !this.isPWA,
            availableCameras: [], // Danh sách camera sẵn có
            selectedCameraId: null
        });

        this.html5QrcodeScanner = null;
        this.beepSound = new Audio("/pos_scan_product/static/src/sounds/beep.mp3");

        // Khởi tạo thư viện khi setup
        onWillStart(async () => {
            try {
                // Tải thư viện html5-qrcode
                await loadJS("/pos_scan_product/static/lib/html5-qrcode.min.js");

                // Khởi tạo danh sách camera
                await this._initializeCameras();
            } catch (error) {
                console.error('Lỗi khi khởi tạo thư viện quét mã:', error);
                this.notification.add('Không thể tải thư viện quét mã', {
                    type: 'warning'
                });
            }
        });

        // Đảm bảo dừng quét khi component bị hủy
        onWillUnmount(() => {
            this._stopCamera();
        });
    }

    // Xử lý cảnh báo iOS
    dismissIOSWarning() {
        this.state.showIOSWarning = false;
    }

    // Mở camera để quét
    openCamera() {
        this.state.showCamera = true;
        this.state.showFileUpload = false;
        this.state.cameraMessage = 'Đang khởi tạo camera...';
        this.state.lastScannedBarcode = null;
        this.state.lastScannedTime = 0;

        // Bắt đầu quét
        this._startCameraScanning();
    }

    // Mở chế độ tải file
    openFileUpload() {
        this.state.showCamera = false;
        this.state.showFileUpload = true;
        this.state.fileMessage = 'Vui lòng chọn ảnh chứa mã vạch hoặc QR code';

        // Đảm bảo đóng camera nếu đang mở
        this._stopCamera();
    }

    // Xử lý khi chọn file
    handleFileInput(event) {
        const file = event.target.files[0];
        if (!file) return;

        this.state.fileMessage = 'Đang xử lý ảnh...';

        // Hiển thị preview file
        const fileReader = new FileReader();
        fileReader.onload = (e) => {
            this.state.filePreview = e.target.result;

            // Quét mã vạch từ ảnh
            this._scanFromImage(file);
        };
        fileReader.readAsDataURL(file);
    }

    // Khởi tạo danh sách camera
    async _initializeCameras() {
        try {
            // Kiểm tra xem thư viện đã được tải
            if (typeof Html5QrcodeScanner === 'undefined') {
                throw new Error('Thư viện Html5QrcodeScanner chưa được tải');
            }

            // Lấy danh sách camera
            const devices = await Html5QrcodeScanner.getCameras();
            this.state.availableCameras = devices;

            // Chọn camera mặc định
            if (devices.length > 0) {
                // Ưu tiên camera sau
                const environmentCamera = devices.find(device =>
                    device.label.toLowerCase().includes('back') ||
                    device.label.toLowerCase().includes('rear')
                ) || devices[0];

                this.state.selectedCameraId = environmentCamera.id;
            }
        } catch (error) {
            console.error('Lỗi khi lấy danh sách camera:', error);
            this.notification.add('Không thể lấy danh sách camera', {
                type: 'warning'
            });
        }
    }

    // Bắt đầu quét camera
    _startCameraScanning() {
        try {
            // Kiểm tra xem thư viện đã được tải
            if (typeof Html5QrcodeScanner === 'undefined') {
                throw new Error('Thư viện Html5QrcodeScanner chưa được tải');
            }

            // Dừng bất kỳ quét nào đang diễn ra
            this._stopCamera();

            // Tạo container cho scanner
            const containerId = 'reader';
            let container = document.getElementById(containerId);
            if (!container) {
                const cameraContainer = document.querySelector('.camera-container');
                if (!cameraContainer) {
                    throw new Error('Không tìm thấy container để chèn scanner');
                }
                container = document.createElement('div');
                container.id = containerId;
                container.style.width = '100%';
                container.style.height = '300px';
                cameraContainer.appendChild(container);
            }

            // Cấu hình scanner
            const config = {
                fps: 10,
                qrbox: 250
            };

            // Khởi tạo scanner
            this.html5QrcodeScanner = new Html5QrcodeScanner(
                containerId,
                config,
                /* verbose= */ false
            );

            // Render scanner với các callback
            this.html5QrcodeScanner.render(
                this._onScanSuccess.bind(this),
                this._onScanError.bind(this)
            );

            this.state.scanning = true;
            this.state.cameraMessage = 'Đưa mã vạch/QR vào vùng quét';
        } catch (error) {
            console.error('Lỗi khi khởi động camera:', error);
            this.state.cameraMessage = 'Không thể khởi động camera: ' + (error.message || 'Lỗi không xác định');
            this.notification.add(this.state.cameraMessage, {
                type: 'warning'
            });
        }
    }

    // Xử lý khi quét thành công
    _onScanSuccess(decodedText, decodedResult) {
        const currentTime = Date.now();
        if (currentTime - this.state.lastScannedTime < 3000) return;

        if (this.scanCount >= 5) {
        this.html5QrcodeScanner.clear();
            return;
        }

        this.scanCount = (this.scanCount || 0) + 1;

        this.state.lastScannedTime = currentTime;
        this.state.cameraMessage = `Đã quét được mã: ${decodedText}`;

        const product = this.posModel.db.get_product_by_barcode(decodedText);
        if (product) {
            const success = this._addOrUpdateProduct(product);
            if (!success) {
                this.notification.add(`Không thể thêm sản phẩm vào đơn hàng`, {
                    type: "warning",
                });
            }
        } else {
            this.notification.add(`Không tìm thấy sản phẩm với mã vạch: ${decodedText}`, {
                type: "warning",
            });
        }
    }

    // Xử lý lỗi khi quét
    _onScanError(errorMessage) {
        console.log('Scan error:', errorMessage);
        this.state.cameraMessage = 'Lỗi quét: ' + errorMessage;
    }

    // Dừng camera
    _stopCamera() {
        if (this.html5QrcodeScanner) {
            try {
                this.html5QrcodeScanner.clear();
                this.html5QrcodeScanner = null;
            } catch (error) {
                console.error('Lỗi khi dừng camera:', error);
            }
        }

        this.state.scanning = false;
        this.state.cameraMessage = '';
    }

    // Quét từ ảnh tải lên
    async _scanFromImage(imageFile) {
        try {
            // Kiểm tra thư viện
            if (typeof Html5Qrcode === 'undefined') {
                throw new Error('Thư viện Html5Qrcode chưa được tải');
            }

            const html5QrCode = new Html5Qrcode('');
            const result = await html5QrCode.scanFile(imageFile);

            if (result) {
                this.state.fileMessage = 'Đã quét được mã: ' + result.decodedText;

                // Xử lý mã vạch
                const product = this.posModel.db.get_product_by_barcode(result.decodedText);

                if (product) {
                    // Thêm hoặc cập nhật sản phẩm trong đơn hàng
                    const success = this._addOrUpdateProduct(product);

                    if (!success) {
                        this.notification.add(`Không thể thêm sản phẩm vào đơn hàng`, {
                            type: "warning",
                        });
                    }
                } else {
                    this.notification.add(`Không tìm thấy sản phẩm với mã vạch: ${result.decodedText}`, {
                        type: "warning",
                    });
                }
            } else {
                this.state.fileMessage = 'Không tìm thấy mã vạch hoặc QR code trong ảnh';
            }
        } catch (error) {
            console.error('Lỗi khi quét ảnh:', error);
            this.state.fileMessage = 'Lỗi khi quét ảnh: ' + (error.message || 'Lỗi không xác định');
        }
    }

    // Phát âm thanh beep
    _playBeepSound() {
        try {
            // Thử nhiều phương pháp phát âm thanh
            if (this.beepSound) {
                // Đặt âm lượng và thời gian
                this.beepSound.volume = 1.0;
                this.beepSound.currentTime = 0;

                // Thử các phương thức phát
                const playPromise = this.beepSound.play();

                // Xử lý promise để bắt lỗi
                if (playPromise !== undefined) {
                    playPromise
                        .then(() => {
                            // Phát thành công
                            console.log('Phát âm thanh thành công');
                        })
                        .catch((error) => {
                            // Thử phát với interact
                            console.warn('Không thể phát âm thanh tự động:', error);
                            // Hiển thị thông báo yêu cầu người dùng tương tác
                            this.notification.add('Vui lòng bấm để phát âm thanh', {
                                type: 'warning'
                            });
                        });
                }
            }
        } catch (error) {
            console.warn('Lỗi khi phát âm thanh:', error);
        }
    }

    // Tìm orderline có chứa sản phẩm
    _findOrderline(order, product) {
        let orderlines = order.get_orderlines();
        for (let i = 0; i < orderlines.length; i++) {
            if (orderlines[i].get_product().id === product.id) {
                return orderlines[i];
            }
        }
        return null;
    }

    // Thêm hoặc cập nhật sản phẩm trong đơn hàng
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

        // Phát âm thanh
        this._playBeepSound();

        return true;
    }

    // Trả về payload (nếu cần)
    getPayload() {
        return {};
    }

    // Xử lý khi hủy popup
    cancel() {
        // Đảm bảo đóng camera khi đóng popup
        this._stopCamera();
        super.cancel();
    }

    // Xử lý khi xác nhận popup
    confirm() {
        // Đảm bảo đóng camera khi đóng popup
        this._stopCamera();
        super.confirm();
    }
}