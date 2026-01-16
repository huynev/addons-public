# -*- coding: utf-8 -*-
# Copyright 2024 Wokwy - quochuy.software@gmail.com
{
    'name': 'Zalo Integration',
    'version': '1.0',
    'category': 'Tools',
    'summary': 'Integrate Zalo messaging across Odoo modules',
    'description': """
        This module adds Zalo messaging capabilities to various Odoo modules
        such as Sales, Inventory.
    """,
    'author': 'Wokwy support by claude.ai',
    'website': '',
    'depends': ['base', 'zalo_zns'],
    'data': [
        'security/ir.model.access.csv',
        'wizards/send_zalo_message_wizard_views.xml',
        'wizards/batch_send_zalo_wizard_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
    'license': 'LGPL-3',
}