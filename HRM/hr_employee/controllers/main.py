# -*- coding: utf-8 -*-
# File: controllers/main.py

from odoo import http
from odoo.http import request
import json
import logging
import werkzeug

_logger = logging.getLogger(__name__)


class testController(http.Controller):

    @http.route('/test/iclock/getrequest', type='http', auth='none', csrf=False, methods=['GET'])
    def get_request(self, **kwargs):
        """Handle GET request from ZKTeco device

        The device sends a request like:
        GET /iclock/getrequest?SN=XXXXXXXXXX

        We need to respond with commands for the device
        """
        try:
            serial_number = kwargs.get('SN')
            if not serial_number:
                return 'ERROR: Missing serial number'

            _logger.info("Received getrequest from device: %s", serial_number)

            # Find the device
            device = request.env['zkteco.device'].sudo().search([
                ('device_serial', '=', serial_number),
                ('is_active', '=', True)
            ], limit=1)

            if not device:
                return 'ERROR: Device not found'

            # Update device status to connected
            device.sudo().action_connect()

            # Typically, we would return commands here if needed
            # For now, just return OK
            return 'OK'

        except Exception as e:
            _logger.error("Error in ZKTeco getrequest: %s", e)
            return 'ERROR: Internal server error'

    @http.route('/test/iclock/cdata', type='http', auth='none', csrf=False, methods=['POST'])
    def cdata(self, **post):
        """Handle attendance data from ZKTeco device

        The device posts attendance data in a special format:
        POST /iclock/cdata?SN=XXXXXXXXXX

        The data format is typically:
        OPERLOG: user_id=1\ttime=2025-05-02 08:30:00\tstatus=0
        """
        try:
            serial_number = post.get('SN')
            if not serial_number:
                return 'ERROR: Missing serial number'

            _logger.info("Received cdata from device: %s", serial_number)

            # Get the raw data
            data = request.httprequest.data.decode('utf-8')
            _logger.info("Raw data: %s", data)

            # Find the device
            device = request.env['zkteco.device'].sudo().search([
                ('device_serial', '=', serial_number),
                ('is_active', '=', True)
            ], limit=1)

            if not device:
                return 'ERROR: Device not found'

            # Process the data based on type
            # Usually starts with a header like "OPERLOG:" or "ATTLOG:"
            if data.startswith('OPERLOG:') or data.startswith('ATTLOG:'):
                header, content = data.split(':', 1)

                # Parse the attendance records
                # Format is typically: user_id=1\ttime=2025-05-02 08:30:00\tstatus=0
                records = []

                for line in content.strip().split('\n'):
                    line = line.strip()
                    if not line:
                        continue

                    # Parse the tab-separated values
                    parts = line.split('\t')
                    record = {}

                    for part in parts:
                        if '=' in part:
                            key, value = part.split('=', 1)
                            if key == 'user_id':
                                record['user_id'] = value
                            elif key in ('time', 'timestamp'):
                                record['timestamp'] = value
                            elif key == 'status':
                                record['status'] = value

                    if 'user_id' in record and 'timestamp' in record:
                        records.append(record)

                # Process the attendance data
                if records:
                    device.sudo().process_attendance_data(serial_number, records)

                return 'OK'
            else:
                _logger.warning("Unknown data format: %s", data)
                return 'ERROR: Unknown data format'

        except Exception as e:
            _logger.error("Error in ZKTeco cdata: %s", e)
            return 'ERROR: Internal server error'

    @http.route('/test/iclock/devicecmd', type='http', auth='none', csrf=False, methods=['GET'])
    def device_cmd(self, **kwargs):
        """Handle device command check from ZKTeco device

        The device periodically checks if there are commands to execute
        """
        try:
            serial_number = kwargs.get('SN')
            if not serial_number:
                return 'ERROR: Missing serial number'

            _logger.info("Received devicecmd from device: %s", serial_number)

            # Find the device
            device = request.env['zkteco.device'].sudo().search([
                ('device_serial', '=', serial_number),
                ('is_active', '=', True)
            ], limit=1)

            if not device:
                return 'ERROR: Device not found'

            # Update device status to connected
            device.sudo().action_connect()

            # For now, just return OK (no commands)
            return 'OK'

        except Exception as e:
            _logger.error("Error in ZKTeco devicecmd: %s", e)
            return 'ERROR: Internal server error'


