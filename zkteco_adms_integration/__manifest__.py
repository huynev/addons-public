# -*- coding: utf-8 -*-
{
    'name': 'ZKTeco ADMS Integration',
    'version': '1.0',
    'category': 'Human Resources/Attendance',
    'summary': 'Integration with ZKTeco devices using iCloud-ADMS protocol',
    'description': """
ZKTeco ADMS Integration
=======================
This module integrates Odoo HR Attendance with ZKTeco biometric devices using the iCloud-ADMS protocol.
Features:
- Receive attendance data pushed from ZKTeco devices
- Automatic synchronization of employee data
- Real-time attendance monitoring
- Support for multiple devices
- No need for static IP configuration
""",
    'author': 'Wokwy (quochuy.software@gmail.com) support by Claude.ai',
    'website': 'https://www.c2bgroup.net',
    'depends': ['base_setup', 'hr_attendance'],
    'external_dependencies': {
        'python': ['pyzk'],
    },
    'data': [
        'security/ir.model.access.csv',
        'views/zkteco_device_view.xml',
        'views/hr_employee_view.xml',
        'views/zkteco_attendance_log_view.xml',
        'views/menu_views.xml',
    ],
    'demo': [],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}