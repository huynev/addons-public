{
    'name': 'Salary Allowances',
    'version': '1.0',
    'summary': 'Quản lý phụ cấp lương cho nhân viên',
    'description': """
        Module quản lý phụ cấp lương cho nhân viên:
        - Đăng ký phụ cấp
        - Quản lý loại phụ cấp
        - Tích hợp với bảng lương
    """,
    'category': 'Human Resources/Payroll',
    'author': 'Wokwy + suppoert by Claude.ai',
    'website': 'https://www.c2bgroup.net',
    'depends': ['hr', 'payroll'],
    'data': [
        'security/ir.model.access.csv',
        'views/allowance_type_views.xml',
        'views/salary_allowance_views.xml',
        'views/hr_employee_views.xml',
        'views/hr_contract_views.xml',
        'wizards/mass_allowance_views.xml',
        'views/menu_views.xml',
        'wizards/employee_allowance_report.xml',
        'data/hr_salary_rule_allowance.xml',
    ],
    'demo': [],
    'installable': True,
    'application': False,
    'auto_install': False,
}