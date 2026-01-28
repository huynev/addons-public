# -*- coding: utf-8 -*-
{
    'name': 'Delivery Display',
    'version': '17.0.3.3.0',
    'category': 'Inventory/Delivery',
    'summary': 'Interactive delivery management with beautiful animations',
    'description': """
Delivery Display Module
=======================
This module provides an interactive display for managing delivery orders,
similar to the MRP Shop Floor interface.

Features:
---------
* Visual delivery order cards with status indicators
* Filter by warehouse, vehicle, driver, or route
* Real-time delivery status tracking
* Driver panel for managing assignments
* Priority indicators
* Quick access to delivery details

    """,
    'author': 'Wokwy (quochuy.software@gmail.com) support by Claude.ai',
    'website': 'https://www.c2bgroup.net',
    'depends': [
        'stock',
        'web',
        'hr',
    ],
    'data': [
        'security/ir.model.access.csv',
        'wizard/add_driver_wizard_views.xml',
        'views/hr_employee_views.xml',
        'views/delivery_display_views.xml',
    ],
    'demo': [
        'data/demo_data.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'delivery_display/static/src/delivery_display/delivery_display_action.js',
            'delivery_display/static/src/delivery_display/delivery_display.js',
            'delivery_display/static/src/delivery_display/delivery_drivers_panel.js',
            'delivery_display/static/src/delivery_display/delivery_display_action.xml',
            'delivery_display/static/src/delivery_display/delivery_display.xml',
            'delivery_display/static/src/delivery_display/delivery_drivers_panel.xml',
            'delivery_display/static/src/delivery_display/delivery_display.scss',
            'delivery_display/static/src/delivery_display/delivery_drivers_panel.scss',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
