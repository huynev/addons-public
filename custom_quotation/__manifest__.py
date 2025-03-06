{
    'name': 'Custom Quotation',
    'version': '1.0',
    'category': 'Sales',
    'summary': 'Custom Quotation Management',
    'author': '(Wokwy) quochuy.software@gmail.com + claude.ai',
    'description': """
        Module for managing custom quotations independent of sales module
    """,
    'depends': ['base', 'product', 'portal', 'sale'],
    'data': [
        'security/ir.model.access.csv',
        'reports/quotation_report_template.xml',
        'views/custom_quotation_views.xml',
        'views/custom_quotation_portal_templates.xml',
    ],
    'installable': True,
    'application': False,
}