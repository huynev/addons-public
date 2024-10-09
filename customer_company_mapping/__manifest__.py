# Copyright 2024 Wokwy - quochuy.software@gmail.com
{
    'name': 'Customer Company Mapping',
    'version': '1.0',
    'category': 'Sales',
    'summary': 'Map customers to companies based on address',
    'depends': ['base', 'contacts', 'sale', 'contacts', 'unicubevn_address'],
    'data': [
        'security/ir.model.access.csv',
        'views/customer_company_mapping_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}