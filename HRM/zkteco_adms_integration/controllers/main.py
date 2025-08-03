# -*- coding: utf-8 -*-
from odoo import http, fields
from odoo.http import request
import json
import logging
import werkzeug
from datetime import datetime, timedelta
import re
import time
import pytz
from datetime import timezone

_logger = logging.getLogger(__name__)


class ZKTecoADMSController(http.Controller):

    @http.route('/iclock/getrequest', type='http', auth='none', csrf=False, methods=['GET'])
    def get_request(self, **kwargs):
        """Handle GET request from ZKTeco device

        The device sends a request like:
        GET /iclock/getrequest?SN=XXXXXXXXXX&INFO=xxxx

        We need to respond with commands for the device or server information
        """
        try:
            serial_number = kwargs.get('SN')
            info = kwargs.get('INFO')

            if not serial_number:
                _logger.warning("Missing serial number in getrequest")
                return 'ERROR: Missing serial number'

            _logger.info("Received getrequest from device: %s (INFO: %s)", serial_number, info)

            # Find or create the device
            device = request.env['zkteco.device'].sudo().search([
                ('device_serial', '=', serial_number),
                ('is_active', '=', True)
            ], limit=1)

            if not device:
                device = request.env['zkteco.device'].sudo().create({
                    'device_name': f'Auto-created Device {serial_number}',
                    'device_serial': serial_number,
                    'location': 'Auto-detected',
                    'is_active': True,
                    'connection_status': 'connected'
                })
                _logger.info("Auto-created device: %s", serial_number)

            # Update device status to connected
            device.sudo().write({
                'last_activity': fields.Datetime.now(),
                'connection_status': 'connected'
            })

            # Handle different types of requests based on INFO parameter
            if info:
                if info.startswith('TimeZone'):
                    return 'TimeZone=7'
                elif info.startswith('TransTimes'):
                    return 'TransTimes=00:00;14:05'
                elif info.startswith('Stamp'):
                    return 'Stamp=9999'

            # Return any pending commands for the device
            pending_commands = device.sudo().get_pending_commands()
            if pending_commands:
                return pending_commands

            # Default successful response
            return 'OK'

        except Exception as e:
            _logger.error("Error in ZKTeco getrequest: %s", e)
            return 'ERROR: Internal server error'

    @http.route('/iclock/cdata', type='http', auth='none', csrf=False, methods=['GET', 'POST'])
    def cdata(self, **post):
        """Handle attendance data from ZKTeco device

        The device sends different types of requests:
        1. Handshake/Connection check (GET with parameters, no data)
        2. Actual attendance data (POST with data)

        Parameters from device:
        - SN: Serial Number
        - options: Device options
        - language: Language code
        - pushver: Push protocol version
        - DeviceType: Type of device (att = attendance)
        - PushOptionsFlag: Push options flag
        """
        start_time = time.time()

        try:
            # Get parameters from both POST data and GET args
            serial_number = post.get('SN') or request.httprequest.args.get('SN')
            options = post.get('options') or request.httprequest.args.get('options')
            language = post.get('language') or request.httprequest.args.get('language')
            pushver = post.get('pushver') or request.httprequest.args.get('pushver')
            device_type = post.get('DeviceType') or request.httprequest.args.get('DeviceType')
            push_options_flag = post.get('PushOptionsFlag') or request.httprequest.args.get('PushOptionsFlag')

            # Log incoming cdata request
            request_info = {
                'SN': serial_number,
                'options': options,
                'language': language,
                'pushver': pushver,
                'DeviceType': device_type,
                'PushOptionsFlag': push_options_flag,
                'method': request.httprequest.method
            }

            if not serial_number:
                _logger.warning("Missing serial number in cdata request")
                return 'ERROR: Missing serial number'

            _logger.info("Received cdata from device: %s (Method: %s)", serial_number, request.httprequest.method)
            _logger.info("Device params - options: %s, language: %s, pushver: %s, type: %s, flag: %s",
                         options, language, pushver, device_type, push_options_flag)

            # Find the device
            device = request.env['zkteco.device'].sudo().search([
                ('device_serial', '=', serial_number),
                ('is_active', '=', True)
            ], limit=1)

            if not device:
                _logger.warning("Device not found: %s", serial_number)
                # Auto-create device if not exists
                device = request.env['zkteco.device'].sudo().create({
                    'device_name': f'Auto-created Device {serial_number}',
                    'device_serial': serial_number,
                    'location': 'Auto-detected',
                    'is_active': True,
                    'connection_status': 'connected'
                })
                _logger.info("Auto-created device: %s", serial_number)

            # Update device last activity and info
            device.sudo().write({
                'last_activity': fields.Datetime.now(),
                'connection_status': 'connected',
            })

            # Get the raw data from different sources
            data = ''

            # Try to get data from POST body
            if request.httprequest.data:
                data = request.httprequest.data.decode('utf-8')

            # Try to get data from form parameters
            if not data and post.get('AttLog'):
                data = f"ATTLOG:{post.get('AttLog')}"
            elif not data and post.get('OPERLOG'):
                data = f"OPERLOG:{post.get('OPERLOG')}"
            elif not data and post.get('table'):
                # Handle table=ATTLOG&AttLog=data format
                table = post.get('table')
                if table == 'ATTLOG' and post.get('AttLog'):
                    data = f"ATTLOG:{post.get('AttLog')}"

            # Try to get data from URL parameters
            if not data:
                for key, value in post.items():
                    if key.startswith('ATTLOG') or key.startswith('OPERLOG'):
                        data = f"{key}:{value}"
                        break

            _logger.info("Raw attendance data: '%s'", data)
            print(f"Raw attendance data: {data}")

            # Log the raw data received
            self._log_attendance_processing(
                device_serial=serial_number,
                raw_data=data,
                request_info=request_info,
                status='processing'
            )

            # Handle different request types
            if not data or data.strip() == '':
                # This is likely a handshake/connection check request
                if options == 'all':
                    _logger.info("Handshake request from device %s - responding with connection acknowledgment",
                                 serial_number)
                    # Return stamp information to let device know server is ready
                    return 'GET OPTION FROM: all\nStamp=9999\nOpStamp=9999\nErrorDelay=60\nDelay=30\nTransTimes=00:00;14:05\nTransInterval=1\nTransFlag=1111000000\nTimeZone=7\nRealtime=1\nEncrypt=0'
                else:
                    _logger.info("Connection check from device %s - no attendance data", serial_number)
                    return 'OK'

            # Process the attendance data
            processed_count = self._process_attendance_data(device, data)

            processing_time = time.time() - start_time
            _logger.info("Processed %d attendance records for device %s", processed_count, serial_number)

            # Log successful processing
            self._log_attendance_processing(
                device_serial=serial_number,
                raw_data=data,
                request_info=request_info,
                processed_records=processed_count,
                # status='success' if processed_count > 0 else 'partial',
                status='success',
                processing_time=processing_time
            )
            return http.Response('OK', headers={'Content-Type': 'text/plain'})

        except Exception as e:
            processing_time = time.time() - start_time
            _logger.error("Error in ZKTeco cdata: %s", e)

            self._log_attendance_processing(
                device_serial=serial_number or 'UNKNOWN',
                raw_data=data if 'data' in locals() else '',
                request_info=request_info if 'request_info' in locals() else {},
                processed_records=processed_count,
                status='error',
                error_message=str(e),
                processing_time=processing_time
            )
            return 'ERROR: Internal server error'

    def _process_attendance_data(self, device, data):
        """Process attendance data and create records in Odoo"""
        processed_count = 0

        try:
            # Handle different data formats
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
            _logger.error("Error processing attendance data: %s", e)
            # Log individual record processing error
            self._log_attendance_processing(
                device_serial=device.device_serial if hasattr(device, 'device_serial') else 'UNKNOWN',
                raw_data=data,
                status='error',
                error_message=f"Error processing data: {str(e)}"
            )

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
        """Parse direct format data

        Supports multiple formats:
        1. Space-separated: 1 101 2024-01-15 09:30:00 1 1 1 0
        2. Tab-separated: 123456	2025-06-13 16:42:31	255	15	0	0	0	0	0	0
        3. Mixed formats with various delimiters
        """
        records = []

        # Try to extract attendance records from various formats
        lines = data.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue

            record = {}

            # Check if line contains tab characters (tab-separated format)
            if '\t' in line:
                parts = line.split('\t')
                print(f"Tab-separated parts: {parts}")

                # Tab-separated format: 123456	2025-06-13 16:42:31	255	15	0	0	0	0	0	0
                # Structure: [record_id]	[timestamp]	[user_id]	[status/verify_type]	[other_flags...]
                if len(parts) >= 4:
                    try:
                        record_id = parts[2].strip()  # 255
                        timestamp_str = parts[1].strip()  # 2025-06-13 16:42:31
                        user_id = parts[0].strip()  # 123456
                        status_or_verify = parts[3].strip()  # 15

                        # Additional fields if present
                        work_code = parts[4].strip() if len(parts) > 4 else '0'
                        reserved1 = parts[5].strip() if len(parts) > 5 else '0'
                        reserved2 = parts[6].strip() if len(parts) > 6 else '0'
                        reserved3 = parts[7].strip() if len(parts) > 7 else '0'
                        reserved4 = parts[8].strip() if len(parts) > 8 else '0'
                        reserved5 = parts[9].strip() if len(parts) > 9 else '0'

                        # Validate timestamp format
                        if self._validate_timestamp(timestamp_str):
                            # For ZKTeco devices, status usually is:
                            # 0 = Check Out, 1 = Check In, 4 = Break Out, 5 = Break In
                            # But in this format, status might be in different position
                            # Let's try to determine the actual status from available data

                            # If status_or_verify is a verify type (like 15 = fingerprint verify)
                            # we need to determine check-in/out from other context
                            # For now, we'll use work_code or default to check-in

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

                            print(f"Parsed tab record: {record}")
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
                    # Try other patterns for different formats
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
                        print(f"Parsed comma record: {record}")
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
            user_tz = 'Asia/Ho_Chi_Minh'

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
            # Try different datetime formats
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

    def _determine_attendance_status(self, status_or_verify, work_code, timestamp_str):
        """
        Determine actual attendance status from ZKTeco data

        Args:
            status_or_verify: Could be verify type (1=fingerprint, 15=face, etc.) or status
            work_code: Work code (0=normal, 1=overtime, etc.)
            timestamp_str: Timestamp for context

        Returns:
            str: '0' for check-out, '1' for check-in
        """

        # If status_or_verify is clearly a status code
        if status_or_verify in ['0', '1', '4', '5']:
            return status_or_verify

        # If work_code indicates status
        if work_code in ['0', '1']:
            return work_code

        # Use time-based heuristic as fallback
        try:
            time_obj = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S').time()

            # Morning hours (6 AM - 12 PM) → likely check-in
            if 6 <= time_obj.hour < 12:
                return '1'  # Check-in
            # Evening hours (5 PM - 10 PM) → likely check-out
            elif 17 <= time_obj.hour < 22:
                return '0'  # Check-out
            # Lunch time (11 AM - 2 PM) → could be either
            elif 11 <= time_obj.hour < 14:
                # Check if it's near lunch start (12 PM) → check-out
                # or lunch end (1 PM) → check-in
                if time_obj.hour == 12:
                    return '0'  # Lunch break out
                else:
                    return '1'  # Back from lunch
            else:
                # Default to check-in for other times
                return '1'

        except:
            # If timestamp parsing fails, default to check-in
            return '1'

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
        """Create attendance record in Odoo"""
        try:
            user_id = record_data.get('user_id')
            timestamp_str = record_data.get('timestamp')
            status = record_data.get('status', '1')

            if not user_id or not timestamp_str:
                _logger.warning("Incomplete attendance record: %s", record_data)
                return False

            # Find employee by device user ID
            employee = request.env['hr.employee'].sudo().search([
                ('attendance_device_id', '=', user_id)
            ], limit=1)

            if not employee:
                _logger.warning("Employee not found for device user ID: %s", user_id)
                # Optionally create a placeholder employee or log for manual review
                self._log_unknown_employee(device, user_id, timestamp_str, status)
                return False

            # Parse timestamp - keep original for date calculation, convert for storage
            try:
                # Parse original timestamp to get local date
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

                # Get local date for searching (device timezone date)
                local_date = local_timestamp.date()

                # Convert timestamp to UTC for storage
                timestamp = self._convert_timestamp_to_utc(timestamp_str)
                _logger.debug("Local timestamp: %s, Local date: %s, UTC timestamp: %s",
                              local_timestamp, local_date, timestamp)

            except Exception as e:
                _logger.error("Error parsing timestamp %s: %s", timestamp_str, e)
                return False

            # Check if this employee is on night shift schedule
            is_night_shift_employee = self._is_night_shift_employee(employee)

            # Determine which shift date this timestamp belongs to
            shift_begin_date, is_night_continuation = self._get_night_shift_date(local_timestamp,
                                                                                 is_night_shift_employee)

            # Calculate search boundaries in LOCAL time first, then convert to UTC
            if is_night_shift_employee:
                local_start_of_day = datetime.combine(shift_begin_date, datetime.min.time())
                local_end_of_day = datetime.combine(shift_begin_date + timedelta(days=1),
                                                   datetime.strptime('12:00:00', '%H:%M:%S').time())
            else:
                # Regular employees: search within the same day
                local_start_of_day = datetime.combine(shift_begin_date, datetime.min.time())  # 00:00 of begin date
                local_end_of_day = datetime.combine(shift_begin_date + timedelta(days=1),
                                                   datetime.strptime('02:00:00',
                                                                     '%H:%M:%S').time())  # next day 03:00:00 of begin date

            # Convert local day boundaries to UTC for database search
            utc_start_of_day = self._convert_timestamp_to_utc(local_start_of_day)
            utc_end_of_day = self._convert_timestamp_to_utc(local_end_of_day)

            _logger.debug("Search range - Local: %s to %s, UTC: %s to %s",
                          local_start_of_day, local_end_of_day, utc_start_of_day, utc_end_of_day)

            # Check for existing attendance record on the same day (using UTC boundaries)
            existing_record = request.env['hr.attendance'].sudo().search([
                ('employee_id', '=', employee.id),
                ('check_in', '>=', utc_start_of_day),
                ('check_in', '<=', utc_end_of_day),
            ], limit=1)

            if existing_record:
                current_check_in = existing_record.check_in
                current_check_out = existing_record.check_out
                updated = False
                update_data = {}
                update_message = []

                # Check if timestamp should be the new check_in (earliest time)
                if timestamp < current_check_in:
                    update_data['check_in'] = timestamp
                    update_data['check_out'] = current_check_in
                    update_message.append(f"Updated check-in to earlier time: {timestamp}")
                    updated = True

                # Check if timestamp should be the new check_out (latest time)
                if not current_check_out or timestamp > current_check_out:
                    # Only update check_out if timestamp is after check_in
                    final_check_in = update_data.get('check_in', current_check_in)
                    if timestamp > final_check_in:
                        update_data['check_out'] = timestamp
                        update_message.append(f"Updated check-out to later time: {timestamp}")
                        updated = True
                    else:
                        _logger.warning("Timestamp %s (local: %s) is not after check-in %s for employee %s",
                                        timestamp, local_timestamp, final_check_in, employee.name)

                if updated:
                    # Update raw_data to include reprocess information
                    current_raw_data = existing_record.raw_data or ''
                    update_data[
                        'raw_data'] = current_raw_data + f"\nReprocessed: {'; '.join(update_message)} - Local: {local_timestamp}, UTC: {timestamp} - {record_data}"

                    existing_record.write(update_data)
                    _logger.info("Updated attendance record for employee %s: %s (Local: %s, UTC: %s)",
                                 employee.name, '; '.join(update_message), local_timestamp, timestamp)
                    return True
                else:
                    # Timestamp doesn't extend the attendance period
                    _logger.info(
                        "Timestamp %s (local: %s) for employee %s is within existing attendance period (%s - %s), no update needed",
                        timestamp, local_timestamp, employee.name, current_check_in, current_check_out or 'No checkout')
                    return False
            else:
                # Create the attendance record
                request.env.cr.execute("""
                    INSERT INTO hr_attendance 
                    (employee_id, check_in, device_id, raw_data, create_date, create_uid, write_date, write_uid)
                    VALUES (%s, %s, %s, %s, NOW(), 1, NOW(), 1)
                """, (employee.id, timestamp, device.id, str(record_data)))
                result = request.env.cr.fetchone()
                request.env.cr.commit()
            return True

        except Exception as e:
            _logger.error("Error creating attendance record for %s: %s", record_data, e)
            return False

    def _log_unknown_employee(self, device, user_id, timestamp, status):
        """Log attendance for unknown employees for manual review"""
        try:
            utc_timestamp = self._convert_timestamp_to_utc(timestamp)

            # Create a log entry for unknown employees
            request.env['zkteco.unknown.attendance'].sudo().create({
                'device_serial': device.device_serial if hasattr(device, 'device_serial') else '',
                'device_user_id': user_id,
                'timestamp': utc_timestamp,
                'status': status,
                'processed': False,
                'notes': f"Unknown employee with device user ID: {user_id}"
            })
        except Exception as e:
            _logger.error("Error logging unknown employee attendance: %s", e)

    @http.route('/iclock/devicecmd', type='http', auth='none', csrf=False, methods=['GET', 'POST'])
    def device_cmd(self, **kwargs):
        print("device_cmd")
        """Handle device command check from ZKTeco device

        The device periodically checks if there are commands to execute
        GET /iclock/devicecmd?SN=XXXXXXXXXX
        """
        try:
            serial_number = kwargs.get('SN')
            if not serial_number:
                _logger.warning("Missing serial number in devicecmd")
                return 'ERROR: Missing serial number'

            print("Received devicecmd from device: %s", serial_number)

            # Find or create the device
            device = request.env['zkteco.device'].sudo().search([
                ('device_serial', '=', serial_number),
                ('is_active', '=', True)
            ], limit=1)

            if not device:
                # Auto-create device if not exists
                device = request.env['zkteco.device'].sudo().create({
                    'device_name': f'Auto-created Device {serial_number}',
                    'device_serial': serial_number,
                    'location': 'Auto-detected',
                    'is_active': True,
                    'connection_status': 'connected'
                })
                _logger.info("Auto-created device: %s", serial_number)

            # Update device status to connected
            device.sudo().write({
                'last_activity': fields.Datetime.now(),
                'connection_status': 'connected'
            })

            # Check for pending commands
            pending_commands = device.sudo().get_pending_commands()
            if pending_commands:
                _logger.info("Sending commands to device %s: %s", serial_number, pending_commands)
                return pending_commands

            return 'OK'

        except Exception as e:
            _logger.error("Error in ZKTeco devicecmd: %s", e)
            return 'ERROR: Internal server error'

    @http.route('/iclock/fdata', type='http', auth='none', csrf=False, methods=['GET', 'POST'])
    def fdata(self, **kwargs):
        """Handle finger template data from ZKTeco device"""
        try:
            serial_number = kwargs.get('SN')
            if not serial_number:
                return 'ERROR: Missing serial number'

            _logger.info("Received fdata from device: %s", serial_number)

            # Log the finger template data for future implementation
            data = request.httprequest.data.decode('utf-8') if request.httprequest.data else ''
            _logger.info("Finger template data: %s", data)

            return 'OK'

        except Exception as e:
            _logger.error("Error in ZKTeco fdata: %s", e)
            return 'ERROR: Internal server error'

    @http.route('/iclock/public', type='http', auth='none', csrf=False, methods=['GET', 'POST'])
    def public_data(self, **kwargs):
        """Handle public data from ZKTeco device (announcements, etc.)"""
        try:
            serial_number = kwargs.get('SN')
            if not serial_number:
                return 'ERROR: Missing serial number'

            _logger.info("Received public data from device: %s", serial_number)

            return 'OK'

        except Exception as e:
            _logger.error("Error in ZKTeco public: %s", e)
            return 'ERROR: Internal server error'

    @http.route('/iclock/test', type='http', auth='none', csrf=False, methods=['GET', 'POST'])
    def test_endpoint(self, **kwargs):
        """Test endpoint để debug dữ liệu từ máy chấm công"""
        try:
            _logger.info("=== ZKTeco Test Endpoint ===")
            _logger.info(f"Method: {request.httprequest.method}")
            _logger.info(f"URL: {request.httprequest.url}")
            _logger.info(f"Headers: {dict(request.httprequest.headers)}")
            _logger.info(f"GET Args: {dict(request.httprequest.args)}")
            _logger.info(f"POST Form: {dict(request.httprequest.form)}")
            _logger.info(f"Raw data: {request.httprequest.data}")
            _logger.info(f"Content type: {request.httprequest.content_type}")
            _logger.info(f"kwargs: {kwargs}")
            _logger.info("=== End Test ===")

            # Create a comprehensive response for testing
            response_html = f"""
            <html>
            <head><title>ZKTeco Test Endpoint</title></head>
            <body>
                <h1>ZKTeco Test Endpoint - Request Details</h1>
                <h2>Method: {request.httprequest.method}</h2>
                <h3>URL:</h3>
                <p>{request.httprequest.url}</p>

                <h3>Headers:</h3>
                <pre>{dict(request.httprequest.headers)}</pre>

                <h3>GET Parameters:</h3>
                <pre>{dict(request.httprequest.args)}</pre>

                <h3>POST Form Data:</h3>
                <pre>{dict(request.httprequest.form)}</pre>

                <h3>Raw Data:</h3>
                <pre>{request.httprequest.data}</pre>

                <h3>Content Type:</h3>
                <p>{request.httprequest.content_type}</p>

                <h3>Kwargs:</h3>
                <pre>{kwargs}</pre>

                <p><strong>Check Odoo logs for detailed information</strong></p>
            </body>
            </html>
            """

            return response_html

        except Exception as e:
            _logger.error(f"Error in test endpoint: {e}")
            return f"Error: {e}"

    @http.route('/iclock/ping', type='http', auth='none', csrf=False, methods=['GET', 'POST'])
    def ping_endpoint(self, **kwargs):
        """Simple ping endpoint để test connectivity"""
        return 'PONG'

    @http.route('/iclock/serverinfo', type='http', auth='none', csrf=False, methods=['GET'])
    def server_info(self, **kwargs):
        """Return server information for ZKTeco devices"""
        return 'ServerVer=1.0\nPushVer=2.4.1\nServerTime=' + str(fields.Datetime.now())

    def _log_attendance_processing(self, device_serial, raw_data, request_info=None,
                                   processed_records=0, status='success', error_message=None, processing_time=0):
        """Log attendance processing activity"""
        try:
            request.env['zkteco.attendance.log'].sudo().log_processing(
                device_serial=device_serial,
                raw_data=raw_data,
                processed_count=processed_records,
                error_msg=error_message,
                processing_time=processing_time,
                status=status,
            )
        except Exception as e:
            _logger.error("Error logging attendance processing: %s", e)