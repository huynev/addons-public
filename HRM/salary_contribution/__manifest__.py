{
    'name': 'Salary Contribution Management',
    'version': '1.0',
    'category': 'Human Resources',
    'summary': 'Manage Employee Salary Contributions',
    'description': '''
        Quản lý đóng góp từ lương nhân viên
        - Hỗ trợ đăng ký đóng góp
        - Quản lý tỷ lệ đóng góp
        - Theo dõi lịch sử đóng góp
    ''',
    'author': 'Wokwy + suppoert by Claude.ai',
    'website': 'https://www.c2bgroup.net',
    'depends': ['hr', 'payroll'],
    'data': [
        'security/ir.model.access.csv',
        'views/salary_contribution_views.xml',
        'views/hr_contract_views.xml',
        'views/contribution_type_views.xml',
        'views/hr_employee_views.xml',
        'wizards/contribution_report_wizard_view.xml',
        'wizards/contribution_register_wizard_views.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}