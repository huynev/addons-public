# Copyright 2024 Wokwy - quochuy.software@gmail.com
{
    'name': 'Zalo ZNS Integration',
    'version': '1.0',
    'category': 'Marketing',
    'summary': 'Manage Zalo ZNS templates and send messages',
    'author': 'Wokwy support by claude.ai',
    'website': '',
    'depends': ['base', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'views/zalo_zns_config_views.xml',
        'views/zalo_zns_template_views.xml',
        'views/zalo_zns_batch_views.xml',
        'views/zalo_zns_message_views.xml',
        'views/zalo_zns_menu.xml',
        'data/zalo_zns_cron.xml',
        'data/zalo_zns_sequence.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}