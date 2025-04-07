{
    'name': 'POS Scan Product',
    'version': '17.0.1.0.0',
    'category': 'Point of Sale',
    'summary': 'Thêm chức năng quét mã vạch và QR code cho sản phẩm trong POS',
    'description': """
        Module này thêm một nút quét vào màn hình POS.
        Khi nhấn vào nút, một popup sẽ hiển thị cho phép:
        - Quét mã vạch/QR bằng camera
        - Tải lên file chứa mã vạch/QR
        Sau khi quét, sản phẩm tương ứng sẽ được thêm vào đơn hàng POS.
    """,
    'author': 'Wokwy + support by Claude.ai',
    'website': 'www.quanghuycorp.com',
    'depends': ['point_of_sale'],
    'data': [],
    'assets': {
        'point_of_sale._assets_pos': [
            'pos_scan_product/static/lib/html5-qrcode.min.js',
            'pos_scan_product/static/src/components/scan_dialog/scan_dialog.js',
            'pos_scan_product/static/src/components/scan_dialog/scan_dialog.xml',
            'pos_scan_product/static/src/components/scan_button/scan_button.js',
            'pos_scan_product/static/src/components/scan_button/scan_button.scss',
            'pos_scan_product/static/src/components/scan_button/scan_button.xml',
            'pos_scan_product/static/src/components/pos_scan_product.js',
        ],
        'web.assets_common': [
            'pos_scan_product/static/src/sounds/beep.mp3',
        ],
    },
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}