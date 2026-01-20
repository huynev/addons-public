# -*- coding: utf-8 -*-
{
    'name': 'Track Vendor by Lot',
    'version': '17.0.1.0.1',
    'category': 'Inventory/Inventory',
    'summary': 'Track vendor information in lot/serial numbers',
    'description': """
        Track Vendor by Lot
        ===================
        
        This module allows tracking vendor information in lot/serial numbers:
        
        * Add track_vendor_by_lot checkbox in product configuration (visible when tracking=lot)
        * Add partner_id field to stock.lot model
        * Auto-copy vendor from purchase order to lot when creating lot
        * Auto-copy vendor when splitting lots in delivery
        * Auto-copy vendor from raw material lots to finished/byproduct lots in manufacturing
    """,
    'author': 'WOKWY',
    'website': '',
    'license': 'LGPL-3',
    'depends': [
        'stock',
        'purchase_stock',
        'mrp',
        'purchase_lot',
    ],
    'data': [
        'views/product_template_views.xml',
        'views/purchase_order_views.xml',
        'views/stock_lot_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
