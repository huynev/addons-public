# -*- coding: utf-8 -*-
{
    'name': 'VNPT Invoice Integration',
    'version': '17.0.1.0.0',
    'category': 'Accounting/Localization',
    'summary': 'Integration with VNPT E-invoice service for Vietnam',
    'description': """
VNPT Invoice Integration for Odoo 17
===================================

This module provides integration with VNPT E-invoice service for Vietnamese companies.

Features:
- Configure VNPT connection settings
- Push invoices to VNPT e-invoice system
- Handle VNPT responses and error codes
- Support for Vietnam e-invoice format (TT78)
- Automatic invoice numbering from VNPT
- Invoice status synchronization

Requirements:
- VNPT Invoice account
- Valid digital certificate for signing
- Vietnam localization
""",
    'author': 'wokwy (quochuy.software@gmail.com)',
    'website': 'https://c2bgroup.net',
    'depends': [
        'account',
        'l10n_vn',
        'mail',
    ],
    'external_dependencies': {
        'python': ['zeep', 'requests', 'lxml'],
    },
    'data': [
        'security/ir.model.access.csv',
        'data/vnpt_invoice_data.xml',
        'views/vnpt_config_views.xml',
        'views/account_move_views.xml',
        'views/menu_views.xml',
        'wizard/vnpt_invoice_wizard_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
    'license': 'LGPL-3',
}