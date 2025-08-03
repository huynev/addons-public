{
    'name': 'HR Attendance Report',
    'version': '17.0.1.0.0',
    'category': 'Human Resources',
    'summary': 'Monthly Attendance Report with Excel Export',
    'description': """
        Xuất báo cáo chấm công theo tháng với format Excel tùy chỉnh.
        - Chọn tháng/năm để xuất báo cáo
        - Hiển thị dữ liệu chấm công từ hr_attendance
        - Highlight các ngày không có dữ liệu
        - Xuất Excel với format chuẩn
    """,
    'author': 'Wokwy (quochuy.software@gmail.com) +  Support by Claude.ai',
    'depends': ['hr', 'hr_attendance'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/hr_attendance_monthly_report_views.xml',
        'wizard/attendance_report_wizard.xml',
        'report/hr_attendance_monthly_report_templates.xml',
        'report/hr_attendance_monthly_report.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
    'license': 'LGPL-3',
}