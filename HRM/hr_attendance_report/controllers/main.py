from odoo import http
from odoo.http import request
import io
import xlsxwriter
from datetime import datetime
import calendar
import logging
import pytz
import re
import unicodedata

_logger = logging.getLogger(__name__)


class AttendanceReportController(http.Controller):

    @http.route('/attendance/monthly/report/excel', type='http', auth='user', csrf=False)
    def export_attendance_monthly_excel(self, wizard_id, **kwargs):
        """Xuất báo cáo Excel với format chuyên nghiệp"""

        try:
            wizard = request.env['hr.attendance.monthly.report'].browse(int(wizard_id))
            if not wizard.exists():
                return request.not_found("Wizard không tồn tại")

            data = wizard._prepare_report_data()

            # Tạo file Excel
            output = io.BytesIO()
            workbook = xlsxwriter.Workbook(output, {
                'in_memory': True,
                'default_date_format': 'dd/mm/yyyy',
                'remove_timezone': True
            })
            worksheet = workbook.add_worksheet('BangChamCong')

            # Định dạng cells chuyên nghiệp
            formats = self._create_excel_formats(workbook)

            # Viết nội dung
            self._write_excel_content(worksheet, data, formats)

            # Thiết lập worksheet
            self._setup_worksheet(worksheet, data, formats)

            workbook.close()
            output.seek(0)

            # Tạo response với filename an toàn (ASCII only)
            company_name_safe = self._make_filename_safe(data['company_name'])
            filename = f"BangChamCong_{data['month']:0>2}_{data['year']}_{company_name_safe}.xlsx"

            return request.make_response(
                output.getvalue(),
                headers=[
                    ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
                    ('Content-Disposition', f'attachment; filename="{filename}"'),
                    ('Content-Length', len(output.getvalue()))
                ]
            )

        except Exception as e:
            _logger.error(f"Error exporting attendance report: {e}", exc_info=True)
            return request.render('http_routing.http_error', {
                'status_code': 500,
                'status_message': f'Lỗi xuất báo cáo: {str(e)}'
            })

    def _create_excel_formats(self, workbook):
        """Tạo các format cho Excel"""
        return {
            'title': workbook.add_format({
                'bold': True,
                'font_size': 16,
                'align': 'center',
                'valign': 'vcenter',
                'border': 2,
                'bg_color': '#4472C4',
                'font_color': 'white'
            }),

            'subtitle': workbook.add_format({
                'bold': True,
                'font_size': 12,
                'align': 'center',
                'valign': 'vcenter',
                'border': 1,
                'bg_color': '#D9E2F3'
            }),

            'header': workbook.add_format({
                'bold': True,
                'bg_color': '#E7E6E6',
                'border': 1,
                'align': 'center',
                'valign': 'vcenter',
                'font_size': 9,
                'text_wrap': True
            }),

            'header_day': workbook.add_format({
                'bold': True,
                'bg_color': '#B4C6E7',
                'border': 1,
                'align': 'center',
                'valign': 'vcenter',
                'font_size': 8
            }),

            'header_weekday': workbook.add_format({
                'bold': True,
                'bg_color': '#D9E2F3',
                'border': 1,
                'align': 'center',
                'valign': 'vcenter',
                'font_size': 7
            }),

            'header_inout': workbook.add_format({
                'bold': True,
                'bg_color': '#F2F2F2',
                'border': 1,
                'align': 'center',
                'valign': 'vcenter',
                'font_size': 8
            }),

            'cell': workbook.add_format({
                'border': 1,
                'align': 'center',
                'valign': 'vcenter',
                'font_size': 8
            }),

            'cell_name': workbook.add_format({
                'border': 1,
                'align': 'left',
                'valign': 'vcenter',
                'font_size': 8
            }),

            'no_data': workbook.add_format({
                'border': 1,
                'align': 'center',
                'valign': 'vcenter',
                'font_size': 8,
                'bg_color': '#FFE6E6',  # Light red
                'font_color': '#999999'
            }),

            'weekend': workbook.add_format({
                'border': 1,
                'align': 'center',
                'valign': 'vcenter',
                'font_size': 8,
                'bg_color': '#E6F3FF',  # Light blue
            }),

            # Thêm format cho nghỉ phép
            'leave_full_day': workbook.add_format({
                'border': 1,
                'align': 'center',
                'valign': 'vcenter',
                'font_size': 8,
                'bg_color': '#FFF2CC',  # Light yellow
                'font_color': '#7F6000',  # Dark yellow
                'bold': True
            }),

            'leave_half_day': workbook.add_format({
                'border': 1,
                'align': 'center',
                'valign': 'vcenter',
                'font_size': 8,
                'bg_color': '#E2EFDA',  # Light green
                'font_color': '#375623',  # Dark green
            }),

            'info': workbook.add_format({
                'bold': True,
                'font_size': 10,
                'border': 1,
                'bg_color': '#F8F9FA',
                'align': 'left'
            }),

            'summary': workbook.add_format({
                'bold': True,
                'bg_color': '#D4EDDA',
                'border': 1,
                'align': 'center',
                'font_size': 9
            })
        }

    def _write_excel_content(self, worksheet, data, formats):
        """Viết nội dung Excel"""

        current_row = 0
        total_cols = 5 + (data['days_in_month'] * 2)

        # 1. Title
        worksheet.merge_range(current_row, 0, current_row, total_cols - 1,
                              'BẢNG CHẤM CÔNG GIỜ', formats['title'])
        current_row += 1

        # 2. Company info
        worksheet.merge_range(current_row, 0, current_row, total_cols - 1,
                              data['company_name'], formats['subtitle'])
        current_row += 1

        # 3. Month/Year info
        worksheet.write(current_row, 1, 'Tháng:', formats['info'])
        worksheet.write(current_row, 2, f"{data['month']:0>2}", formats['cell'])
        worksheet.write(current_row, 4, 'Năm:', formats['info'])
        worksheet.write(current_row, 5, data['year'], formats['cell'])
        current_row += 1

        # 4. Report info
        worksheet.write(current_row, 1, 'Ngày tạo:', formats['info'])
        worksheet.write(current_row, 2, data['report_date'], formats['cell'])
        worksheet.write(current_row, 4, 'Người tạo:', formats['info'])
        worksheet.write(current_row, 5, data['user_name'], formats['cell'])
        current_row += 1

        # Empty row
        current_row += 1

        # 5. Headers
        header_start = current_row

        # Main headers (3 rows)
        headers = ['STT', 'Mã NV', 'Tên nhân viên', 'Phòng ban', 'Chức vụ']
        for col, header in enumerate(headers):
            worksheet.merge_range(header_start, col, header_start + 2, col, header, formats['header'])

        # Day numbers and weekdays
        col = 5
        weekend_days = self._get_weekend_days(data['year'], int(data['month']))

        for day in range(1, data['days_in_month'] + 1):
            # Day number
            day_format = formats['weekend'] if day in weekend_days else formats['header_day']
            worksheet.merge_range(header_start, col, header_start, col + 1, str(day), day_format)

            # Weekday name
            day_name = self._get_day_name(data['year'], int(data['month']), day)
            weekday_format = formats['weekend'] if day in weekend_days else formats['header_weekday']
            worksheet.merge_range(header_start + 1, col, header_start + 1, col + 1, day_name, weekday_format)

            # In/Out
            worksheet.write(header_start + 2, col, 'Vào', formats['header_inout'])
            worksheet.write(header_start + 2, col + 1, 'Ra', formats['header_inout'])

            col += 2

        current_row = header_start + 3

        # 6. Employee data
        for idx, employee in enumerate(data['employees']):
            worksheet.write(current_row, 0, idx + 1, formats['cell'])
            worksheet.write(current_row, 1, employee['employee_code'], formats['cell'])
            worksheet.write(current_row, 2, employee['name'], formats['cell_name'])
            worksheet.write(current_row, 3, employee['department'], formats['cell'])
            worksheet.write(current_row, 4, employee['job_title'], formats['cell'])

            col = 5
            for day in range(1, data['days_in_month'] + 1):
                day_data = data['attendance_data'].get(employee['id'], {}).get(day, {})
                leave_data = data['leave_data'].get(employee['id'], {}).get(day, {})

                has_attendance = day_data.get('has_data', False)
                has_leave = leave_data.get('has_leave', False)
                is_weekend = day in weekend_days

                # Xác định format và nội dung hiển thị
                cell_format, check_in_text, check_out_text = self._determine_cell_format_and_content(
                    formats, has_attendance, has_leave, is_weekend, day_data, leave_data
                )

                worksheet.write(current_row, col, check_in_text, cell_format)
                worksheet.write(current_row, col + 1, check_out_text, cell_format)
                col += 2

            current_row += 1

        # 7. Legend (chú thích màu sắc)
        current_row += 1
        self._write_legend(worksheet, current_row, formats, total_cols)
        current_row += 3

        # 8. Summary (if enabled)
        if data.get('show_summary', True) and data.get('statistics'):
            current_row += 1
            self._write_summary(worksheet, current_row, data['statistics'], formats, total_cols)

    def _determine_cell_format_and_content(self, formats, has_attendance, has_leave, is_weekend, day_data, leave_data):
        """Xác định format và nội dung hiển thị cho cell dựa trên trạng thái"""

        if has_leave:
            leave_type = leave_data.get('leave_type', 'full')
            leave_name = leave_data.get('leave_name', 'Nghỉ phép')

            if leave_type == 'full':
                # Nghỉ cả ngày
                return formats['leave_full_day'], leave_name, ''
            else:
                # Nghỉ nửa ngày - vẫn có thể có dữ liệu chấm công
                if has_attendance:
                    return formats['leave_half_day'], day_data.get('check_in', ''), day_data.get('check_out', '')
                else:
                    return formats['leave_half_day'], f"{leave_name} (1/2)", ''

        elif has_attendance:
            # Có dữ liệu chấm công bình thường
            if is_weekend:
                return formats['weekend'], day_data.get('check_in', ''), day_data.get('check_out', '')
            else:
                return formats['cell'], day_data.get('check_in', ''), day_data.get('check_out', '')

        else:
            # Không có dữ liệu
            if is_weekend:
                return formats['weekend'], '', ''
            else:
                return formats['no_data'], '', ''

    def _write_legend(self, worksheet, start_row, formats, total_cols):
        """Viết chú thích màu sắc"""

        worksheet.merge_range(start_row, 0, start_row, total_cols - 1, 'CHÚ THÍCH MÀU SẮC', formats['subtitle'])
        start_row += 1

        legends = [
            ('Ngày làm việc có chấm công', formats['cell']),
            ('Ngày cuối tuần', formats['weekend']),
            ('Nghỉ phép cả ngày', formats['leave_full_day']),
            ('Nghỉ phép nửa ngày', formats['leave_half_day']),
            ('Không có dữ liệu chấm công', formats['no_data']),
        ]

        for i, (text, format_style) in enumerate(legends):
            worksheet.write(start_row, i * 2, '■', format_style)
            worksheet.write(start_row, i * 2 + 1, text, formats['info'])

    def _write_summary(self, worksheet, start_row, stats, formats, total_cols):
        """Viết phần tổng kết"""

        worksheet.merge_range(start_row, 0, start_row, total_cols - 1, 'TỔNG KẾT', formats['title'])
        start_row += 1

        # Statistics
        summary_data = [
            ['Tổng số nhân viên:', stats['total_employees']],
            ['Tổng số ngày làm việc:', stats['total_working_days']],
            ['Tổng số ngày vắng mặt:', stats['total_absent_days']],
            ['Tổng số ngày nghỉ phép:', stats.get('total_leave_days', 0)],
            ['Tổng giờ làm việc:', f"{stats['total_working_hours']} giờ"],
            ['Tỷ lệ chấm công trung bình:', f"{stats['overall_attendance_rate']}%"],
        ]

        for i, (label, value) in enumerate(summary_data):
            worksheet.write(start_row + i, 1, label, formats['info'])
            worksheet.write(start_row + i, 2, value, formats['summary'])

    def _setup_worksheet(self, worksheet, data, formats):
        """Thiết lập worksheet"""

        total_cols = 5 + (data['days_in_month'] * 2)

        # Column widths
        worksheet.set_column(0, 0, 5)  # STT
        worksheet.set_column(1, 1, 12)  # Mã NV
        worksheet.set_column(2, 2, 25)  # Tên
        worksheet.set_column(3, 3, 20)  # Phòng ban
        worksheet.set_column(4, 4, 20)  # Chức vụ
        worksheet.set_column(5, total_cols - 1, 6)  # Các cột ngày

        # Row heights
        worksheet.set_row(0, 35)  # Title
        worksheet.set_row(1, 25)  # Company
        worksheet.set_row(5, 25)  # Header row 1
        worksheet.set_row(6, 30)  # Header row 2 (weekdays)
        worksheet.set_row(7, 20)  # Header row 3 (In/Out)

        # Freeze panes
        worksheet.freeze_panes(8, 5)

        # Print settings
        worksheet.set_landscape()
        worksheet.set_paper(9)  # A4
        worksheet.fit_to_pages(1, 0)  # Fit to 1 page wide

        # Margins
        worksheet.set_margins(0.5, 0.5, 0.8, 0.8)

    def _get_day_name(self, year, month, day):
        """Lấy tên thứ trong tuần theo timezone local"""
        try:
            user_tz_name = request.env.user.tz or request.env.company.partner_id.tz or 'UTC'
            user_tz = pytz.timezone(user_tz_name)

            local_dt = user_tz.localize(datetime(year, month, day))
            day_names = ['Thứ hai', 'Thứ ba', 'Thứ tư', 'Thứ năm', 'Thứ sáu', 'Thứ bảy', 'CN']
            return day_names[local_dt.weekday()]
        except Exception as e:
            _logger.warning(f"Error getting day name: {e}")
            return ''

    def _get_weekend_days(self, year, month):
        """Lấy danh sách ngày cuối tuần trong tháng"""
        try:
            user_tz_name = request.env.user.tz or request.env.company.partner_id.tz or 'UTC'
            user_tz = pytz.timezone(user_tz_name)
            days_in_month = calendar.monthrange(year, month)[1]
            weekend_days = []

            for day in range(1, days_in_month + 1):
                local_dt = user_tz.localize(datetime(year, month, day))
                # 5 = Saturday, 6 = Sunday
                if local_dt.weekday() in [5, 6]:
                    weekend_days.append(day)

            return weekend_days
        except Exception as e:
            _logger.warning(f"Error getting weekend days: {e}")
            return []

    def _make_filename_safe(self, text):
        """Tạo filename an toàn chỉ chứa ASCII characters"""
        import re
        import unicodedata

        if not text:
            return "Company"

        # Normalize Unicode và loại bỏ diacritics
        text = unicodedata.normalize('NFD', text)
        text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')

        # Chỉ giữ lại alphanumeric và một số ký tự an toàn
        text = re.sub(r'[^a-zA-Z0-9\-_]', '_', text)

        # Loại bỏ underscore liên tiếp và trim
        text = re.sub(r'_+', '_', text).strip('_')

        # Giới hạn độ dài
        if len(text) > 30:
            text = text[:30].rstrip('_')

        # Fallback nếu string rỗng
        return text if text else "Company"