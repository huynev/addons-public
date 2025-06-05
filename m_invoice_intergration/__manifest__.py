{
    'name': 'M-Invoice Electronic Invoice Integration',
    'version': '17.0.1.0.0',
    'category': 'Accounting',
    'summary': 'Tích hợp hóa đơn điện tử M-Invoice cho Odoo 17',
    'description': '''
        Addon tích hợp hệ thống hóa đơn điện tử M-Invoice:
        - Tạo hóa đơn điện tử từ invoice Odoo
        - Ký và gửi hóa đơn lên CQT
        - Tra cứu trạng thái hóa đơn
        - In hóa đơn điện tử
        - Hủy, điều chỉnh, thay thế hóa đơn
    ''',
    'author': 'Wokwy + support by clause.ai',
    'website': 'https://www.c2bgroup.net',
    'depends': ['account', 'base', 'web'],
    'data': [
        'security/ir.model.access.csv',
        'data/invoice_series_data.xml',
        'views/minvoice_config_views.xml',
        'views/account_move_views.xml',
        'views/minvoice_series_views.xml',
        'views/menu_views.xml',
        'wizard/minvoice_send_wizard_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}