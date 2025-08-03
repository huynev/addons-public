{
    'name': 'HR Payroll Report',
    'version': '1.0',
    'category': 'Human Resources/Payroll',
    'summary': 'Advanced Payroll Reports for Employees',
    'description': """
HR Payroll Report
================
This module provides detailed payroll reports for employees.
    """,
    'author': 'Your Name',
    'website': 'https://www.yourwebsite.com',
    'depends': ['payroll', 'hr'],
    'data': [
        'security/hr_payroll_report_security.xml',
        'security/ir.model.access.csv',
        'views/hr_payroll_report_views.xml',
        'wizards/hr_payroll_excel_view.xml',
        'report/hr_payroll_report_templates.xml',
    ],
    'demo': [],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
    'external_dependencies': {
        'python': ['xlsxwriter'],
    },
}