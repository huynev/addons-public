{
    'name': 'PAX Payment Terminal',
    'version': '18.0.1.0.0',
    'category': 'Point of Sale',
    'summary': 'Integrate PAX payment terminals with Odoo POS',
    'description': """
PAX Payment Terminal Integration
================================
This module allows Odoo to communicate with PAX payment terminals.
Features:
- Process credit card payments
- Capture signatures
- Handle various transaction types
- Store transaction details in Odoo
""",
    'author': 'Wokwy (quochuy.software@gmail.com)',
    'website': 'https://c2bgroup.net',
    'depends': ['point_of_sale'],
    'data': [
        'security/ir.model.access.csv',
        'views/pax_terminal_views.xml',
        'views/pos_payment_method_views.xml',
        'data/ir_sequence_data.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'odoo_pax_terminal/static/src/app/**/*',
        ],
    },
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}