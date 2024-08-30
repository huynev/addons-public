# -*- coding: utf-8 -*-
{
    'name': 'Zalo Integration',
    'version': '1.0',
    'category': 'Tools',
    'summary': 'Integrate Zalo messaging across Odoo modules',
    'description': """
        This module adds Zalo messaging capabilities to various Odoo modules
        such as Sales, Inventory, and Accounting.
    """,
    'author': 'Wokwy support by claude.ai',
    'website': '',
    'depends': ['base', 'sale', 'zalo_zns'],
    'data': [
        'security/ir.model.access.csv',
        'views/sale_order_views.xml',
        'wizards/send_zalo_message_wizard_views.xml',
        'wizards/batch_send_zalo_wizard_views.xml',
        'views/ir_actions_act_window.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
    'translations': ['i18n/vi_VN.po'],
}