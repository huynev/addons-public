from odoo import api, fields, models, _


class ZktecoAttendanceLog(models.Model):
    _name = 'zkteco.attendance.log'
    _description = 'ZKTeco Attendance Processing Log'
    _order = 'create_date desc'

    device_serial = fields.Char('Device Serial')
    raw_data = fields.Text('Raw Data')
    processed_records = fields.Integer('Processed Records')
    error_message = fields.Text('Error Message')
    processing_time = fields.Float('Processing Time (seconds)')
    status = fields.Selection([
        ('success', 'Success'),
        ('partial', 'Partial Success'),
        ('processing', 'Processing'),
        ('error', 'Error'),
    ], string='Status')

    @api.model
    def log_processing(self, device_serial, raw_data, processed_count=0, error_msg=None, processing_time=0, status=None):
        self.create({
            'device_serial': device_serial,
            'raw_data': raw_data[:1000] if raw_data else '',
            'processed_records': processed_count,
            'error_message': error_msg,
            'processing_time': processing_time,
            'status': status
        })