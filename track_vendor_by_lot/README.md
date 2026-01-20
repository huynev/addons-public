# Track Vendor by Lot

## Mô tả

Module này cho phép theo dõi thông tin nhà cung cấp trong số lô/serial của sản phẩm trong Odoo 17.

## Tính năng chính

### 1. Cấu hình sản phẩm
- Thêm checkbox **Track Vendor by Lot** trong form sản phẩm
- Checkbox chỉ hiển thị khi sản phẩm có tracking = 'lot' hoặc 'serial'
- Tự động reset về False khi thay đổi tracking về 'none'

### 2. Quản lý số lô
- Thêm trường **Vendor** (partner_id) vào model `stock.lot`
- Hiển thị vendor trong form, tree và search view của số lô
- Cho phép group by theo vendor trong danh sách số lô

### 3. Đơn mua hàng (Purchase Order)
- Tự động copy nhà cung cấp từ đơn mua hàng vào số lô khi:
  - Tạo số lô mới trong quá trình nhận hàng
  - Sản phẩm có `track_vendor_by_lot = True`
  - Số lô chưa có vendor

### 4. Phân tách số lô (Lot Splitting)
- Khi phân tách sản phẩm ở màn hình nhận hàng:
  - Tự động copy vendor từ số lô cha sang số lô con
  - Áp dụng cho các trường hợp internal transfer

### 5. Sản xuất (Manufacturing)
- Khi tạo số lô cho thành phẩm và phụ phẩm:
  - Tự động copy vendor từ số lô nguyên liệu vào số lô thành phẩm
  - Tự động copy vendor vào số lô phụ phẩm (byproduct)
  - Ưu tiên vendor từ nguyên liệu đầu tiên tìm thấy

## Cài đặt

1. Copy thư mục `track_vendor_by_lot` vào thư mục addons của Odoo
2. Update danh sách apps: 
   - Vào Settings > Apps > Update Apps List
3. Tìm và cài đặt module "Track Vendor by Lot"

## Sử dụng

### Cấu hình sản phẩm
1. Vào Inventory > Products > Products
2. Chọn hoặc tạo sản phẩm mới
3. Trong tab Inventory:
   - Chọn Tracking = "By Unique Serial Number" hoặc "By Lots"
   - Tick checkbox "Track Vendor by Lot"

### Đơn mua hàng
1. Tạo đơn mua hàng với sản phẩm đã cấu hình
2. Confirm và nhận hàng (Receipt)
3. Khi tạo/chọn số lô, vendor sẽ tự động được điền từ đơn hàng

### Sản xuất
1. Tạo Manufacturing Order với:
   - Nguyên liệu có số lô đã có vendor
   - Thành phẩm có `track_vendor_by_lot = True`
2. Khi hoàn thành sản xuất, vendor sẽ tự động copy vào số lô thành phẩm

## Phụ thuộc

- `stock` - Inventory Management
- `purchase_stock` - Purchase and Inventory Integration
- `mrp` - Manufacturing

## Tác giả

TRINH QUOC

## Phiên bản

17.0.1.0.0

## Giấy phép

LGPL-3

## Tham khảo

Addon này được phát triển dựa trên tham khảo từ:
- [stock_restrict_lot](https://github.com/OCA/stock-logistics-workflow/tree/17.0/stock_restrict_lot)
- [purchase_lot](https://github.com/OCA/purchase-workflow/tree/17.0/purchase_lot)
- [purchase_mrp_distribution](https://github.com/OCA/manufacture/tree/17.0/purchase_mrp_distribution)

## Ghi chú kỹ thuật

### Xử lý ưu tiên vendor
Khi tìm vendor cho số lô, hệ thống sử dụng thứ tự ưu tiên:
1. Từ đơn mua hàng (purchase_line_id)
2. Từ số lô cha (khi split/transfer)
3. Từ số lô hiện có của cùng sản phẩm trong location

### Hook points
Module override các phương thức sau:
- `stock.move.line.create()` - Để set vendor khi tạo move line
- `stock.move.line.write()` - Để set vendor khi update lot
- `stock.move.line._action_done()` - Để đảm bảo vendor được set khi hoàn thành
- `mrp.production._post_inventory()` - Để copy vendor trong sản xuất
- `mrp.production.button_mark_done()` - Để copy vendor khi hoàn thành MO
- `mrp.product.produce._update_finished_move()` - Để copy vendor trong wizard sản xuất

### Best Practices
- Chỉ enable `track_vendor_by_lot` cho sản phẩm thực sự cần tracking vendor
- Vendor chỉ được set tự động nếu số lô chưa có vendor (không ghi đè)
- Có thể manually update vendor trong form số lô nếu cần

## Hỗ trợ

Nếu có vấn đề hoặc câu hỏi, vui lòng liên hệ với tác giả.
