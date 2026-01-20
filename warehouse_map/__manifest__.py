# -*- coding: utf-8 -*-
{
    'name': 'Warehouse Map Layout',
    'version': '17.0.1.6.4',
    'category': 'Inventory/Inventory',
    'summary': 'Sơ đồ kho - Cell updates instantly',
    'description': """
        Warehouse Map Layout
    """,
    'author': 'Wokwy (quochuy.software@gmail.com) support by Claude.ai',
    'depends': ['stock', 'product', 'track_vendor_by_lot'],
    'data': [
        'security/ir.model.access.csv',
        'views/blocked_cell_views.xml',
        'views/warehouse_map_views.xml',
        'views/stock_location_views.xml',
        'wizard/location_action_wizard_views.xml',
        'wizard/assign_lot_position_wizard_views.xml',
        'wizard/block_cell_wizard_views.xml',
        'views/menu_views.xml',
    ],
    'demo': [
        'demo/demo_data.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'warehouse_map/static/src/css/warehouse_map.css',
            'warehouse_map/static/src/js/warehouse_map_view.js',
            'warehouse_map/static/src/xml/warehouse_map.xml',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
