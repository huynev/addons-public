from odoo import models, fields, api
from datetime import datetime
import logging

_logger = logging.getLogger(__name__)


class ZktecoDevice(models.Model):
    _name = 'zkteco.device'
    _description = 'ZKTeco Attendance Device'
    _rec_name = 'device_name'

    device_name = fields.Char('Device Name', required=True)
    device_serial = fields.Char('Serial Number', required=True, unique=True)
    device_ip = fields.Char('IP Address')
    device_port = fields.Integer('Port', default=4370)
    location = fields.Char('Location')
    is_active = fields.Boolean('Active', default=True)
    connection_status = fields.Selection([
        ('connected', 'Connected'),
        ('disconnected', 'Disconnected'),
        ('error', 'Error')
    ], string='Status', default='disconnected')
    last_activity = fields.Datetime('Last Activity')

    # Statistics
    total_records = fields.Integer('Total Records', compute='_compute_statistics')
    today_records = fields.Integer('Today Records', compute='_compute_statistics')

    # Commands relationship
    command_ids = fields.One2many('zkteco.device.command', 'device_id', 'Commands')

    @api.depends('device_serial')
    def _compute_statistics(self):
        for device in self:
            # Count total attendance records
            total = self.env['hr.attendance'].search_count([
                ('device_serial', '=', device.device_serial)
            ])

            # Count today's records
            today = fields.Date.today()
            today_count = self.env['hr.attendance'].search_count([
                ('device_serial', '=', device.device_serial),
                ('attendance_timestamp', '>=', today),
                ('attendance_timestamp', '<', fields.Datetime.now().replace(hour=23, minute=59, second=59))
            ])

            device.total_records = total
            device.today_records = today_count

    def action_connect(self):
        """Mark device as connected"""
        self.write({
            'connection_status': 'connected',
            'last_activity': fields.Datetime.now()
        })

    def action_disconnect(self):
        """Mark device as disconnected"""
        self.write({
            'connection_status': 'disconnected'
        })

    def get_pending_commands(self):
        """Get pending commands for the device"""
        commands = self.env['zkteco.device.command'].search([
            ('device_id', '=', self.id),
            ('status', '=', 'pending'),
            ('scheduled_time', '<=', fields.Datetime.now())
        ], order='priority desc, create_date asc', limit=1)

        if commands:
            command = commands[0]
            # Mark as sent
            command.write({
                'status': 'sent',
                'sent_time': fields.Datetime.now()
            })
            _logger.info("Sending command to device %s: %s", self.device_serial, command.command)
            return command.command

        return ''

    def send_command(self, command, priority=5):
        """Send command to device"""
        self.env['zkteco.device.command'].create({
            'device_id': self.id,
            'command': command,
            'priority': priority,
            'status': 'pending',
            'scheduled_time': fields.Datetime.now()
        })

    def restart_device(self):
        """Send restart command to device"""
        self.send_command('RESTART', priority=10)

    def clear_data(self):
        """Send clear data command to device"""
        self.send_command('CLEAR DATA', priority=8)

    def sync_time(self):
        """Send time sync command to device"""
        current_time = fields.Datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.send_command(f'SET TIME {current_time}', priority=3)

    def process_attendance_data(self, serial_number, records):
        """Process attendance data (legacy method for compatibility)"""
        _logger.info("Processing %d attendance records for device %s", len(records), serial_number)
        # This method is called from the old code
        # The actual processing is now done in the controller
        return True

class ZktecoUnknownAttendance(models.Model):
    _name = 'zkteco.unknown.attendance'
    _description = 'Unknown Attendance Records'
    _order = 'timestamp desc'

    device_serial = fields.Char('Device Serial', required=True)
    device_user_id = fields.Char('Device User ID', required=True)
    timestamp = fields.Datetime('Timestamp', required=True)
    status = fields.Char('Status')
    processed = fields.Boolean('Processed', default=False)
    notes = fields.Text('Notes')
    employee_id = fields.Many2one('hr.employee', 'Assigned Employee')

    def action_assign_employee(self):
        """Open wizard to assign employee to unknown attendance"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Assign Employee',
            'res_model': 'zkteco.assign.employee.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_unknown_attendance_id': self.id,
                'default_device_user_id': self.device_user_id
            }
        }

    def action_ignore(self):
        """Mark as processed without creating attendance record"""
        self.write({
            'processed': True,
            'notes': (self.notes or '') + '\nMarked as ignored on ' + str(fields.Datetime.now())
        })


class ZktecoAssignEmployeeWizard(models.TransientModel):
    _name = 'zkteco.assign.employee.wizard'
    _description = 'Assign Employee to Unknown Attendance'

    unknown_attendance_id = fields.Many2one('zkteco.unknown.attendance', 'Unknown Attendance')
    device_user_id = fields.Char('Device User ID')
    employee_id = fields.Many2one('hr.employee', 'Employee', required=True)
    update_employee_device_id = fields.Boolean('Update Employee Device ID', default=True)
    create_attendance_record = fields.Boolean('Create Attendance Record', default=True)

    def action_assign(self):
        """Assign employee and create attendance record"""
        unknown_attendance = self.unknown_attendance_id

        # Update employee device ID if requested
        if self.update_employee_device_id:
            self.employee_id.attendance_device_id = self.device_user_id

        # Create attendance record if requested
        if self.create_attendance_record:
            # Get the date of the attendance timestamp
            attendance_date = unknown_attendance.timestamp.date()

            # Search for existing attendance record on the same date
            existing_attendance = self.env['hr.attendance'].search([
                ('employee_id', '=', self.employee_id.id),
                ('attendance_timestamp', '>=', attendance_date.strftime('%Y-%m-%d 00:00:00')),
                ('attendance_timestamp', '<=', attendance_date.strftime('%Y-%m-%d 23:59:59')),
            ], limit=1, order='create_date desc')

            if not existing_attendance:
                # No existing record for today - create new record with check_in
                attendance_data = {
                    'employee_id': self.employee_id.id,
                    'attendance_timestamp': unknown_attendance.timestamp,
                    'device_serial': unknown_attendance.device_serial,
                    'raw_data': f"Manual assignment from unknown attendance ID: {unknown_attendance.id}",
                    'check_in': unknown_attendance.timestamp,
                }
                self.env['hr.attendance'].create(attendance_data)

            else:
                # Existing record found - update with check_out
                existing_attendance.write({
                    'check_out': unknown_attendance.timestamp,
                    'raw_data': (existing_attendance.raw_data or '') +
                                f"\nCheck-out updated from unknown attendance ID: {unknown_attendance.id}"
                })

        # Mark unknown attendance as processed
        unknown_attendance.write({
            'processed': True,
            'employee_id': self.employee_id.id,
            'notes': (
                                 unknown_attendance.notes or '') + f'\nAssigned to {self.employee_id.name} on {fields.Datetime.now()}'
        })

        return {'type': 'ir.actions.act_window_close'}


class ZktecoDeviceCommand(models.Model):
    _name = 'zkteco.device.command'
    _description = 'ZKTeco Device Commands'
    _order = 'priority desc, create_date desc'

    device_id = fields.Many2one('zkteco.device', 'Device', required=True, ondelete='cascade')
    command = fields.Text('Command', required=True)
    priority = fields.Integer('Priority', default=5, help='Higher number = higher priority')
    status = fields.Selection([
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('confirmed', 'Confirmed'),
        ('failed', 'Failed'),
        ('expired', 'Expired')
    ], string='Status', default='pending')

    scheduled_time = fields.Datetime('Scheduled Time', default=fields.Datetime.now)
    sent_time = fields.Datetime('Sent Time')
    confirmed_time = fields.Datetime('Confirmed Time')

    notes = fields.Text('Notes')
    retry_count = fields.Integer('Retry Count', default=0)
    max_retries = fields.Integer('Max Retries', default=3)

    def action_retry(self):
        """Retry sending the command"""
        if self.retry_count < self.max_retries:
            self.write({
                'status': 'pending',
                'retry_count': self.retry_count + 1,
                'scheduled_time': fields.Datetime.now()
            })
        else:
            self.write({'status': 'failed'})

    def action_confirm(self):
        """Mark command as confirmed"""
        self.write({
            'status': 'confirmed',
            'confirmed_time': fields.Datetime.now()
        })

    @api.model
    def cleanup_expired_commands(self):
        """Clean up expired commands (older than 1 hour and still pending)"""
        from datetime import timedelta

        one_hour_ago = fields.Datetime.now() - timedelta(hours=1)
        expired_commands = self.search([
            ('status', '=', 'pending'),
            ('scheduled_time', '<', one_hour_ago)
        ])

        expired_commands.write({'status': 'expired'})