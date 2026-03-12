# -*- coding: utf-8 -*-
{
    'name': 'POS Direct Login',
    'version': '17.0.1.0.0',
    'category': 'Point of Sale',
    'summary': 'Màn hình đăng nhập trực tiếp vào POS mà không qua backend Odoo',
    'author': 'Wokwy (quochuy.software@gmail.com) support by claude.ai',
    'depends': ['point_of_sale', 'web', 'hr', 'pos_hr'],
    'data': [
        'views/pos_login_template.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'pos_direct_login/static/src/css/pos_login.css',
            'pos_direct_login/static/src/js/pos_login.js',
        ],
        'point_of_sale._assets_pos': [
            'pos_direct_login/static/src/pos_patch/pos_direct_login_patch.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
