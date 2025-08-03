# -*- coding: utf-8 -*-
{
    "name": "Employees",
    'version': '1.0',
    'category': 'Human Resources/Employees',
    "website": "",
    "sequence": 38,
    "summary": "Minh Đúc",
    "license": "LGPL-3",
    "author": "Wokwy",
    "depends": [
        "hr_contract",
        "hr_holidays",
        "payroll",
        "mail",
    ],
    "data": [
        'security/ir.model.access.csv',
        "views/hr_employee.xml",
        "data/hr_seniority_cron.xml",
        'wizard/employee_import_wizard_views.xml',
        'views/menu_views.xml',
    ],
    'external_dependencies': {
        'python': ['pandas', 'openpyxl'],
    },
    "application": False,
}
