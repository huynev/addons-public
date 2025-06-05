# M-Invoice Electronic Invoice Integration for Odoo 17

Addon tích hợp hệ thống hóa đơn điện tử M-Invoice cho Odoo 17.

## Tính năng

- **Cấu hình kết nối**: Cấu hình thông tin đăng nhập M-Invoice
- **Đồng bộ ký hiệu**: Tự động đồng bộ ký hiệu hóa đơn từ M-Invoice
- **Tạo hóa đơn điện tử**: Chuyển đổi invoice Odoo thành hóa đơn điện tử
- **Ký và gửi**: Tự động ký và gửi hóa đơn lên Cục Thuế
- **Tra cứu trạng thái**: Theo dõi trạng thái hóa đơn điện tử
- **In hóa đơn**: In hóa đơn điện tử định dạng PDF
- **Xuất XML**: Xuất file XML hóa đơn điện tử

## Cài đặt

1. Copy folder addon vào thư mục addons của Odoo
2. Cập nhật danh sách addons
3. Cài đặt addon "M-Invoice Electronic Invoice Integration"

## Cấu hình

1. Vào **M-Invoice > Configuration > M-Invoice Settings**
2. Tạo cấu hình mới với thông tin:
   - Base URL: URL API M-Invoice
   - Username/Password: Thông tin đăng nhập
   - Mã đơn vị: Mặc định "VP"
3. Test kết nối để kiểm tra
4. Vào **M-Invoice > Configuration > Sync Series** để đồng bộ ký hiệu

## Sử dụng

1. Tạo invoice thông thường trong Odoo
2. Xác nhận (Post) invoice
3. Chọn ký hiệu hóa đơn trong tab "M-Invoice"
4. Click "Send to M-Invoice" để gửi lên hệ thống
5. Sử dụng các nút "Print M-Invoice", "Download XML" khi cần

## Yêu cầu

- Odoo 17.0+
- Python requests library
- Tài khoản M-Invoice hợp lệ

## Hỗ trợ

Liên hệ đội phát triển để được hỗ trợ kỹ thuật.