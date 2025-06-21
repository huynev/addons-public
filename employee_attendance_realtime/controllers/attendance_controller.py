from odoo import http
from odoo.http import request
import json


class AttendanceController(http.Controller):

    @http.route('/attendance/dashboard/data', type='json', auth='user', methods=['POST'])
    def get_attendance_dashboard_data(self):
        """API endpoint to get real-time attendance data"""
        dashboard = request.env['attendance.dashboard']
        return dashboard.get_attendance_data()