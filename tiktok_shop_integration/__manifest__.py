# Copyright 2024 Wokwy - quochuy.software@gmail.com
{
    'name': 'TikTok Shop Integration',
    'version': '1.0',
    'category': 'Sales/Sales',
    'summary': 'Integrate TikTok Shop with Odoo',
    'description': """
        This module integrates TikTok Shop with Odoo, allowing:
        - Synchronization of orders from TikTok to Odoo
        - Stock synchronization between TikTok and Odoo
        - Product synchronization between TikTok and Odoo
    """,
    'author': 'Wokwy support by claude.ai',
    'website': '',
    'depends': ['base', 'sale_management', 'stock'],
    'data': [
        'security/ir.model.access.csv',
        'views/tiktok_shop_views.xml',
        'views/product_views.xml',
        'views/sale_order_views.xml',
        'data/tiktok_shop_data.xml',
        'views/tiktok_category_views.xml',
        'views/tiktok_category_mapping_wizard_views.xml',
        'security/ir.model.access.csv',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
    'translations': ['i18n/vi_VN.po'],
}