{
    'name': 'HR Late/Early Tracking',
    'version': '1.0',
    'summary': 'Theo dõi và tính toán phần đi trễ và về sớm',
    'description': """
Theo dõi và tính toán phần đi trễ và về sớm
===========================================

Module này cho phép:
- Theo dõi thời gian đi trễ và về sớm của nhân viên dựa vào lịch làm việc
- Tính toán khấu trừ lương theo công thức: lương cơ bản/30/8/60 * (tổng số phút đi trễ + tổng số phút về sớm)
- Tích hợp với bảng tính lương
- Báo cáo thống kê đi trễ/về sớm
    """,
    'category': 'Human Resources/Payroll',
    'author': 'Wokwy (quochuy.software@gmail.com)',
    'website': 'https://c2bgroup.net',
    'license': 'AGPL-3',
    'depends': [
        'hr',
        'hr_attendance',
        'payroll',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/hr_late_early_tracking_views.xml',
        'views/hr_payslip_views_extension.xml',
        'views/report_late_early.xml',
        'views/report_late_early_wizard_views.xml',
        'views/hr_late_early_dashboard.xml',
    ],
    'demo': [],
    'installable': True,
    'auto_install': False,
    'application': False,
}