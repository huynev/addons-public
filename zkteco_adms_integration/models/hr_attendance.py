from odoo import models, fields, api
from datetime import datetime
import logging

class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    # Add fields for ZKTeco integration
    device_serial = fields.Char('Device Serial')
    device_id = fields.Many2one('zkteco.device', 'Device')
    attendance_timestamp = fields.Datetime('Original Timestamp')
    raw_data = fields.Text('Raw Data')