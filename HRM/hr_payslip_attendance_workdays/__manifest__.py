# -*- coding: utf-8 -*-
{
    'name': 'HR Payslip Attendance Work Days',
    'version': '17.0.1.0.0',
    'category': 'Human Resources/Payroll',
    'summary': 'Calculate WORK100 from actual attendance data based on resource calendar',
    'description': """
HR Payslip Attendance Work Days
===============================

This module calculates the WORK100 (Normal Working Days) based on:
1. Actual attendance data (check-in/check-out records)
2. Resource calendar configuration (full-time/part-time schedules)

Features:
---------
* Calculate worked days only for days with actual attendance
* Respect resource calendar working hours (8h = 1 day, 4h = 0.5 day)
* Support for part-time employees and flexible schedules  
* Automatic integration with existing payroll workflow
* No UI changes - works transparently with standard payslip

How it works:
-------------
1. Checks which days the employee actually attended (has check-in + check-out)
2. For each attendance day, gets expected working hours from resource calendar
3. Converts hours to days (default: 8 hours = 1 day)
4. Sums up the total worked days for WORK100 calculation

Example:
--------
Resource Calendar: Mon-Fri (8h), Sat (4h)
Attendance: Mon, Wed, Thu, Fri, Sat attended
Result: WORK100 = 1+1+1+1+0.5 = 4.5 days
    """,
    'author': 'Wokwy (quochuy.sofware@gmail.com) support by Clause.ai',
    'website': 'https://c2bgroup.net',
    'license': 'LGPL-3',
    'depends': [
        'payroll',
        'hr_attendance',
    ],
    'data': [
    ],
    'external_dependencies': {
        'python': ['pytz'],
    },
    'installable': True,
    'auto_install': False,
    'application': False,
}