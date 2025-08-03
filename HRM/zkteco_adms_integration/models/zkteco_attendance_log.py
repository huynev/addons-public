from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import logging
import re
from datetime import datetime, timedelta
try:
    import pytz
except ImportError:
    pytz = None


_logger = logging.getLogger(__name__)


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
    reprocessed = fields.Boolean('Reprocessed', default=False, help="Indicates if this log has been reprocessed")
    reprocess_count = fields.Integer('Reprocess Count', default=0)
    last_reprocess_date = fields.Datetime('Last Reprocess Date')

    @api.model
    def log_processing(self, device_serial, raw_data, processed_count=0, error_msg=None, processing_time=0,
                       status=None):
        return self.create({
            'device_serial': device_serial,
            'raw_data': raw_data if raw_data else '',
            'processed_records': processed_count,
            'error_message': error_msg,
            'processing_time': processing_time,
            'status': status
        })

    def action_reprocess_attendance(self):
        """Action to reprocess attendance data for selected records"""
        if not self:
            raise UserError(_("Please select at least one record to reprocess."))

        reprocessed_count = 0
        total_processed_records = 0
        errors = []

        for log_record in self:
            try:
                if not log_record.raw_data:
                    errors.append(f"Log ID {log_record.id}: No raw data to reprocess")
                    continue

                if not log_record.device_serial:
                    errors.append(f"Log ID {log_record.id}: No device serial found")
                    continue

                # Find the device
                device = self.env['zkteco.device'].search([
                    ('device_serial', '=', log_record.device_serial),
                    ('is_active', '=', True)
                ], limit=1)

                if not device:
                    errors.append(f"Log ID {log_record.id}: Device {log_record.device_serial} not found")
                    continue

                # Process the attendance data
                processed_count = self._reprocess_attendance_data(device, log_record.raw_data)

                # Update the log record
                log_record.write({
                    'reprocessed': True,
                    'reprocess_count': log_record.reprocess_count + 1,
                    'last_reprocess_date': fields.Datetime.now(),
                    'processed_records': log_record.processed_records + processed_count,
                    'status': 'success' if processed_count > 0 else 'partial'
                })

                total_processed_records += processed_count
                reprocessed_count += 1

            except Exception as e:
                error_msg = f"Log ID {log_record.id}: {str(e)}"
                errors.append(error_msg)
                _logger.error(f"Error reprocessing log {log_record.id}: {e}")

        # Show result message
        if errors:
            error_message = "\n".join(errors)
            if reprocessed_count > 0:
                message = _(
                    f"Reprocessed {reprocessed_count} logs with {total_processed_records} attendance records.\n\nErrors:\n{error_message}")
            else:
                message = _(f"Failed to reprocess logs:\n{error_message}")
                raise UserError(message)
        else:
            message = _(
                f"Successfully reprocessed {reprocessed_count} logs with {total_processed_records} attendance records.")

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Reprocess Complete'),
                'message': message,
                'type': 'success' if not errors else 'warning',
                'sticky': True,
            }
        }

    def _reprocess_attendance_data(self, device, data):
        """Reprocess attendance data and create records in Odoo"""
        processed_count = 0

        try:
            # Handle different data formats (same as main.py logic)
            if data.startswith('OPERLOG:') or data.startswith('ATTLOG:'):
                header, content = data.split(':', 1)
                records = self._parse_operlog_format(content)
            else:
                # Try to parse as direct format
                records = self._parse_direct_format(data)

            # Create attendance records
            for record in records:
                if self._create_attendance_record(device, record):
                    processed_count += 1

        except Exception as e:
            _logger.error("Error reprocessing attendance data: %s", e)
            raise ValidationError(_("Error processing data: %s") % str(e))

        return processed_count

    def _parse_operlog_format(self, content):
        """Parse OPERLOG/ATTLOG format data"""
        records = []
        for line in content.strip().split('\n'):
            line = line.strip()
            if not line:
                continue

            record = {}

            # Handle tab-separated format: user_id=1\ttime=2025-05-02 08:30:00\tstatus=0
            if '\t' in line:
                parts = line.split('\t')
                for part in parts:
                    if '=' in part:
                        key, value = part.split('=', 1)
                        if key == 'user_id':
                            record['user_id'] = value
                        elif key in ('time', 'timestamp'):
                            record['timestamp'] = value
                        elif key == 'status':
                            record['status'] = value
            else:
                # Handle space-separated format: 1 101 2024-01-15 09:30:00 1 1 1 0
                parts = line.split()
                if len(parts) >= 4:
                    record['user_id'] = parts[1]
                    record['timestamp'] = f"{parts[2]} {parts[3]}"
                    record['status'] = parts[4] if len(parts) > 4 else '1'

            if record.get('user_id') and record.get('timestamp'):
                records.append(record)

        return records

    def _parse_direct_format(self, data):
        """Parse direct format data"""
        records = []

        lines = data.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue

            record = {}

            # Check if line contains tab characters (tab-separated format)
            if '\t' in line:
                parts = line.split('\t')

                # Tab-separated format: 123456	2025-06-13 16:42:31	255	15	0	0	0	0	0	0
                if len(parts) >= 4:
                    try:
                        user_id = parts[0].strip()  # 123456
                        timestamp_str = parts[1].strip()  # 2025-06-13 16:42:31
                        record_id = parts[2].strip()  # 255
                        status_or_verify = parts[3].strip()  # 15

                        # Additional fields if present
                        work_code = parts[4].strip() if len(parts) > 4 else '0'

                        # Validate timestamp format
                        if self._validate_timestamp(timestamp_str):
                            # Determine actual status
                            if work_code in ['0', '1']:
                                actual_status = work_code  # 0=out, 1=in
                            elif status_or_verify in ['0', '1', '4', '5']:
                                actual_status = status_or_verify
                            else:
                                # Default to check-in if we can't determine
                                actual_status = '1'

                            record = {
                                'user_id': user_id,
                                'timestamp': timestamp_str,
                                'status': actual_status,
                                'record_id': record_id,
                                'verify_type': status_or_verify,
                                'work_code': work_code,
                                'raw_data': line
                            }

                            records.append(record)

                    except (ValueError, IndexError) as e:
                        _logger.warning(f"Error parsing tab-separated line '{line}': {e}")
                        continue

            else:
                # Space-separated format: 1 101 2024-01-15 09:30:00 1 1 1 0
                pattern = r'(\d+)\s+(\d+)\s+(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2})\s+(\d+)'
                match = re.search(pattern, line)

                if match:
                    record = {
                        'user_id': match.group(2),
                        'timestamp': f"{match.group(3)} {match.group(4)}",
                        'status': match.group(5),
                        'record_id': match.group(1),
                        'raw_data': line
                    }
                    records.append(record)
                else:
                    # Pattern for: user_id,timestamp,status
                    comma_pattern = r'(\d+),(\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2}),(\d+)'
                    comma_match = re.search(comma_pattern, line)

                    if comma_match:
                        record = {
                            'user_id': comma_match.group(1),
                            'timestamp': comma_match.group(2),
                            'status': comma_match.group(3),
                            'raw_data': line
                        }
                        records.append(record)

        return records

    def _convert_timestamp_to_utc(self, timestamp_str_or_obj):
        """Convert timestamp from device timezone to UTC for Odoo storage"""
        try:
            # Parse string to datetime if needed
            if isinstance(timestamp_str_or_obj, str):
                formats = ['%Y-%m-%d %H:%M:%S', '%d/%m/%Y %H:%M:%S', '%Y/%m/%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S']
                naive_timestamp = None
                for fmt in formats:
                    try:
                        naive_timestamp = datetime.strptime(timestamp_str_or_obj, fmt)
                        break
                    except ValueError:
                        continue

                if naive_timestamp is None:
                    raise ValueError(f"Unable to parse timestamp: {timestamp_str_or_obj}")
            else:
                naive_timestamp = timestamp_str_or_obj

            # Get user's timezone (device timezone)
            user_tz = self.env.context.get('tz') or self.env.user.tz or 'Asia/Ho_Chi_Minh'

            if pytz:
                try:
                    # Use pytz for accurate timezone conversion
                    user_timezone = pytz.timezone(user_tz)
                    if naive_timestamp.tzinfo is None:
                        # Localize naive datetime to user's timezone
                        local_timestamp = user_timezone.localize(naive_timestamp)
                    else:
                        # Convert to user's timezone first
                        local_timestamp = naive_timestamp.astimezone(user_timezone)

                    # Convert to UTC for Odoo storage
                    utc_timestamp = local_timestamp.astimezone(pytz.UTC).replace(tzinfo=None)
                    return utc_timestamp
                except Exception as e:
                    _logger.warning("Error using pytz for timezone conversion: %s", e)

            # Fallback: Manual timezone offset for Vietnam (UTC+7)
            if user_tz in ['Asia/Ho_Chi_Minh', 'Asia/Saigon'] or user_tz.startswith('GMT+7'):
                # Device time is UTC+7, convert to UTC by subtracting 7 hours
                utc_timestamp = naive_timestamp - timedelta(hours=7)
            elif user_tz.startswith('GMT+'):
                # Extract offset and convert
                try:
                    offset = int(user_tz.replace('GMT+', ''))
                    utc_timestamp = naive_timestamp - timedelta(hours=offset)
                except:
                    utc_timestamp = naive_timestamp  # Use as-is if can't parse
            elif user_tz.startswith('GMT-'):
                # Extract offset and convert
                try:
                    offset = int(user_tz.replace('GMT-', ''))
                    utc_timestamp = naive_timestamp + timedelta(hours=offset)
                except:
                    utc_timestamp = naive_timestamp  # Use as-is if can't parse
            else:
                # Default: assume device time is UTC+7 (Vietnam)
                utc_timestamp = naive_timestamp - timedelta(hours=7)

            return utc_timestamp

        except Exception as e:
            _logger.error("Error converting timestamp %s to UTC: %s", timestamp_str_or_obj, e)
            # Return original timestamp as fallback
            if isinstance(timestamp_str_or_obj, str):
                return datetime.strptime(timestamp_str_or_obj, '%Y-%m-%d %H:%M:%S')
            return timestamp_str_or_obj

    def _validate_timestamp(self, timestamp_str):
        """Validate timestamp format"""
        try:
            formats = [
                '%Y-%m-%d %H:%M:%S',
                '%d/%m/%Y %H:%M:%S',
                '%Y/%m/%d %H:%M:%S',
                '%Y-%m-%dT%H:%M:%S'
            ]

            for fmt in formats:
                try:
                    datetime.strptime(timestamp_str, fmt)
                    return True
                except ValueError:
                    continue

            return False
        except:
            return False

    def _is_night_shift_employee(self, employee):
        """
        Check if employee is assigned to night shift calendar
        Night shift is detected by working hours that span across midnight (18:00-06:00 pattern)
        """
        try:
            if not employee:
                return False

            # Get employee's resource calendar
            calendar = employee.resource_calendar_id
            if not calendar:
                return False

            # Check working times to detect night shift pattern
            working_times = calendar.attendance_ids
            if not working_times:
                return False

            # Look for night shift patterns:
            # 1. Working hours starting from 18:00+ (6 PM or later)
            # 2. Working hours ending at 06:00 or early morning (before 8 AM)
            has_evening_hours = False
            has_early_morning_hours = False

            for working_time in working_times:
                hour_from = working_time.hour_from
                hour_to = working_time.hour_to

                # Check for evening start (18:00 or later)
                if hour_from >= 18.0:  # 18:00 or later
                    has_evening_hours = True

                # Check for early morning end (06:00 or earlier, or hour_to > 24 indicating next day)
                if hour_to <= 6.0 or hour_to >= 24.0:  # 06:00 or earlier, or next day
                    has_early_morning_hours = True

            # Night shift detected if has both evening start and early morning end
            is_night_shift = has_evening_hours and has_early_morning_hours

            _logger.debug("Employee %s calendar check - Evening hours: %s, Early morning hours: %s, Night shift: %s",
                          employee.name, has_evening_hours, has_early_morning_hours, is_night_shift)

            return is_night_shift

        except Exception as e:
            _logger.error("Error checking night shift for employee %s: %s", employee.name if employee else 'Unknown', e)
            return False

    def _get_night_shift_date(self, local_timestamp, is_night_shift_employee):
        """
        Determine which shift date this timestamp belongs to

        For night shift employees:
        - Times around 12:00 (00:00-12:00): End of night shift → shift begins from PREVIOUS date
        - Times around 12:01 (12:01-23:59): Start of night shift → shift begins from CURRENT date

        For regular employees:
        - All times belong to current date

        Returns: (shift_begin_date, is_continuation_of_previous_shift)
        """
        local_time = local_timestamp.time()
        local_date = local_timestamp.date()

        if not is_night_shift_employee:
            # Regular employees: all times belong to current date
            return local_date, False

        # Night shift logic
        if local_time >= datetime.strptime('00:00:00', '%H:%M:%S').time() and local_time <= datetime.strptime(
                '12:00:00', '%H:%M:%S').time():
            # Early morning (00:00-12:00): End of night shift that BEGAN from PREVIOUS day
            shift_begin_date = local_date - timedelta(days=1)
            return shift_begin_date, True
        else:
            # Evening/day time (12:01-23:59): Night shift that BEGINS from CURRENT day
            shift_begin_date = local_date
            return shift_begin_date, False

    def _create_attendance_record(self, device, record_data):
        """
        Create attendance record in Odoo with proper night shift handling

        Night shift format:
        - Check-in: 29/07/2025 17:47:22 (evening start)
        - Check-out: 30/07/2025 06:02:22 (morning end)
        - Both recorded in SAME attendance record for date 29/07/2025
        """
        try:
            user_id = record_data.get('user_id')
            timestamp_str = record_data.get('timestamp')
            status = record_data.get('status', '1')

            if not user_id or not timestamp_str:
                _logger.warning("Incomplete attendance record: %s", record_data)
                return False

            # Find employee by device user ID
            employee = self.env['hr.employee'].search([
                ('attendance_device_id', '=', user_id)
            ], limit=1)

            if not employee:
                _logger.warning("Employee not found for device user ID: %s", user_id)
                self._log_unknown_employee(device, user_id, timestamp_str, status)
                return False

            # Parse timestamp
            try:
                if isinstance(timestamp_str, str):
                    formats = ['%Y-%m-%d %H:%M:%S', '%d/%m/%Y %H:%M:%S', '%Y/%m/%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S']
                    local_timestamp = None
                    for fmt in formats:
                        try:
                            local_timestamp = datetime.strptime(timestamp_str, fmt)
                            break
                        except ValueError:
                            continue

                    if local_timestamp is None:
                        raise ValueError(f"Unable to parse timestamp: {timestamp_str}")
                else:
                    local_timestamp = timestamp_str

                # Convert timestamp to UTC for storage
                timestamp = self._convert_timestamp_to_utc(timestamp_str)
                _logger.debug("Processing timestamp - Local: %s, UTC: %s", local_timestamp, timestamp)

            except Exception as e:
                _logger.error("Error parsing timestamp %s: %s", timestamp_str, e)
                return False

            # Check if this employee is on night shift schedule
            is_night_shift_employee = self._is_night_shift_employee(employee)

            # Determine which shift date this timestamp belongs to
            shift_begin_date, is_night_continuation = self._get_night_shift_date(local_timestamp,
                                                                                 is_night_shift_employee)

            _logger.debug(
                "Employee %s (%s schedule): Timestamp %s → Night shift begins from date %s (continuation: %s)",
                employee.name, 'Night' if is_night_shift_employee else 'Regular',
                local_timestamp, shift_begin_date, is_night_continuation)

            # Calculate search boundaries in LOCAL time first, then convert to UTC
            if is_night_shift_employee:
                local_shift_start = datetime.combine(shift_begin_date, datetime.min.time())
                local_shift_end = datetime.combine(shift_begin_date + timedelta(days=1),
                                                   datetime.strptime('12:00:00', '%H:%M:%S').time())
            else:
                # Regular employees: search within the same day
                local_shift_start = datetime.combine(shift_begin_date, datetime.min.time())  # 00:00 of begin date
                local_shift_end = datetime.combine(shift_begin_date + timedelta(days=1),
                                                   datetime.strptime('02:00:00', '%H:%M:%S').time()) # next day 03:00:00 of begin date

            # Convert LOCAL shift boundaries to UTC for database search
            # This is critical because hr.attendance stores all timestamps in UTC
            utc_shift_start = self._convert_timestamp_to_utc(local_shift_start)
            utc_shift_end = self._convert_timestamp_to_utc(local_shift_end)

            _logger.debug("Search range for %s employee %s (shift begins from %s):",
                          'Night' if is_night_shift_employee else 'Regular', employee.name, shift_begin_date)
            _logger.debug("  Local range: %s to %s", local_shift_start, local_shift_end)
            _logger.debug("  UTC range: %s to %s", utc_shift_start, utc_shift_end)
            _logger.debug("  Current timestamp - Local: %s, UTC: %s", local_timestamp, timestamp)

            # Search for existing attendance record in this shift period
            existing_record = self.env['hr.attendance'].search([
                ('employee_id', '=', employee.id),
                ('check_in', '>=', utc_shift_start),
                ('check_in', '<=', utc_shift_end),
            ], limit=1)

            if not existing_record:
                # No existing record - Create new attendance record
                attendance_record = self.env['hr.attendance'].create({
                    'employee_id': employee.id,
                    'check_in': timestamp,
                    'device_id': device.id if hasattr(device, 'id') else False,
                    'device_serial': device.device_serial if hasattr(device, 'device_serial') else '',
                    'raw_data': f"Reprocessed - New {'night' if is_night_shift_employee else 'regular'} shift record (shift begins from: {shift_begin_date}): {record_data}",
                })

                _logger.info(
                    "Created new attendance record for %s employee %s - Check-in: %s (Local: %s, Shift begins from: %s)",
                    'night shift' if is_night_shift_employee else 'regular',
                    employee.name, timestamp, local_timestamp, shift_begin_date)
                return True

            else:
                # Existing record found - Update check-in or check-out appropriately
                current_check_in = existing_record.check_in
                current_check_out = existing_record.check_out
                updated = False
                update_data = {}
                update_message = []

                # Logic for updating existing record
                if timestamp < current_check_in:
                    # This is an earlier time - should be new check-in
                    update_data['check_in'] = timestamp
                    update_data['check_out'] = current_check_in
                    update_message.append(f"Updated check-in to earlier time: {timestamp} (Local: {local_timestamp})")
                    updated = True

                elif timestamp > current_check_in:
                    # This is a later time
                    if not current_check_out:
                        # No check-out yet - this becomes check-out
                        update_data['check_out'] = timestamp
                        update_message.append(f"Set check-out: {timestamp} (Local: {local_timestamp})")
                        updated = True
                    elif timestamp > current_check_out:
                        # Later than current check-out - update check-out
                        update_data['check_out'] = timestamp
                        update_message.append(
                            f"Updated check-out to later time: {timestamp} (Local: {local_timestamp})")
                        updated = True
                    else:
                        # Timestamp is between check-in and check-out - no update needed
                        _logger.info(
                            "Timestamp %s (local: %s) for employee %s is between existing check-in (%s) and check-out (%s), no update needed (Shift begins from: %s)",
                            timestamp, local_timestamp, employee.name, current_check_in, current_check_out,
                            shift_begin_date)
                else:
                    # Exact same time as check-in - duplicate, no update needed
                    _logger.info(
                        "Duplicate check-in timestamp %s for employee %s, no update needed (Shift begins from: %s)",
                        timestamp, employee.name, shift_begin_date)

                if updated:
                    # Update the record
                    current_raw_data = existing_record.raw_data or ''
                    schedule_type = 'Night' if is_night_shift_employee else 'Regular'
                    update_data[
                        'raw_data'] = current_raw_data + f"\nReprocessed ({schedule_type} schedule, shift begins from: {shift_begin_date}): {'; '.join(update_message)} - {record_data}"

                    existing_record.write(update_data)
                    _logger.info("Updated attendance record for %s employee %s: %s (Shift begins from: %s)",
                                 'night shift' if is_night_shift_employee else 'regular',
                                 employee.name, '; '.join(update_message), shift_begin_date)
                    return True
                else:
                    return False

        except Exception as e:
            _logger.error("Error creating attendance record for %s: %s", record_data, e)
            return False

    def _log_unknown_employee(self, device, user_id, timestamp, status):
        """Log attendance for unknown employees for manual review"""
        try:
            utc_timestamp = self._convert_timestamp_to_utc(timestamp)
            device_serial = device.device_serial if hasattr(device, 'device_serial') else ''
            existing_record = self.env['zkteco.unknown.attendance'].search([
                ('device_serial', '=', device_serial),
                ('device_user_id', '=', user_id),
                ('timestamp', '=', utc_timestamp),
            ], limit=1)

            if existing_record:
                _logger.debug("Unknown employee attendance already exists for user ID %s at %s, skipping duplicate",
                              user_id, utc_timestamp)

                # Update existing record with additional notes if needed
                current_notes = existing_record.notes or ''
                if f"from reprocess" not in current_notes:
                    existing_record.write({
                        'notes': current_notes + f"\nDuplicate attempt from reprocess at {fields.Datetime.now()}"
                    })

                return existing_record.id

            # Create a log entry for unknown employees if model exists
            self.env['zkteco.unknown.attendance'].create({
                'device_serial': device.device_serial if hasattr(device, 'device_serial') else '',
                'device_user_id': user_id,
                'timestamp': utc_timestamp,
                'status': status,
                'processed': False,
                'notes': f"Unknown employee with device user ID: {user_id} (from reprocess)"
            })
        except Exception as e:
            _logger.error("Error logging unknown employee attendance: %s", e)

    def action_view_attendance_records(self):
        """View attendance records created from this log"""
        self.ensure_one()

        if not self.device_serial:
            raise UserError(_("No device serial found in this log."))

        # Find attendance records that might be related to this log
        domain = [
            ('device_serial', '=', self.device_serial),
            ('create_date', '>=', self.create_date - timedelta(hours=1)),
            ('create_date', '<=', self.create_date + timedelta(hours=1)),
        ]

        return {
            'name': _('Related Attendance Records'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.attendance',
            'view_mode': 'tree,form',
            'domain': domain,
            'context': {'create': False}
        }

    def action_show_raw_data(self):
        """Show raw data in a dialog"""
        self.ensure_one()

        return {
            'name': _('Raw Attendance Data'),
            'type': 'ir.actions.act_window',
            'res_model': 'zkteco.attendance.log',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
            'context': {'form_view_initial_mode': 'readonly'}
        }