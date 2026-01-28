# Delivery Display Module for Odoo

Một module quản lý giao hàng với giao diện tương tác tương tự như Shop Floor trong Odoo MRP.

## 🎯 Compatibility

- ✅ **Odoo 17.0** - Fully compatible
- ✅ **Odoo 18.0** - Native support

> Xem file `MIGRATION.md` để biết chi tiết về compatibility.

## Tính năng

### 1. Giao diện hiển thị trực quan
- Hiển thị delivery orders dưới dạng cards với màu sắc theo trạng thái
- Thông tin chi tiết: khách hàng, ngày giao, xe, tài xế, trọng lượng
- Chỉ báo độ ưu tiên (Priority indicators)

### 2. Bộ lọc linh hoạt
- Lọc theo trạng thái: Draft, Waiting, Confirmed, Ready, Done
- Lọc theo kho (Warehouse)
- Lọc theo xe (Vehicle) 
- Lọc theo tuyến đường (Route)
- Lọc "My Deliveries" - chỉ xem đơn của tôi

### 3. Panel quản lý tài xế
- Hiển thị danh sách tài xế đang hoạt động
- Thông tin xe và đơn hàng được giao
- Chức năng thêm/xóa tài xế

### 4. Tích hợp với Stock Management
- Mở rộng model stock.picking với các trường:
  - vehicle_id: Xe giao hàng
  - driver_id: Tài xế
  - delivery_route_id: Tuyến đường giao hàng
  - shipping_weight: Trọng lượng giao hàng (tự động tính)

## Cài đặt

### 1. Cấu trúc thư mục

```
delivery_display/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   └── stock_picking.py
├── views/
│   └── delivery_display_views.xml
└── static/
    └── src/
        └── delivery_display/
            ├── delivery_display_search_model.js
            ├── delivery_display_search_bar.js
            ├── delivery_display_action.js
            ├── delivery_display.js
            ├── delivery_drivers_panel.js
            ├── delivery_control_panel.js
            ├── delivery_search_bar.xml
            ├── delivery_display_action.xml
            ├── delivery_display.xml
            ├── delivery_drivers_panel.xml
            ├── delivery_control_panel.xml
            ├── delivery_display.scss
            ├── delivery_drivers_panel.scss
            └── delivery_control_panel.scss
```

### 2. Copy files vào đúng vị trí

```bash
# Copy các file JavaScript
mkdir -p delivery_display/static/src/delivery_display
cp delivery_display_search_model.js delivery_display/static/src/delivery_display/
cp delivery_display_search_bar.js delivery_display/static/src/delivery_display/
cp delivery_display_action.js delivery_display/static/src/delivery_display/
cp delivery_display.js delivery_display/static/src/delivery_display/
cp delivery_drivers_panel.js delivery_display/static/src/delivery_display/
cp delivery_control_panel.js delivery_display/static/src/delivery_display/

# Copy các file XML
cp delivery_search_bar.xml delivery_display/static/src/delivery_display/
cp delivery_display_action.xml delivery_display/static/src/delivery_display/
cp delivery_display.xml delivery_display/static/src/delivery_display/
cp delivery_drivers_panel.xml delivery_display/static/src/delivery_display/
cp delivery_control_panel.xml delivery_display/static/src/delivery_display/

# Copy các file SCSS
cp delivery_display.scss delivery_display/static/src/delivery_display/
cp delivery_drivers_panel.scss delivery_display/static/src/delivery_display/
cp delivery_control_panel.scss delivery_display/static/src/delivery_display/

# Copy file views
mkdir -p delivery_display/views
cp views_delivery_display.xml delivery_display/views/delivery_display_views.xml

# Copy file models
mkdir -p delivery_display/models
cp models_stock_picking.py delivery_display/models/stock_picking.py
echo "from . import stock_picking" > delivery_display/models/__init__.py

# Copy root files
cp __init__.py delivery_display/
cp __manifest__.py delivery_display/
```

### 3. Cài đặt module trong Odoo

1. Copy thư mục `delivery_display` vào thư mục addons của Odoo
2. Restart Odoo server
3. Vào Apps > Update Apps List
4. Tìm "Delivery Display" và cài đặt

## Sử dụng

### Truy cập Delivery Display

Inventory → Delivery Display

### Các chức năng chính

#### 1. Xem danh sách deliveries
- Mỗi delivery hiển thị dưới dạng card với thông tin:
  - Tên delivery order
  - Khách hàng
  - Ngày giao hàng dự kiến
  - Xe và tài xế (nếu có)
  - Trạng thái
  - Độ ưu tiên

#### 2. Lọc deliveries
- Click vào các button trên control panel:
  - "All Deliveries": Hiển thị tất cả
  - "My Deliveries": Chỉ deliveries của bạn
  - Các warehouse: Lọc theo kho
  - Các vehicle: Lọc theo xe
  - Các route: Lọc theo tuyến

#### 3. Lọc theo trạng thái
- Sử dụng search bar để chọn trạng thái:
  - Draft: Nháp
  - Waiting: Đang chờ
  - Confirmed: Đã xác nhận
  - Ready: Sẵn sàng giao
  - Done: Hoàn thành

#### 4. Mở delivery order
- Click vào card để mở form chi tiết

## Tùy chỉnh

### Thêm trường mới vào stock.picking

Chỉnh sửa file `models/stock_picking.py`:

```python
class StockPicking(models.Model):
    _inherit = 'stock.picking'
    
    your_field = fields.Char('Your Field')
```

### Thêm filter mới

Chỉnh sửa file `views/delivery_display_views.xml`:

```xml
<filter string="Your Filter" name="your_filter" 
        domain="[('your_field', '=', 'value')]"/>
```

### Tùy chỉnh giao diện

Chỉnh sửa các file SCSS trong `static/src/delivery_display/`

## Dependencies

- stock: Module quản lý kho của Odoo
- web: Web framework của Odoo
- fleet (optional): Để quản lý xe

## Lưu ý

- Module này được thiết kế cho Odoo 18
- Nếu không có module fleet, chức năng vehicle sẽ bị disable
- Có thể mở rộng thêm các chức năng như:
  - Barcode scanning
  - GPS tracking
  - Signature capture
  - Photo upload
  - Print delivery note

## Hỗ trợ

Để được hỗ trợ, vui lòng liên hệ:
- Email: support@yourcompany.com
- Website: https://www.yourcompany.com

## License

LGPL-3

## Tác giả

Your Company - 2024
