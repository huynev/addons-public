{
    'name': 'HR Bank Payroll Report',
    'version': '17.0.1.0.0',
    'summary': 'Generate bank transfer reports for payroll',
    'description': """
        This module allows to generate bank transfer reports in Excel format
        for payroll with separate sheets for each bank.
    """,
    'category': 'Human Resources/Payroll',
    'author': 'Your Company',
    'website': 'https://www.yourcompany.com',
    'depends': [
        'hr',
        'payroll',
        'account_payment',
    ],
    'data': [
        'security/ir.model.access.csv',
        'wizard/hr_payroll_bank_report_view.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
    'external_dependencies': {
        'python': ['xlsxwriter'],
    }
}