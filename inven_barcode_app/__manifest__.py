# -*- coding: utf-8 -*-

{
    'name': "Barcode - Vận Kho",
    'summary': "Use barcode scanners to process logistics operations",
    'description': """
This module enables the barcode scanning feature for the warehouse management system.
    """,
    'category': 'Inventory/Inventory',
    'sequence': 255,
    'version': '1.0',
    'depends': ['stock'],
    'data': [
        'views/ir_sequence_views.xml',
        'views/stock_location_views.xml',
        'views/stock_picking_views.xml'
    ],
    'external_dependencies': {
       'python': ['python-barcode'],
    },
    'installable': True
}
