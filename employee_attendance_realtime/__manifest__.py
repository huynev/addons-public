{
    'name': 'Employee Attendance Realtime Dashboard',
    'version': '17.0.1.0.0',
    'category': 'Human Resources',
    'summary': 'Real-time employee attendance status dashboard',
    'description': """
        Employee Attendance Realtime Dashboard
        =====================================
        - Real-time display of employee check-in/check-out status
        - Dashboard showing employees who are present, absent, or checked out
        - Auto-refresh functionality
        - Clean and intuitive interface
    """,
    'author': 'Wokwy (quochuy.software@gmail.com) + supported by claude.ai',
    'website': 'https://www.yourcompany.com',
    'depends': ['base', 'hr', 'hr_attendance', 'web'],
    'data': [
        'security/ir.model.access.csv',
        'views/attendance_dashboard_views.xml',
        'views/menu_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'employee_attendance_realtime/static/src/js/attendance_dashboard.js',
            'employee_attendance_realtime/static/src/css/attendance_dashboard.css',
            'employee_attendance_realtime/static/src/xml/attendance_dashboard.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}