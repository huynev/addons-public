from odoo import http
from odoo.http import request
import io
import xlsxwriter
from datetime import datetime
import logging

_logger = logging.getLogger(__name__)


class EmployeeAllowanceReportController(http.Controller):

    @http.route('/employee/allowance/report/excel', type='http', auth='user', csrf=False)
    def export_employee_allowance_excel(self, wizard_id, **kwargs):
        """Xuất báo cáo Excel phụ cấp nhân viên"""

        try:
            wizard = request.env['employee.allowance.report'].browse(int(wizard_id))
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
            worksheet = workbook.add_worksheet('BaoCaoPhiCap')

            # Định dạng cells
            formats = self._create_excel_formats(workbook)

            # Viết nội dung
            self._write_excel_content(worksheet, data, formats)

            # Thiết lập worksheet
            self._setup_worksheet(worksheet, data, formats)

            workbook.close()
            output.seek(0)

            # Tạo response với filename
            filename = f"BaoCaoPhiCap_{data['date_from'].strftime('%d%m%Y')}_{data['date_to'].strftime('%d%m%Y')}.xlsx"

            return request.make_response(
                output.getvalue(),
                headers=[
                    ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
                    ('Content-Disposition', f'attachment; filename="{filename}"'),
                    ('Content-Length', len(output.getvalue()))
                ]
            )

        except Exception as e:
            _logger.error(f"Error exporting allowance report: {e}", exc_info=True)
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
                'font_size': 10,
                'text_wrap': True
            }),

            'header_allowance': workbook.add_format({
                'bold': True,
                'bg_color': '#B4C6E7',
                'border': 1,
                'align': 'center',
                'valign': 'vcenter',
                'font_size': 9,
                'text_wrap': True
            }),

            'cell': workbook.add_format({
                'border': 1,
                'align': 'center',
                'valign': 'vcenter',
                'font_size': 9
            }),

            'cell_text': workbook.add_format({
                'border': 1,
                'align': 'left',
                'valign': 'vcenter',
                'font_size': 9
            }),

            'cell_number': workbook.add_format({
                'border': 1,
                'align': 'right',
                'valign': 'vcenter',
                'font_size': 9,
                'num_format': '#,##0'
            }),

            'total_row': workbook.add_format({
                'bold': True,
                'bg_color': '#D4EDDA',
                'border': 1,
                'align': 'center',
                'font_size': 10
            }),

            'total_number': workbook.add_format({
                'bold': True,
                'bg_color': '#D4EDDA',
                'border': 1,
                'align': 'right',
                'font_size': 10,
                'num_format': '#,##0'
            }),

            'info': workbook.add_format({
                'bold': True,
                'font_size': 10,
                'border': 1,
                'bg_color': '#F8F9FA',
                'align': 'left'
            }),
            'department_header': workbook.add_format({  # New format for department group header
                'bold': True,
                'font_size': 11,
                'bg_color': '#A9D08E',
                'border': 1,
                'align': 'left',
                'valign': 'vcenter',
            }),
            'department_total_row': workbook.add_format({  # New format for department total row
                'bold': True,
                'bg_color': '#C6E0B4',
                'border': 1,
                'align': 'center',
                'font_size': 10
            }),
            'department_total_number': workbook.add_format({  # New format for department total number
                'bold': True,
                'bg_color': '#C6E0B4',
                'border': 1,
                'align': 'right',
                'font_size': 10,
                'num_format': '#,##0'
            }),
        }

    def _write_excel_content(self, worksheet, data, formats):
        """Viết nội dung Excel"""

        current_row = 0
        employees = data['employees']
        allowance_types = data['allowance_types']
        allowance_data = data['allowance_data']
        group_by_department = data['group_by_department']  # Get the new option

        # Tính tổng cột cần thiết
        base_cols = 5  # STT, Mã NV, Tên, Phòng ban, Lương cơ bản
        allowance_cols = len(allowance_types)
        total_cols = base_cols + allowance_cols + 3  # +1 for Total, +1 for Date of Joining, +1 for Seniority

        # 1. Title
        worksheet.merge_range(current_row, 0, current_row, total_cols - 1,
                              'BÁO CÁO PHỤ CẤP NHÂN VIÊN', formats['title'])
        current_row += 1

        # 2. Company info
        worksheet.merge_range(current_row, 0, current_row, total_cols - 1,
                              data['company_name'], formats['subtitle'])
        current_row += 1

        # 3. Thời gian báo cáo
        worksheet.write(current_row, 1, 'Từ ngày:', formats['info'])
        worksheet.write(current_row, 2, data['date_from'].strftime('%d/%m/%Y'), formats['cell'])
        worksheet.write(current_row, 3, 'Đến ngày:', formats['info'])
        worksheet.write(current_row, 4, data['date_to'].strftime('%d/%m/%Y'), formats['cell'])
        current_row += 1

        # 4. Thông tin báo cáo
        worksheet.write(current_row, 1, 'Ngày tạo:', formats['info'])
        worksheet.write(current_row, 2, data['report_date'], formats['cell'])
        worksheet.write(current_row, 3, 'Người tạo:', formats['info'])
        worksheet.write(current_row, 4, data['user_name'], formats['cell'])
        current_row += 1

        # Empty row
        current_row += 1

        # 5. Headers (written once for the entire report)
        header_start = current_row

        headers = ['STT', 'Mã NV', 'Họ và tên', 'Phòng ban', 'Lương cơ bản']
        for col, header in enumerate(headers):
            worksheet.write(header_start, col, header, formats['header'])

        col = base_cols
        for allowance_type in allowance_types:
            worksheet.write(header_start, col, f"{allowance_type['code']}\n{allowance_type['name']}",
                            formats['header_allowance'])
            col += 1

        worksheet.write(header_start, col, 'Tổng cộng', formats['header'])
        col += 1
        worksheet.write(header_start, col, 'Ngày vào làm', formats['header'])
        col += 1
        worksheet.write(header_start, col, 'Thâm niên', formats['header']) # New header

        current_row = header_start + 1

        # 6. Dữ liệu nhân viên
        if group_by_department:
            grouped_employees_data = {}
            for emp in employees:
                dept_name = emp['department']
                if dept_name not in grouped_employees_data:
                    grouped_employees_data[dept_name] = []
                grouped_employees_data[dept_name].append(emp)

            # Sort department names for consistent output
            sorted_departments = sorted(grouped_employees_data.keys())

            for dept_name in sorted_departments:
                # Department Header
                worksheet.merge_range(current_row, 0, current_row, total_cols - 1,
                                      f"PHÒNG BAN: {dept_name.upper()}", formats['department_header'])
                current_row += 1

                dept_employees = grouped_employees_data[dept_name]
                for employee in dept_employees:
                    # Employee Data
                    worksheet.write(current_row, 0, employee['stt'], formats['cell'])
                    worksheet.write(current_row, 1, employee['employee_code'], formats['cell'])
                    worksheet.write(current_row, 2, employee['name'], formats['cell_text'])
                    worksheet.write(current_row, 3, employee['department'], formats['cell_text'])
                    worksheet.write(current_row, 4, employee['basic_salary'], formats['cell_number'])

                    col = base_cols
                    employee_total = employee['basic_salary']  # Start with basic salary
                    for allowance_type in allowance_types:
                        amount = allowance_data[employee['id']][allowance_type['id']]['amount']
                        if amount > 0:
                            worksheet.write(current_row, col, amount, formats['cell_number'])
                            employee_total += amount
                        else:
                            worksheet.write(current_row, col, '', formats['cell'])
                        col += 1

                    if employee_total > 0:
                        worksheet.write(current_row, col, employee_total, formats['cell_number'])
                    else:
                        worksheet.write(current_row, col, '', formats['cell'])
                    col += 1
                    worksheet.write(current_row, col, employee['date_of_joining'], formats['cell'])
                    col += 1
                    worksheet.write(current_row, col, employee['employment_years'], formats['cell']) # New column

                    current_row += 1

                # Department Total Row
                dept_stats = data['statistics']['department_totals'][dept_name]
                worksheet.write(current_row, 0, '', formats['department_total_row'])
                worksheet.write(current_row, 1, '', formats['department_total_row'])
                worksheet.write(current_row, 2, f'TỔNG PHÒNG {dept_name.upper()}', formats['department_total_row'])
                worksheet.write(current_row, 3, '', formats['department_total_row'])
                worksheet.write(current_row, 4, '', formats['department_total_row'])  # For Basic Salary

                col = base_cols
                # Write allowance type totals for department
                for allowance_type in allowance_types:
                    type_dept_total = dept_stats['allowance_type_totals'][allowance_type['id']]
                    if type_dept_total > 0:
                        worksheet.write(current_row, col, type_dept_total, formats['department_total_number'])
                    else:
                        worksheet.write(current_row, col, '', formats['department_total_row'])
                    col += 1

                # Write department's total amount (allowances + basic salary)
                if dept_stats['total_amount'] > 0:
                    worksheet.write(current_row, col, dept_stats['total_amount'], formats['department_total_number'])
                else:
                    worksheet.write(current_row, col, '', formats['department_total_row'])
                col += 1
                worksheet.write(current_row, col, '', formats['department_total_row'])  # For Date of Joining
                col += 1
                worksheet.write(current_row, col, '', formats['department_total_row']) # For Seniority
                current_row += 1
                current_row += 1  # Add an empty row after department total

        else:  # Not grouping by department
            for employee in employees:
                # Thông tin cơ bản
                worksheet.write(current_row, 0, employee['stt'], formats['cell'])
                worksheet.write(current_row, 1, employee['employee_code'], formats['cell'])
                worksheet.write(current_row, 2, employee['name'], formats['cell_text'])
                worksheet.write(current_row, 3, employee['department'], formats['cell_text'])
                worksheet.write(current_row, 4, employee['basic_salary'], formats['cell_number'])

                # Dữ liệu phụ cấp
                col = base_cols
                employee_total = employee['basic_salary']  # Start with basic salary
                for allowance_type in allowance_types:
                    amount = allowance_data[employee['id']][allowance_type['id']]['amount']
                    if amount > 0:
                        worksheet.write(current_row, col, amount, formats['cell_number'])
                        employee_total += amount
                    else:
                        worksheet.write(current_row, col, '', formats['cell'])
                    col += 1

                # Tổng nhân viên
                if employee_total > 0:
                    worksheet.write(current_row, col, employee_total, formats['cell_number'])
                else:
                    worksheet.write(current_row, col, '', formats['cell'])
                col += 1  # Move to the next column for Date of Joining

                # Ngày vào làm
                worksheet.write(current_row, col, employee['date_of_joining'], formats['cell'])
                col += 1
                # Thâm niên
                worksheet.write(current_row, col, employee['employment_years'], formats['cell'])

                current_row += 1

        # 7. Dòng tổng cộng (Grand Total)
        worksheet.write(current_row, 0, '', formats['total_row'])
        worksheet.write(current_row, 1, '', formats['total_row'])
        worksheet.write(current_row, 2, 'TỔNG CỘNG', formats['total_row'])
        worksheet.write(current_row, 3, '', formats['total_row'])
        worksheet.write(current_row, 4, '', formats['total_row'])  # For Basic Salary column

        col = base_cols
        grand_total_allowances = 0  # Calculate only allowance totals for type_totals row
        for allowance_type in allowance_types:
            type_total = data['statistics']['type_totals'][allowance_type['id']]['total_amount']
            if type_total > 0:
                worksheet.write(current_row, col, type_total, formats['total_number'])
                grand_total_allowances += type_total
            else:
                worksheet.write(current_row, col, '', formats['total_row'])
            col += 1

        # Grand total (including basic salary)
        grand_total_overall = data['statistics']['total_amount']
        worksheet.write(current_row, col, grand_total_overall, formats['total_number'])
        col += 1  # Move past the total column

        # No total for 'Ngày vào làm' and 'Thâm niên' column
        worksheet.write(current_row, col, '', formats['total_row'])
        col += 1
        worksheet.write(current_row, col, '', formats['total_row'])
        current_row += 1

        # 8. Thống kê tổng hợp
        current_row += 1
        self._write_summary(worksheet, current_row, data['statistics'], formats, total_cols)

    def _write_summary(self, worksheet, start_row, stats, formats, total_cols):
        """Viết phần thống kê tổng hợp"""

        worksheet.merge_range(start_row, 0, start_row, total_cols - 1,
                              'THỐNG KÊ TỔNG HỢP', formats['title'])
        start_row += 1

        summary_data = [
            ['Tổng số nhân viên:', stats['total_employees']],
            ['Số nhân viên có phụ cấp:', stats['employees_with_allowance']],
            ['Tổng số loại phụ cấp:', stats['total_allowance_types']],
            ['Tổng tiền phụ cấp (chỉ phụ cấp):',
             f"{stats['total_taxable_amount'] + stats['total_non_taxable_amount']:,} VNĐ"],  # Only allowance total
            ['Tổng phụ cấp chịu thuế:', f"{stats['total_taxable_amount']:,} VNĐ"],
            ['Tổng phụ cấp không chịu thuế:', f"{stats['total_non_taxable_amount']:,} VNĐ"],
            ['Tổng lương cơ bản:', f"{stats['total_basic_salary']:,} VNĐ"],  # New: total basic salary
            ['Tổng cộng (Lương cơ bản + Phụ cấp):', f"{stats['total_amount']:,} VNĐ"],
            # Overall total including basic salary
        ]

        for i, (label, value) in enumerate(summary_data):
            worksheet.write(start_row + i, 1, label, formats['info'])
            worksheet.write(start_row + i, 2, value, formats['cell'])

    def _setup_worksheet(self, worksheet, data, formats):
        """Thiết lập worksheet"""

        base_cols = 5
        allowance_cols = len(data['allowance_types'])
        total_cols = base_cols + allowance_cols + 3 # New total columns

        # Column widths
        worksheet.set_column(0, 0, 6)  # STT
        worksheet.set_column(1, 1, 12)  # Mã NV
        worksheet.set_column(2, 2, 25)  # Họ tên
        worksheet.set_column(3, 3, 20)  # Phòng ban
        worksheet.set_column(4, 4, 15)  # Lương cơ bản

        # Cột phụ cấp
        for i in range(allowance_cols):
            worksheet.set_column(base_cols + i, base_cols + i, 12)

        # Cột tổng cộng
        worksheet.set_column(base_cols + allowance_cols, base_cols + allowance_cols, 15)
        # Cột Ngày vào làm (the very last column)
        worksheet.set_column(base_cols + allowance_cols + 1, base_cols + allowance_cols + 1, 15)
        # Cột Thâm niên (new column)
        worksheet.set_column(base_cols + allowance_cols + 2, base_cols + allowance_cols + 2, 10)

        # Row heights
        worksheet.set_row(0, 35)  # Title
        worksheet.set_row(1, 25)  # Company
        worksheet.set_row(5, 30)  # Header

        # Freeze panes
        worksheet.freeze_panes(6, base_cols)  # Freeze at header row (6) and base_cols (5)

        # Print settings
        worksheet.set_landscape()
        worksheet.set_paper(9)  # A4
        worksheet.fit_to_pages(1, 0)  # Fit to 1 page wide
        worksheet.set_margins(0.5, 0.5, 0.8, 0.8)