# Warehouse Map Layout - Sơ đồ kho Odoo 17

## Mô tả

Module **Warehouse Map Layout** giúp hiển thị sơ đồ kho một cách trực quan với các tính năng:

- Hiển thị sơ đồ kho dạng lưới (grid)
- **Mỗi ô là một lot/serial sản phẩm** (mỗi stock.quant)
- Click vào lot để thực hiện các actions:
  - 🔸 **Lấy hàng**: Tạo phiếu xuất kho
  - 🔸 **Chuyển vị trí**: Di chuyển hàng giữa các vị trí trong kho
  - 🔸 **Chuyển kho**: Chuyển hàng sang kho khác
  - 🔸 **Xem chi tiết**: Xem chi tiết lot/quant
  - 🔸 **Chi tiết vị trí**: Xem và chỉnh sửa thông tin vị trí kho

## Cài đặt

1. Copy thư mục `warehouse_map` vào thư mục addons của Odoo
2. Cập nhật danh sách Apps
3. Tìm và cài đặt module "Warehouse Map Layout"

## Cấu hình

### 1. Cấu hình vị trí cho lot/quant

Truy cập: **Inventory > Products > Lots/Serial Numbers** hoặc **Inventory > Reporting > Inventory**

Chọn quant và cấu hình:

- **Vị trí X (Cột)**: Số thứ tự cột (0, 1, 2, ...)
- **Vị trí Y (Hàng)**: Số thứ tự hàng (0, 1, 2, ...)
- **Vị trí Z (Tầng)**: Tầng/kệ (mặc định 0)
- **Hiển thị trên sơ đồ**: Check để hiển thị lot này trên sơ đồ

### 2. Tạo sơ đồ kho

Truy cập: **Inventory > Sơ đồ kho > Sơ đồ kho**

Click **Create** và điền:

- **Tên sơ đồ**: Tên mô tả (VD: "Sơ đồ kho WH/Stock")
- **Kho**: Chọn warehouse
- **Vị trí kho chính**: Chọn parent location
- **Số hàng**: Số hàng trên lưới (VD: 10)
- **Số cột**: Số cột trên lưới (VD: 10)
- **Thứ tự**: Thứ tự hiển thị

### 3. Xem sơ đồ

Sau khi tạo sơ đồ, click vào button **"Xem sơ đồ"** để mở view trực quan.

## Sử dụng

### Hiển thị sơ đồ

Sơ đồ hiển thị dạng lưới với:
- ✅ Màu xanh lá: Ô có hàng tồn
- 🟠 Màu cam: Ô có hàng đã đặt trước (reserved)
- ⚪ Màu trắng: Ô trống (click để gán lot)

Mỗi ô có **kích thước cố định 140x140px** và hiển thị:
- **Badge số ngày trong kho** (góc phải trên)
  - < 60 ngày: Badge xanh tím (bình thường)
  - 60-90 ngày: Badge hồng (cảnh báo)
  - > 90 ngày: Badge đỏ cam nhấp nháy (tồn lâu)
- Tên lot/serial number
- Tên sản phẩm
- Mã sản phẩm
- Số lượng (tổng và khả dụng)
- Số lượng đã đặt trước (nếu có)
- Ngày nhập kho
- Vị trí kho

### Badge số ngày trong kho

Badge hiển thị số ngày hàng đã nằm trong kho (tính từ ngày nhập kho đến hiện tại).

**Mục đích:**
- Theo dõi hàng tồn kho lâu
- Cảnh báo hàng cần xử lý
- Quản lý FIFO (First In First Out)

**Quy tắc màu sắc:**

| Số ngày | Màu sắc | Ý nghĩa | Hành động |
|---------|---------|---------|-----------|
| 0-60 ngày | 🟣 Xanh tím | Bình thường | Không cần xử lý |
| 61-90 ngày | 🟡 Hồng | Cảnh báo | Ưu tiên xuất kho |
| > 90 ngày | 🔴 Đỏ cam (nhấp nháy) | Tồn lâu | Cần xử lý ngay |

**Ví dụ:**
- Hàng nhập ngày 01/10/2024, hôm nay 19/01/2025 → Badge hiển thị "110 ngày" (màu đỏ cam nhấp nháy)
- Hàng nhập ngày 20/12/2024, hôm nay 19/01/2025 → Badge hiển thị "30 ngày" (màu xanh tím)

### Click vào ô trống để gán lot

**Click vào ô trống** sẽ mở wizard cho phép:

#### Option 1: Chọn lot hiện có
- Chọn từ danh sách lots/quants chưa có vị trí
- Chỉ hiển thị lots có số lượng > 0
- Chỉ hiển thị lots trong kho được chọn
- Xác nhận để gán vị trí cho lot

#### Option 2: Tạo quant mới
- Chọn sản phẩm
- Chọn lot/serial (nếu có)
- Nhập số lượng
- Tạo quant mới tại vị trí được chọn

**Lưu ý:** Tạo quant mới chỉ để gán vị trí nhanh. Để thêm hàng thực tế, dùng Receipt/Purchase Order.

### Click vào lot để thực hiện action

**Click vào lot** sẽ hiển thị menu context với các options:

#### 1. Lấy hàng (Pick)
- Tạo phiếu xuất kho (Delivery Order)
- Lot và số lượng được điền sẵn
- Xác nhận để tạo picking

#### 2. Chuyển vị trí (Move)
- Di chuyển lot sang vị trí khác trong cùng kho
- Chọn vị trí đích
- Tạo Internal Transfer

#### 3. Chuyển kho (Transfer)
- Chuyển lot sang kho khác
- Chọn warehouse/location đích
- Tạo Inter-warehouse Transfer

#### 4. Xem chi tiết
- Hiển thị form chi tiết của quant
- Xem/sửa thông tin lot

#### 5. Chi tiết vị trí
- Mở form location
- Xem/sửa thông tin vị trí kho

#### 6. Xóa khỏi sơ đồ
- Ẩn lot khỏi sơ đồ (set display_on_map = False)
- Hàng vẫn còn trong kho
- Có thể gán lại vị trí sau

## Ví dụ Setup

### Cấu hình vị trí cho quants

Truy cập **Inventory > Reporting > Inventory** hoặc **Inventory > Products > Lots/Serial Numbers**

Chọn từng quant và điền:
```
# Lot LOT-001 tại vị trí (0,0)
Vị trí X: 0
Vị trí Y: 0
Vị trí Z: 0
Hiển thị trên sơ đồ: ✓

# Lot LOT-002 tại vị trí (1,0)
Vị trí X: 1
Vị trí Y: 0
Vị trí Z: 0
Hiển thị trên sơ đồ: ✓

# Lot LOT-003 tại vị trí (0,1)
Vị trí X: 0
Vị trí Y: 1
Vị trí Z: 0
Hiển thị trên sơ đồ: ✓
```

### Cấu trúc sơ đồ mẫu

```
Grid 5x5:
[0,0] LOT-001  [1,0] LOT-002  [2,0] LOT-003  [3,0] Empty   [4,0] Empty
[0,1] LOT-004  [1,1] LOT-005  [2,1] Empty    [3,1] Empty   [4,1] Empty
[0,2] LOT-006  [1,2] Empty    [2,2] Empty    [3,2] Empty   [4,2] Empty
[0,3] Empty    [1,3] Empty    [2,3] Empty    [3,3] Empty   [4,3] Empty
[0,4] Empty    [1,4] Empty    [2,4] Empty    [3,4] Empty   [4,4] Empty
```

## Tính năng nâng cao

### Custom CSS theo màu vị trí

Nếu location có trường `color_code`, ô sẽ hiển thị màu tùy chỉnh.

### Hỗ trợ nhiều tầng

Sử dụng trường `posz` để quản lý nhiều tầng/kệ trong kho.

### Real-time refresh

Click button "Làm mới" để cập nhật dữ liệu mới nhất từ kho.

## Lưu ý

1. Đảm bảo các location đã được cấu hình đúng vị trí X, Y
2. Module yêu cầu Odoo 17.0
3. Phụ thuộc vào modules: `stock`, `product`

## Tác giả

**TRINH QUOC**

## License

LGPL-3

## Hỗ trợ

Nếu gặp vấn đề, vui lòng tạo issue hoặc liên hệ tác giả.
