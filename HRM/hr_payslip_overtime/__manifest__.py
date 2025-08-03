{
    'name': 'Payslip Overtime Details',
    'version': '1.0',
    'summary': 'Add overtime details to payslip',
    'description': 'Module to manage overtime details in payslip',
    'category': 'Human Resources/Payroll',
    'author': 'Wokwy + support by Claude.ai',
    'depends': ['payroll', 'hr_attendance'],
    'data': [
        'security/ir.model.access.csv',
        'views/hr_payslip_views.xml',
        'views/hr_overtime_plan_views.xml',
        'views/hr_payroll_report_views.xml',
    ],
    'installable': True,
    'application': False,
}