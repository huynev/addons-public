from odoo import models, fields, api
from datetime import datetime, timedelta
import logging
import pytz

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

    def _convert_timestamp_to_utc(self, timestamp_obj):
        """Convert timestamp from device timezone to UTC for Odoo storage"""
        try:
            # Get user's timezone (device timezone)
            user_tz = self.env.context.get('tz') or self.env.user.tz or 'Asia/Ho_Chi_Minh'

            if pytz:
                try:
                    # Use pytz for accurate timezone conversion
                    user_timezone = pytz.timezone(user_tz)
                    if timestamp_obj.tzinfo is None:
                        # Localize naive datetime to user's timezone
                        local_timestamp = user_timezone.localize(timestamp_obj)
                    else:
                        # Convert to user's timezone first
                        local_timestamp = timestamp_obj.astimezone(user_timezone)

                    # Convert to UTC for Odoo storage
                    utc_timestamp = local_timestamp.astimezone(pytz.UTC).replace(tzinfo=None)
                    return utc_timestamp
                except Exception as e:
                    _logger.warning("Error using pytz for timezone conversion: %s", e)

            # Fallback: Manual timezone offset for Vietnam (UTC+7)
            if user_tz in ['Asia/Ho_Chi_Minh', 'Asia/Saigon'] or user_tz.startswith('GMT+7'):
                # Device time is UTC+7, convert to UTC by subtracting 7 hours
                utc_timestamp = timestamp_obj - timedelta(hours=7)
            elif user_tz.startswith('GMT+'):
                # Extract offset and convert
                try:
                    offset = int(user_tz.replace('GMT+', ''))
                    utc_timestamp = timestamp_obj - timedelta(hours=offset)
                except:
                    utc_timestamp = timestamp_obj  # Use as-is if can't parse
            elif user_tz.startswith('GMT-'):
                # Extract offset and convert
                try:
                    offset = int(user_tz.replace('GMT-', ''))
                    utc_timestamp = timestamp_obj + timedelta(hours=offset)
                except:
                    utc_timestamp = timestamp_obj  # Use as-is if can't parse
            else:
                # Default: assume device time is UTC+7 (Vietnam)
                utc_timestamp = timestamp_obj - timedelta(hours=7)

            return utc_timestamp

        except Exception as e:
            _logger.error("Error converting timestamp %s to UTC: %s", timestamp_obj, e)
            return timestamp_obj

    def action_assign(self):
        """Assign employee and create attendance record with improved logic"""
        unknown_attendance = self.unknown_attendance_id

        # Update employee device ID if requested
        if self.update_employee_device_id:
            self.employee_id.attendance_device_id = self.device_user_id

        # Create attendance record if requested
        if self.create_attendance_record:
            try:
                # Get the timestamp from unknown attendance (stored as UTC in database)
                utc_timestamp_from_db = unknown_attendance.timestamp

                # Convert UTC timestamp back to local timezone to get correct local date
                user_tz = self.env.context.get('tz') or self.env.user.tz or 'Asia/Ho_Chi_Minh'

                if pytz:
                    try:
                        # Convert UTC to local time to get correct date
                        utc_tz = pytz.UTC
                        user_timezone = pytz.timezone(user_tz)
                        utc_aware = utc_tz.localize(utc_timestamp_from_db)
                        local_timestamp = utc_aware.astimezone(user_timezone).replace(tzinfo=None)
                    except Exception as e:
                        _logger.warning("Error using pytz for timezone conversion: %s", e)
                        # Fallback: add 7 hours for Vietnam timezone
                        local_timestamp = utc_timestamp_from_db + timedelta(hours=7)
                else:
                    # Fallback: add 7 hours for Vietnam timezone (UTC+7)
                    local_timestamp = utc_timestamp_from_db + timedelta(hours=7)

                # Get local date for searching
                local_date = local_timestamp.date()

                # Use the UTC timestamp as-is for storage (it's already in UTC)
                utc_timestamp = utc_timestamp_from_db

                _logger.debug("Processing unknown attendance - UTC from DB: %s, Converted local: %s, Local date: %s",
                              utc_timestamp_from_db, local_timestamp, local_date)

                # Calculate start and end of day in device timezone, then convert to UTC for search
                local_start_of_day = datetime.combine(local_date, datetime.min.time())
                local_end_of_day = datetime.combine(local_date, datetime.max.time())

                # Convert local day boundaries to UTC for database search
                utc_start_of_day = self._convert_timestamp_to_utc(local_start_of_day)
                utc_end_of_day = self._convert_timestamp_to_utc(local_end_of_day)

                _logger.debug("Search range - Local: %s to %s, UTC: %s to %s",
                              local_start_of_day, local_end_of_day, utc_start_of_day, utc_end_of_day)

                # Search for existing attendance record on the same day (using UTC boundaries)
                existing_attendance = self.env['hr.attendance'].search([
                    ('employee_id', '=', self.employee_id.id),
                    ('check_in', '>=', utc_start_of_day),
                    ('check_in', '<=', utc_end_of_day),
                ], limit=1)

                if not existing_attendance:
                    # No attendance record for today - Create new record with check_in = timestamp
                    attendance_data = {
                        'employee_id': self.employee_id.id,
                        'check_in': utc_timestamp,
                        'device_serial': unknown_attendance.device_serial,
                        'raw_data': f"Manual assignment from unknown attendance ID: {unknown_attendance.id} - Local time: {local_timestamp}",
                    }
                    self.env['hr.attendance'].create(attendance_data)
                    _logger.info("Created new attendance record for employee %s with check-in at %s (local: %s)",
                                 self.employee_id.name, utc_timestamp, local_timestamp)
                else:
                    # Already has attendance record for today - Update based on timestamp
                    current_check_in = existing_attendance.check_in
                    current_check_out = existing_attendance.check_out
                    updated = False
                    update_data = {}
                    update_message = []

                    # Check if timestamp should be the new check_in (earliest time)
                    if utc_timestamp < current_check_in:
                        update_data['check_in'] = utc_timestamp
                        update_message.append(
                            f"Updated check-in to earlier time: {utc_timestamp} (local: {local_timestamp})")
                        updated = True

                    # Check if timestamp should be the new check_out (latest time)
                    if not current_check_out or utc_timestamp > current_check_out:
                        # Only update check_out if timestamp is after check_in
                        final_check_in = update_data.get('check_in', current_check_in)
                        if utc_timestamp > final_check_in:
                            update_data['check_out'] = utc_timestamp
                            update_message.append(
                                f"Updated check-out to later time: {utc_timestamp} (local: {local_timestamp})")
                            updated = True
                        else:
                            _logger.warning("Timestamp %s (local: %s) is not after check-in %s for employee %s",
                                            utc_timestamp, local_timestamp, final_check_in, self.employee_id.name)

                    if updated:
                        # Update raw_data to include manual assignment information
                        current_raw_data = existing_attendance.raw_data or ''
                        update_data[
                            'raw_data'] = current_raw_data + f"\nManual assignment: {'; '.join(update_message)} - from unknown attendance ID: {unknown_attendance.id}"

                        existing_attendance.write(update_data)
                        _logger.info("Updated attendance record for employee %s: %s",
                                     self.employee_id.name, '; '.join(update_message))
                    else:
                        # Timestamp doesn't extend the attendance period
                        _logger.info(
                            "Timestamp %s (local: %s) for employee %s is within existing attendance period (%s - %s), no update needed",
                            utc_timestamp, local_timestamp, self.employee_id.name, current_check_in,
                            current_check_out or 'No checkout')
            except Exception as e:
                _logger.error("Error creating attendance record from unknown attendance ID %s: %s",
                              unknown_attendance.id, e)

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