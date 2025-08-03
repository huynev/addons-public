from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import datetime
import base64
import io
import xlsxwriter
import calendar
from dateutil.relativedelta import relativedelta


class HrPayrollExcelExport(models.TransientModel):
    _name = 'hr.payroll.excel.export'
    _description = 'Payroll Excel Export'

    date_from = fields.Date(string='Date From', required=True)
    date_to = fields.Date(string='Date To', required=True)
    department_ids = fields.Many2many('hr.department', string='Departments')
    employee_ids = fields.Many2many('hr.employee', string='Employees')

    # Thêm trường để chọn loại báo cáo
    report_type = fields.Selection([
        ('detailed', 'Báo cáo chi tiết (theo salary rules)'),
        ('summary', 'Báo cáo tổng hợp (theo format chuẩn)')
    ], string='Loại báo cáo', default='detailed', required=True)

    # Thêm trường để chọn trạng thái phiếu lương
    include_draft = fields.Boolean(string='Include Draft Payslips', default=False)
    include_waiting = fields.Boolean(string='Include Waiting Payslips', default=False)
    include_done = fields.Boolean(string='Include Done Payslips', default=True)
    include_rejected = fields.Boolean(string='Include Rejected Payslips', default=False)

    # Thêm trường để hiển thị tăng ca và đi trễ/về sớm
    show_overtime = fields.Boolean(string='Show Overtime', default=True)
    show_late_early = fields.Boolean(string='Show Late/Early', default=True)

    # Thêm trường hiển thị ngày công
    show_workdays = fields.Boolean(string='Show Working Days', default=True)

    group_by_department = fields.Boolean(string='Group by Department', default=True)
    excel_file = fields.Binary('Excel Report', readonly=True)
    file_name = fields.Char('File Name', readonly=True)
    state = fields.Selection([
        ('choose', 'Choose'),
        ('done', 'Done'),
    ], default='choose')

    @api.model
    def default_get(self, fields_list):
        res = super(HrPayrollExcelExport, self).default_get(fields_list)
        today = fields.Date.today()
        # Ngày đầu tháng hiện tại
        first_day = today.replace(day=1)
        # Ngày cuối tháng hiện tại
        last_day = self._get_last_day_of_month(first_day)

        res.update({
            'date_from': first_day,
            'date_to': last_day
        })
        return res

    @api.onchange('date_from')
    def _onchange_date_from(self):
        """Cập nhật date_to là ngày cuối cùng của tháng khi date_from thay đổi"""
        if self.date_from:
            self.date_to = self._get_last_day_of_month(self.date_from)

    def _get_last_day_of_month(self, date):
        """Lấy ngày cuối cùng của tháng"""
        last_day = calendar.monthrange(date.year, date.month)[1]
        return date.replace(day=last_day)

    def action_back_to_choose(self):
        """Quay lại màn hình chọn điều kiện xuất báo cáo"""
        self.ensure_one()
        self.write({
            'state': 'choose'
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'hr.payroll.excel.export',
            'view_mode': 'form',
            'res_id': self.id,
            'views': [(False, 'form')],
            'target': 'new',
        }

    def action_export_excel(self):
        self.ensure_one()

        # Xác định trạng thái phiếu lương được chọn
        states = []
        if self.include_draft:
            states.append('draft')
        if self.include_waiting:
            states.append('verify')
        if self.include_done:
            states.append('done')
        if self.include_rejected:
            states.append('cancel')

        if not states:
            raise UserError(_("Please select at least one payslip state."))

        # Tìm kiếm phiếu lương dựa trên điều kiện
        domain = [
            ('date_from', '>=', self.date_from),
            ('date_to', '<=', self.date_to),
            ('state', 'in', states),
        ]

        if self.employee_ids:
            domain.append(('employee_id', 'in', self.employee_ids.ids))
        elif self.department_ids:
            employees = self.env['hr.employee'].search([('department_id', 'in', self.department_ids.ids)])
            if employees:
                domain.append(('employee_id', 'in', employees.ids))
            else:
                raise UserError(_("No employees found in the selected departments."))

        payslips = self.env['hr.payslip'].search(domain)

        if not payslips:
            raise UserError(_("No payslips found for the selected criteria."))

        # Tạo file Excel
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output)

        # Chọn phương thức tạo báo cáo dựa trên loại báo cáo
        if self.report_type == 'summary':
            self._create_summary_excel_report(workbook, payslips)
        else:
            self._create_excel_report(workbook, payslips)

        workbook.close()
        output.seek(0)

        # Lưu file Excel vào field binary
        report_name = 'Detailed' if self.report_type == 'detailed' else 'Summary'
        file_name = f'Payroll_{report_name}_Report_{self.date_from}_{self.date_to}.xlsx'
        self.write({
            'excel_file': base64.b64encode(output.read()),
            'file_name': file_name,
            'state': 'done'
        })

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'hr.payroll.excel.export',
            'view_mode': 'form',
            'res_id': self.id,
            'views': [(False, 'form')],
            'target': 'new',
        }

    def _create_summary_excel_report(self, workbook, payslips):
        """Tạo báo cáo tổng hợp theo format chuẩn"""
        worksheet = workbook.add_worksheet('Bảng lương tổng hợp')

        # Định dạng
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#D9E1F2',
            'border': 1,
            'align': 'center',
            'valign': 'vcenter',
            'text_wrap': True,
            'font_name': 'Arial',
            'font_size': 10
        })

        title_format = workbook.add_format({
            'bold': True,
            'font_size': 16,
            'align': 'center',
            'valign': 'vcenter',
            'font_name': 'Arial'
        })

        subtitle_format = workbook.add_format({
            'bold': True,
            'font_size': 12,
            'align': 'center',
            'valign': 'vcenter',
            'font_name': 'Arial'
        })

        cell_format = workbook.add_format({
            'border': 1,
            'align': 'left',
            'valign': 'vcenter',
            'font_name': 'Arial',
            'font_size': 10
        })

        number_format = workbook.add_format({
            'border': 1,
            'align': 'right',
            'valign': 'vcenter',
            'num_format': '#,##0',
            'font_name': 'Arial',
            'font_size': 10
        })

        decimal_format = workbook.add_format({
            'border': 1,
            'align': 'right',
            'valign': 'vcenter',
            'num_format': '#,##0.0',
            'font_name': 'Arial',
            'font_size': 10
        })

        total_format = workbook.add_format({
            'bold': True,
            'bg_color': '#D9E1F2',
            'border': 1,
            'align': 'right',
            'valign': 'vcenter',
            'num_format': '#,##0',
            'font_name': 'Arial',
            'font_size': 10
        })

        # Định dạng đặc biệt cho cột Thực lãnh
        net_header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#92D050',
            'border': 1,
            'align': 'center',
            'valign': 'vcenter',
            'text_wrap': True,
            'font_name': 'Arial',
            'font_size': 10
        })

        net_number_format = workbook.add_format({
            'bold': True,
            'bg_color': '#E2EFDA',
            'border': 1,
            'align': 'right',
            'valign': 'vcenter',
            'num_format': '#,##0',
            'font_name': 'Arial',
            'font_size': 10
        })

        net_total_format = workbook.add_format({
            'bold': True,
            'bg_color': '#92D050',
            'border': 1,
            'align': 'right',
            'valign': 'vcenter',
            'num_format': '#,##0',
            'font_name': 'Arial',
            'font_size': 10
        })

        department_format = workbook.add_format({
            'bold': True,
            'bg_color': '#E9E9E9',
            'border': 1,
            'align': 'left',
            'valign': 'vcenter',
            'font_name': 'Arial',
            'font_size': 10
        })

        # Tạo mapping các rule codes với các cột
        rule_mapping = {
            'basic_salary': ['BASIC', 'BASIC_SALARY', 'LUONG_CO_BAN'],
            'salary_amount': ['GROSS', 'TONG_LUONG', 'SALARY'],
            'overtime_amount': ['OT_ALW', 'TANG_CA_TIEN', 'OVERTIME_PAY'],
            'seniority': ['THAM_NIEN', 'SENIORITY', 'SENIOR_ALW'],
            'allowances': ['PHU_CAP', 'ALLOWANCE', 'ALW_'],
            'other_plus': ['CONG_KHAC', 'OTHER_PLUS', 'BONUS'],
            'late_penalty': ['LATE_PEN', 'DI_TRE', 'PENALTY', 'LATE_EAR'],
            'insurance': ['BAO_HIEM', 'INSURANCE', 'BHXH', 'BHYT', 'BHTN'],
            'union_fee': ['CONG_DOAN', 'UNION', 'CD_FEE'],
            'other_minus': ['TRU_KHAC', 'OTHER_MINUS', 'DEDUCTION'],
            'advance': ['TAM_UNG', 'ADVANCE', 'PREPAID'],
            'net_salary': ['NET', 'THUC_LINH', 'NET_SALARY']
        }

        # Tạo dữ liệu tổng hợp cho từng nhân viên
        employee_data = {}

        for slip in payslips:
            employee = slip.employee_id
            if employee.id not in employee_data:
                employee_data[employee.id] = {
                    'employee_code': employee.employee_code or '',
                    'employee_name': employee.name,
                    'department': employee.department_id.name if employee.department_id else 'Không xác định',
                    'basic_salary': 0,
                    'total_workdays': 0,
                    'salary_amount': 0,
                    'overtime_hours': 0,
                    'overtime_amount': 0,
                    'seniority': 0,
                    'total_allowances': 0,
                    'other_plus': 0,
                    'late_penalty': 0,
                    'insurance': 0,
                    'union_fee': 0,
                    'other_minus': 0,
                    'advance': 0,
                    'net_salary': 0
                }

            # Lấy thông tin ngày công
            if hasattr(slip, 'worked_days_line_ids'):
                total_days = 0
                for worked_days in slip.worked_days_line_ids:
                    if worked_days.code == 'WORK100' or 'NGAY_CONG' in worked_days.code or 'NORMAL' in worked_days.code:
                        total_days += worked_days.number_of_days
                    if worked_days.code == 'LEAVE110':
                        total_days -= worked_days.number_of_days
                employee_data[employee.id]['total_workdays'] = total_days
            else:
                employee_data[employee.id]['total_workdays'] = 22.0

            # Lấy giờ tăng ca
            if hasattr(slip, 'overtime_hours'):
                employee_data[employee.id]['overtime_hours'] = slip.overtime_hours or 0

            # Xử lý các salary rules
            for line in slip.line_ids:
                rule_code = line.salary_rule_id.code.upper()
                rule_name = line.salary_rule_id.name.upper()
                amount = line.total

                # Mapping rules với các cột
                if any(code in rule_code for code in rule_mapping['basic_salary']) or any(
                        name in rule_name for name in ['LƯƠNG CƠ BẢN', 'LUONG CO BAN']):
                    employee_data[employee.id]['basic_salary'] += amount

                elif any(code in rule_code for code in rule_mapping['salary_amount']) or any(
                        name in rule_name for name in ['TỔNG LƯƠNG', 'TONG LUONG']):
                    employee_data[employee.id]['salary_amount'] += amount

                elif any(code in rule_code for code in rule_mapping['overtime_amount']) or any(
                        name in rule_name for name in ['TĂNG CA', 'TANG CA']):
                    employee_data[employee.id]['overtime_amount'] += amount

                elif any(code in rule_code for code in rule_mapping['seniority']) or any(
                        name in rule_name for name in ['THÂM NIÊN', 'THAM NIEN']):
                    employee_data[employee.id]['seniority'] += amount

                elif any(code in rule_code for code in rule_mapping['allowances']) or any(
                        name in rule_name for name in ['PHỤ CẤP', 'PHU CAP']):
                    employee_data[employee.id]['total_allowances'] += amount

                elif any(code in rule_code for code in rule_mapping['other_plus']) or any(
                        name in rule_name for name in ['CỘNG KHÁC', 'CONG KHAC', 'THƯỞNG', 'THUONG']):
                    employee_data[employee.id]['other_plus'] += amount

                elif any(code in rule_code for code in rule_mapping['late_penalty']) or any(
                        name in rule_name for name in ['ĐI TRỄ', 'DI TRE', 'PHẠT', 'PHAT']):
                    employee_data[employee.id]['late_penalty'] += abs(amount)  # Đảm bảo là số dương

                elif any(code in rule_code for code in rule_mapping['insurance']) or any(
                        name in rule_name for name in ['BẢO HIỂM', 'BAO HIEM']):
                    employee_data[employee.id]['insurance'] += abs(amount)  # Đảm bảo là số dương

                elif any(code in rule_code for code in rule_mapping['union_fee']) or any(
                        name in rule_name for name in ['CÔNG ĐOÀN', 'CONG DOAN']):
                    employee_data[employee.id]['union_fee'] += abs(amount)  # Đảm bảo là số dương

                elif any(code in rule_code for code in rule_mapping['other_minus']) or any(
                        name in rule_name for name in ['TRỪ KHÁC', 'TRU KHAC']):
                    employee_data[employee.id]['other_minus'] += abs(amount)  # Đảm bảo là số dương

                elif any(code in rule_code for code in rule_mapping['advance']) or any(
                        name in rule_name for name in ['TẠM ỨNG', 'TAM UNG']):
                    employee_data[employee.id]['advance'] += abs(amount)  # Đảm bảo là số dương

                elif any(code in rule_code for code in rule_mapping['net_salary']) or any(
                        name in rule_name for name in ['THỰC LĨNH', 'THUC LINH']):
                    employee_data[employee.id]['net_salary'] += amount

        # Bắt đầu viết dữ liệu vào Excel
        row = 0

        # Tiêu đề công ty
        worksheet.merge_range(row, 0, row, 16, 'CÔNG TY CỔ PHẦN MINH ĐỨC', title_format)
        row += 1

        # Tiêu đề báo cáo
        worksheet.merge_range(row, 0, row, 16, 'BẢNG TỔNG HỢP TIỀN LƯƠNG', title_format)
        row += 1

        # Kỳ báo cáo
        month_year = self.date_from.strftime('Tháng %m năm %Y')
        worksheet.merge_range(row, 0, row, 16, month_year, subtitle_format)
        row += 2

        # Header
        headers = [
            'STT', 'Mã NV', 'Họ và tên', 'Mức lương cơ bản', 'Tổng số công',
            'Số tiền lương', 'Giờ tăng ca', 'Số tiền tăng ca', 'Tiền thâm niên',
            'Tổng tiền phụ cấp', 'Cộng khác', 'Đi trễ, nghỉ không phép',
            'Bảo hiểm', 'Tiền phí công đoàn', 'Trừ khác', 'Tạm ứng', 'Thực lãnh'
        ]

        for col, header in enumerate(headers):
            if header == 'Thực lãnh':
                worksheet.write(row, col, header, net_header_format)
            else:
                worksheet.write(row, col, header, header_format)

        row += 1

        # Data
        if self.group_by_department:
            # Nhóm theo phòng ban
            departments = {}
            for emp_id, data in employee_data.items():
                dept = data['department']
                if dept not in departments:
                    departments[dept] = []
                departments[dept].append(data)

            for dept_name, dept_employees in departments.items():
                # Tiêu đề phòng ban
                worksheet.merge_range(row, 0, row, 16, f'Phòng ban: {dept_name}', department_format)
                row += 1

                # Dữ liệu nhân viên
                count = 1
                dept_totals = {
                    'basic_salary': 0, 'total_workdays': 0, 'salary_amount': 0,
                    'overtime_hours': 0, 'overtime_amount': 0, 'seniority': 0,
                    'total_allowances': 0, 'other_plus': 0, 'late_penalty': 0,
                    'insurance': 0, 'union_fee': 0, 'other_minus': 0,
                    'advance': 0, 'net_salary': 0
                }

                # Sắp xếp theo mã nhân viên
                sorted_employees = sorted(dept_employees, key=lambda x: x['employee_code'] or '')

                for data in sorted_employees:
                    col = 0
                    worksheet.write(row, col, count, cell_format)
                    col += 1
                    worksheet.write(row, col, data['employee_code'], cell_format)
                    col += 1
                    worksheet.write(row, col, data['employee_name'], cell_format)
                    col += 1
                    worksheet.write(row, col, data['basic_salary'], number_format)
                    col += 1
                    worksheet.write(row, col, data['total_workdays'], decimal_format)
                    col += 1
                    worksheet.write(row, col, data['salary_amount'], number_format)
                    col += 1
                    worksheet.write(row, col, data['overtime_hours'], decimal_format)
                    col += 1
                    worksheet.write(row, col, data['overtime_amount'], number_format)
                    col += 1
                    worksheet.write(row, col, data['seniority'], number_format)
                    col += 1
                    worksheet.write(row, col, data['total_allowances'], number_format)
                    col += 1
                    worksheet.write(row, col, data['other_plus'], number_format)
                    col += 1
                    worksheet.write(row, col, data['late_penalty'], number_format)
                    col += 1
                    worksheet.write(row, col, data['insurance'], number_format)
                    col += 1
                    worksheet.write(row, col, data['union_fee'], number_format)
                    col += 1
                    worksheet.write(row, col, data['other_minus'], number_format)
                    col += 1
                    worksheet.write(row, col, data['advance'], number_format)
                    col += 1
                    worksheet.write(row, col, data['net_salary'], net_number_format)

                    # Tính tổng phòng ban
                    for key in dept_totals:
                        dept_totals[key] += data[key]

                    row += 1
                    count += 1

                # Tổng phòng ban
                col = 0
                worksheet.merge_range(row, col, row, 2, 'Tổng phòng ban:', total_format)
                col += 3
                worksheet.write(row, col, dept_totals['basic_salary'], total_format)
                col += 1
                worksheet.write(row, col, dept_totals['total_workdays'], total_format)
                col += 1
                worksheet.write(row, col, dept_totals['salary_amount'], total_format)
                col += 1
                worksheet.write(row, col, dept_totals['overtime_hours'], total_format)
                col += 1
                worksheet.write(row, col, dept_totals['overtime_amount'], total_format)
                col += 1
                worksheet.write(row, col, dept_totals['seniority'], total_format)
                col += 1
                worksheet.write(row, col, dept_totals['total_allowances'], total_format)
                col += 1
                worksheet.write(row, col, dept_totals['other_plus'], total_format)
                col += 1
                worksheet.write(row, col, dept_totals['late_penalty'], total_format)
                col += 1
                worksheet.write(row, col, dept_totals['insurance'], total_format)
                col += 1
                worksheet.write(row, col, dept_totals['union_fee'], total_format)
                col += 1
                worksheet.write(row, col, dept_totals['other_minus'], total_format)
                col += 1
                worksheet.write(row, col, dept_totals['advance'], total_format)
                col += 1
                worksheet.write(row, col, dept_totals['net_salary'], net_total_format)

                row += 2
        else:
            # Không nhóm theo phòng ban
            count = 1
            grand_totals = {
                'basic_salary': 0, 'total_workdays': 0, 'salary_amount': 0,
                'overtime_hours': 0, 'overtime_amount': 0, 'seniority': 0,
                'total_allowances': 0, 'other_plus': 0, 'late_penalty': 0,
                'insurance': 0, 'union_fee': 0, 'other_minus': 0,
                'advance': 0, 'net_salary': 0
            }

            # Sắp xếp theo mã nhân viên
            sorted_employees = sorted(employee_data.values(), key=lambda x: x['employee_code'] or '')

            for data in sorted_employees:
                col = 0
                worksheet.write(row, col, count, cell_format)
                col += 1
                worksheet.write(row, col, data['employee_code'], cell_format)
                col += 1
                worksheet.write(row, col, data['employee_name'], cell_format)
                col += 1
                worksheet.write(row, col, data['basic_salary'], number_format)
                col += 1
                worksheet.write(row, col, data['total_workdays'], decimal_format)
                col += 1
                worksheet.write(row, col, data['salary_amount'], number_format)
                col += 1
                worksheet.write(row, col, data['overtime_hours'], decimal_format)
                col += 1
                worksheet.write(row, col, data['overtime_amount'], number_format)
                col += 1
                worksheet.write(row, col, data['seniority'], number_format)
                col += 1
                worksheet.write(row, col, data['total_allowances'], number_format)
                col += 1
                worksheet.write(row, col, data['other_plus'], number_format)
                col += 1
                worksheet.write(row, col, data['late_penalty'], number_format)
                col += 1
                worksheet.write(row, col, data['insurance'], number_format)
                col += 1
                worksheet.write(row, col, data['union_fee'], number_format)
                col += 1
                worksheet.write(row, col, data['other_minus'], number_format)
                col += 1
                worksheet.write(row, col, data['advance'], number_format)
                col += 1
                worksheet.write(row, col, data['net_salary'], net_number_format)

                # Tính tổng chung
                for key in grand_totals:
                    grand_totals[key] += data[key]

                row += 1
                count += 1

            # Tổng chung
            col = 0
            worksheet.merge_range(row, col, row, 2, 'Tổng cộng:', total_format)
            col += 3
            worksheet.write(row, col, grand_totals['basic_salary'], total_format)
            col += 1
            worksheet.write(row, col, grand_totals['total_workdays'], total_format)
            col += 1
            worksheet.write(row, col, grand_totals['salary_amount'], total_format)
            col += 1
            worksheet.write(row, col, grand_totals['overtime_hours'], total_format)
            col += 1
            worksheet.write(row, col, grand_totals['overtime_amount'], total_format)
            col += 1
            worksheet.write(row, col, grand_totals['seniority'], total_format)
            col += 1
            worksheet.write(row, col, grand_totals['total_allowances'], total_format)
            col += 1
            worksheet.write(row, col, grand_totals['other_plus'], total_format)
            col += 1
            worksheet.write(row, col, grand_totals['late_penalty'], total_format)
            col += 1
            worksheet.write(row, col, grand_totals['insurance'], total_format)
            col += 1
            worksheet.write(row, col, grand_totals['union_fee'], total_format)
            col += 1
            worksheet.write(row, col, grand_totals['other_minus'], total_format)
            col += 1
            worksheet.write(row, col, grand_totals['advance'], total_format)
            col += 1
            worksheet.write(row, col, grand_totals['net_salary'], net_total_format)

        # Cố định độ rộng cột
        worksheet.set_column('A:A', 5)  # STT
        worksheet.set_column('B:B', 10)  # Mã NV
        worksheet.set_column('C:C', 25)  # Họ và tên
        worksheet.set_column('D:Q', 12)  # Các cột số liệu

    def _create_excel_report(self, workbook, payslips):
        # Tạo trang tính chính (báo cáo chi tiết cũ)
        worksheet = workbook.add_worksheet('Bảng lương tổng')

        # Định dạng
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#D9E1F2',
            'border': 1,
            'align': 'center',
            'valign': 'vcenter',
            'text_wrap': True,
            'font_name': 'Arial',
            'font_size': 10
        })

        title_format = workbook.add_format({
            'bold': True,
            'font_size': 16,
            'align': 'center',
            'valign': 'vcenter',
            'font_name': 'Arial'
        })

        subtitle_format = workbook.add_format({
            'bold': True,
            'font_size': 12,
            'align': 'center',
            'valign': 'vcenter',
            'font_name': 'Arial'
        })

        date_format = workbook.add_format({
            'align': 'center',
            'valign': 'vcenter',
            'font_name': 'Arial',
            'font_size': 10
        })

        cell_format = workbook.add_format({
            'border': 1,
            'align': 'left',
            'valign': 'vcenter',
            'font_name': 'Arial',
            'font_size': 10
        })

        number_format = workbook.add_format({
            'border': 1,
            'align': 'right',
            'valign': 'vcenter',
            'num_format': '#,##0',
            'font_name': 'Arial',
            'font_size': 10
        })

        total_format = workbook.add_format({
            'bold': True,
            'bg_color': '#D9E1F2',
            'border': 1,
            'align': 'right',
            'valign': 'vcenter',
            'num_format': '#,##0',
            'font_name': 'Arial',
            'font_size': 10
        })

        department_format = workbook.add_format({
            'bold': True,
            'bg_color': '#E9E9E9',
            'border': 1,
            'align': 'left',
            'valign': 'vcenter',
            'font_name': 'Arial',
            'font_size': 10
        })

        # Định dạng đặc biệt cho cột NET
        net_header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#92D050',  # Màu xanh lá
            'border': 1,
            'align': 'center',
            'valign': 'vcenter',
            'text_wrap': True,
            'font_name': 'Arial',
            'font_size': 10
        })

        net_number_format = workbook.add_format({
            'bold': True,
            'bg_color': '#E2EFDA',  # Màu xanh lá nhạt
            'border': 1,
            'align': 'right',
            'valign': 'vcenter',
            'num_format': '#,##0',
            'font_name': 'Arial',
            'font_size': 10
        })

        net_total_format = workbook.add_format({
            'bold': True,
            'bg_color': '#92D050',  # Màu xanh lá
            'border': 1,
            'align': 'right',
            'valign': 'vcenter',
            'num_format': '#,##0',
            'font_name': 'Arial',
            'font_size': 10
        })

        # Định dạng cột Ngày công
        workday_header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#9BC2E6',  # Màu xanh dương nhạt
            'border': 1,
            'align': 'center',
            'valign': 'vcenter',
            'text_wrap': True,
            'font_name': 'Arial',
            'font_size': 10
        })

        workday_number_format = workbook.add_format({
            'border': 1,
            'align': 'right',
            'valign': 'vcenter',
            'num_format': '#,##0.0',
            'font_name': 'Arial',
            'font_size': 10
        })

        workday_total_format = workbook.add_format({
            'bold': True,
            'bg_color': '#9BC2E6',  # Màu xanh dương nhạt
            'border': 1,
            'align': 'right',
            'valign': 'vcenter',
            'num_format': '#,##0.0',
            'font_name': 'Arial',
            'font_size': 10
        })

        # Lấy tất cả các mã lương (salary rules) độc nhất từ tất cả phiếu lương
        all_rules = {}
        all_rule_codes = set()
        for slip in payslips:
            for line in slip.line_ids:
                all_rule_codes.add(line.salary_rule_id.id)

        # Lấy thông tin và sequence của tất cả các salary rules
        salary_rules = self.env['hr.salary.rule'].browse(list(all_rule_codes))

        # Tạo từ điển rule_id -> (code, name, sequence)
        net_rule_id = None  # Để lưu ID của quy tắc NET
        late_ear_rule_id = None  # Để lưu ID của quy tắc LATE-EAR
        ot_alw_rule_id = None  # Để lưu ID của quy tắc Phụ cấp tăng ca (OT_ALW)
        basic_rule_id = None  # Để lưu ID của quy tắc Lương cơ bản (BASIC)

        for rule in salary_rules:
            all_rules[rule.id] = {
                'code': rule.code,
                'name': rule.name,
                'sequence': rule.sequence or 0
            }
            # Xác định quy tắc NET dựa trên mã hoặc tên
            if rule.code == 'NET' or 'NET' in rule.code or 'THỰC LĨNH' in rule.name.upper() or 'THUC LINH' in rule.name.upper():
                net_rule_id = rule.id
            # Xác định quy tắc LATE-EAR
            if rule.code == 'LATE-EAR' or rule.code == 'LATE_EAR':
                late_ear_rule_id = rule.id
            # Xác định quy tắc Phụ cấp tăng ca (OT_ALW)
            if rule.code == 'OT_ALW':
                ot_alw_rule_id = rule.id
            # Xác định quy tắc Lương cơ bản (BASIC)
            if rule.code == 'BASIC' or rule.code == 'BASIC_SALARY' or 'LƯƠNG CƠ BẢN' in rule.name.upper() or 'LUONG CO BAN' in rule.name.upper():
                basic_rule_id = rule.id

        # Sắp xếp mã lương theo sequence
        sorted_rules = sorted(
            [(rule_id, all_rules[rule_id]['code'], all_rules[rule_id]['name'])
             for rule_id in all_rules],
            key=lambda x: all_rules[x[0]]['sequence']
        )

        # Tổ chức dữ liệu theo nhân viên hoặc phòng ban
        payslips_data = {}
        departments_data = {}

        # Nhóm phiếu lương theo nhân viên và mã phiếu lương
        payslips_by_employee_slip = {}

        for slip in payslips:
            employee = slip.employee_id
            key = (employee, slip.id)  # Dùng tuple (nhân viên, mã phiếu lương) làm key
            payslips_by_employee_slip[key] = slip

        # Xử lý dữ liệu cho từng nhân viên và phiếu lương
        employee_slip_data = {}

        for (employee, slip_id), slip in payslips_by_employee_slip.items():
            department = employee.department_id

            if not department and self.group_by_department:
                department_name = 'Không xác định'
            elif self.group_by_department:
                department_name = department.name

            if self.group_by_department:
                if department_name not in departments_data:
                    departments_data[department_name] = {}

            # Lưu trữ dữ liệu theo nhân viên và phiếu lương
            key = (employee, slip_id)
            employee_slip_data[key] = {
                'employee_id': employee.id,
                'employee_code': employee.employee_code or '',
                'employee_name': employee.name,
                'payslip_id': slip_id,
                'payslip_number': slip.number or f'PS{slip_id}',  # Sử dụng số phiếu lương hoặc tạo mã tạm
                'department': department.name if department else 'Không xác định',
                'position': employee.job_id.name if employee.job_id else '',
                'rules': {rule_id: 0 for rule_id, _, _ in sorted_rules},
                'overtime_hours': 0,
                'late_early_minutes': 0,
                'working_days': 0  # Thêm trường ngày công
            }

            # Tính tổng từ phiếu lương
            for line in slip.line_ids:
                rule_id = line.salary_rule_id.id
                employee_slip_data[key]['rules'][rule_id] = line.total

            # Thêm dữ liệu tăng ca và đi trễ về sớm
            if hasattr(slip, 'overtime_hours'):
                employee_slip_data[key]['overtime_hours'] = slip.overtime_hours or 0
            if hasattr(slip, 'total_penalty_minutes'):
                employee_slip_data[key]['late_early_minutes'] = slip.total_penalty_minutes or 0

            # Thêm dữ liệu ngày công
            if hasattr(slip, 'worked_days_line_ids'):
                # Tổng hợp ngày công từ worked_days_line_ids
                total_days = 0
                for worked_days in slip.worked_days_line_ids:
                    # Chỉ tính ngày công thực tế, bỏ qua nghỉ phép, nghỉ lễ, ...
                    if worked_days.code == 'WORK100' or 'NGAY_CONG' in worked_days.code or 'NORMAL' in worked_days.code:
                        employee_slip_data[key]['working_days'] = worked_days.number_of_days
            else:
                # Nếu không có dữ liệu ngày công, có thể tính toán từ payslip
                # Sử dụng số ngày làm việc mặc định trong tháng (ví dụ: 22 ngày)
                employee_slip_data[key]['working_days'] = 22.0

            # Thêm vào dữ liệu phòng ban nếu cần
            if self.group_by_department:
                if key not in departments_data[department_name]:
                    departments_data[department_name][key] = employee_slip_data[key]

        # Bắt đầu viết dữ liệu vào Excel
        row = 0

        # Tiêu đề công ty
        worksheet.merge_range(row, 0, row, len(sorted_rules) + (1 if self.show_overtime else 0) + (
            1 if self.show_late_early else 0) + (1 if self.show_workdays else 0) + 2,
                              'CÔNG TY CỔ PHẦN MINH ĐỨC',
                              title_format)
        row += 1

        # Tiêu đề báo cáo
        worksheet.merge_range(row, 0, row, len(sorted_rules) + (1 if self.show_overtime else 0) + (
            1 if self.show_late_early else 0) + (1 if self.show_workdays else 0) + 2,
                              'BẢNG TỔNG HỢP TIỀN LƯƠNG',
                              title_format)
        row += 1

        # Kỳ báo cáo
        month_year = self.date_from.strftime('Tháng %m năm %Y')
        worksheet.merge_range(row, 0, row, len(sorted_rules) + (1 if self.show_overtime else 0) + (
            1 if self.show_late_early else 0) + (1 if self.show_workdays else 0) + 2,
                              month_year,
                              subtitle_format)
        row += 2

        # Header
        col = 0
        worksheet.write(row, col, 'STT', header_format)
        col += 1
        worksheet.write(row, col, 'Mã NV', header_format)
        col += 1
        worksheet.write(row, col, 'Họ và tên', header_format)
        col += 1
        worksheet.write(row, col, 'Mã phiếu lương', header_format)
        col += 1

        if not self.group_by_department:
            worksheet.write(row, col, 'Phòng ban', header_format)
            col += 1
            worksheet.write(row, col, 'Chức vụ', header_format)
            col += 1

        # Các cột lương
        net_col_index = None  # Lưu vị trí cột NET
        late_ear_col_index = None  # Lưu vị trí cột LATE-EAR
        ot_alw_col_index = None  # Lưu vị trí cột OT_ALW
        basic_col_index = None  # Lưu vị trí cột BASIC
        late_early_col_inserted = False  # Đánh dấu nếu cột đi trễ/về sớm đã được chèn
        overtime_col_inserted = False  # Đánh dấu nếu cột tăng ca đã được chèn
        workday_col_inserted = False  # Đánh dấu nếu cột ngày công đã được chèn

        # Lưu các cột tùy chỉnh để xử lý sau này
        custom_columns = {}
        if self.show_overtime:
            custom_columns['overtime'] = {'title': 'Tăng ca (giờ)', 'format': header_format}
        if self.show_late_early:
            custom_columns['late_early'] = {'title': 'Đi trễ/Về sớm (phút)', 'format': header_format}
        if self.show_workdays and not basic_rule_id:
            custom_columns['working_days'] = {'title': 'Ngày công', 'format': workday_header_format}

        # Viết các cột salary rule
        for i, (rule_id, rule_code, rule_name) in enumerate(sorted_rules):
            # Kiểm tra xem đây có phải là cột NET không
            if rule_id == net_rule_id:
                worksheet.write(row, col, f'{rule_name}\n({rule_code})', net_header_format)
                net_col_index = col
            else:
                worksheet.write(row, col, f'{rule_name}\n({rule_code})', header_format)

            # Nếu đây là cột BASIC và cần hiển thị ngày công
            if rule_id == basic_rule_id and self.show_workdays:
                basic_col_index = col

                # Chèn cột Ngày công ngay sau BASIC
                col += 1
                worksheet.write(row, col, 'Ngày công', workday_header_format)
                workday_col_inserted = True
                if 'working_days' in custom_columns:
                    del custom_columns['working_days']  # Đã chèn rồi, không cần chèn lại

            # Nếu đây là cột LATE-EAR và cần hiển thị đi trễ/về sớm
            if rule_id == late_ear_rule_id:
                late_ear_col_index = col

                # Chèn cột đi trễ/về sớm ngay sau LATE-EAR
                if self.show_late_early:
                    col += 1
                    worksheet.write(row, col, 'Đi trễ/Về sớm (phút)', header_format)
                    late_early_col_inserted = True
                    if 'late_early' in custom_columns:
                        del custom_columns['late_early']  # Đã chèn rồi, không cần chèn lại

            # Nếu đây là cột OT_ALW và cần hiển thị tăng ca
            if rule_id == ot_alw_rule_id:
                ot_alw_col_index = col

                # Chèn cột tăng ca ngay sau OT_ALW
                if self.show_overtime:
                    col += 1
                    worksheet.write(row, col, 'Tăng ca (giờ)', header_format)
                    overtime_col_inserted = True
                    if 'overtime' in custom_columns:
                        del custom_columns['overtime']  # Đã chèn rồi, không cần chèn lại

            col += 1

        # Thêm các cột còn lại nếu có
        for column_key, column_data in custom_columns.items():
            worksheet.write(row, col, column_data['title'], column_data['format'])
            col += 1

        row += 1

        # Data
        if self.group_by_department:
            # Nhóm theo phòng ban
            for dept_name, dept_slips in departments_data.items():
                # Tiêu đề phòng ban
                worksheet.merge_range(row, 0, row, len(sorted_rules) + len(custom_columns) + (
                    1 if late_early_col_inserted else 0) + (1 if overtime_col_inserted else 0) + (
                                          1 if workday_col_inserted else 0) + 3,
                                      f'Phòng ban: {dept_name}',
                                      department_format)
                row += 1

                # Dữ liệu nhân viên và phiếu lương
                count = 1
                dept_total = {rule[0]: 0 for rule in sorted_rules}
                dept_overtime_hours = 0
                dept_late_early_minutes = 0
                dept_working_days = 0

                # Sắp xếp theo mã nhân viên và mã phiếu lương
                sorted_slips = sorted(dept_slips.items(),
                                      key=lambda x: (x[1]['employee_code'] or '', x[1]['payslip_number'] or ''))

                for (employee, slip_id), data in sorted_slips:
                    col = 0
                    worksheet.write(row, col, count, cell_format)
                    col += 1
                    worksheet.write(row, col, data['employee_code'], cell_format)
                    col += 1
                    worksheet.write(row, col, data['employee_name'], cell_format)
                    col += 1
                    worksheet.write(row, col, data['payslip_number'], cell_format)
                    col += 1

                    # Viết các giá trị cho từng quy tắc lương
                    for i, (rule_id, rule_code, rule_name) in enumerate(sorted_rules):
                        value = data['rules'].get(rule_id, 0)
                        # Sử dụng định dạng đặc biệt cho cột NET
                        if rule_id == net_rule_id:
                            worksheet.write(row, col, value, net_number_format)
                        else:
                            worksheet.write(row, col, value, number_format)
                        dept_total[rule_id] += value

                        # Nếu đây là cột BASIC và cần hiển thị ngày công
                        if rule_id == basic_rule_id and self.show_workdays and workday_col_inserted:
                            col += 1
                            working_days = data['working_days']
                            worksheet.write(row, col, working_days, workday_number_format)
                            dept_working_days += working_days

                        # Nếu đây là cột LATE-EAR và cần hiển thị đi trễ/về sớm
                        if rule_id == late_ear_rule_id and self.show_late_early and late_early_col_inserted:
                            col += 1
                            late_early_minutes = data['late_early_minutes']
                            worksheet.write(row, col, late_early_minutes, number_format)
                            dept_late_early_minutes += late_early_minutes

                        # Nếu đây là cột OT_ALW và cần hiển thị tăng ca
                        if rule_id == ot_alw_rule_id and self.show_overtime and overtime_col_inserted:
                            col += 1
                            overtime_hours = data['overtime_hours']
                            worksheet.write(row, col, overtime_hours, number_format)
                            dept_overtime_hours += overtime_hours

                        col += 1

                    # Thêm dữ liệu tăng ca nếu được chọn và chưa được xử lý
                    if self.show_overtime and 'overtime' in custom_columns:
                        overtime_hours = data['overtime_hours']
                        worksheet.write(row, col, overtime_hours, number_format)
                        col += 1
                        dept_overtime_hours += overtime_hours

                    # Thêm dữ liệu đi trễ/về sớm nếu được chọn và chưa được xử lý
                    if self.show_late_early and 'late_early' in custom_columns:
                        late_early_minutes = data['late_early_minutes']
                        worksheet.write(row, col, late_early_minutes, number_format)
                        col += 1
                        dept_late_early_minutes += late_early_minutes

                    # Thêm dữ liệu ngày công nếu được chọn và chưa được xử lý
                    if self.show_workdays and 'working_days' in custom_columns:
                        working_days = data['working_days']
                        worksheet.write(row, col, working_days, workday_number_format)
                        col += 1
                        dept_working_days += working_days

                    row += 1
                    count += 1

                # Tổng của phòng ban
                col = 0
                worksheet.merge_range(row, col, row, 3, 'Tổng phòng ban:', total_format)
                col += 4

                # Viết tổng cho từng quy tắc lương
                for i, (rule_id, _, _) in enumerate(sorted_rules):
                    # Sử dụng định dạng đặc biệt cho tổng cột NET
                    if rule_id == net_rule_id:
                        worksheet.write(row, col, dept_total[rule_id], net_total_format)
                    else:
                        worksheet.write(row, col, dept_total[rule_id], total_format)

                    # Nếu đây là cột BASIC và cần hiển thị ngày công
                    if rule_id == basic_rule_id and self.show_workdays and workday_col_inserted:
                        col += 1
                        worksheet.write(row, col, dept_working_days, workday_total_format)

                    # Nếu đây là cột LATE-EAR và cần hiển thị đi trễ/về sớm
                    if rule_id == late_ear_rule_id and self.show_late_early and late_early_col_inserted:
                        col += 1
                        worksheet.write(row, col, dept_late_early_minutes, total_format)

                    # Nếu đây là cột OT_ALW và cần hiển thị tăng ca
                    if rule_id == ot_alw_rule_id and self.show_overtime and overtime_col_inserted:
                        col += 1
                        worksheet.write(row, col, dept_overtime_hours, total_format)

                    col += 1

                # Tổng tăng ca của phòng ban
                if self.show_overtime and 'overtime' in custom_columns:
                    worksheet.write(row, col, dept_overtime_hours, total_format)
                    col += 1

                # Tổng đi trễ/về sớm của phòng ban (nếu chưa được xử lý)
                if self.show_late_early and 'late_early' in custom_columns:
                    worksheet.write(row, col, dept_late_early_minutes, total_format)
                    col += 1

                # Tổng ngày công của phòng ban (nếu chưa được xử lý)
                if self.show_workdays and 'working_days' in custom_columns:
                    worksheet.write(row, col, dept_working_days, workday_total_format)
                    col += 1

                row += 2
        else:
            # Không nhóm theo phòng ban
            count = 1
            grand_total = {rule[0]: 0 for rule in sorted_rules}
            total_overtime_hours = 0
            total_late_early_minutes = 0
            total_working_days = 0

            # Sắp xếp theo mã nhân viên và mã phiếu lương
            sorted_slips = sorted(employee_slip_data.items(),
                                  key=lambda x: (x[1]['employee_code'] or '', x[1]['payslip_number'] or ''))

            for (employee, slip_id), data in sorted_slips:
                col = 0
                worksheet.write(row, col, count, cell_format)
                col += 1
                worksheet.write(row, col, data['employee_code'], cell_format)
                col += 1
                worksheet.write(row, col, data['employee_name'], cell_format)
                col += 1
                worksheet.write(row, col, data['payslip_number'], cell_format)
                col += 1
                worksheet.write(row, col, data['department'], cell_format)
                col += 1
                worksheet.write(row, col, data['position'], cell_format)
                col += 1

                for i, (rule_id, rule_code, rule_name) in enumerate(sorted_rules):
                    value = data['rules'].get(rule_id, 0)
                    # Sử dụng định dạng đặc biệt cho cột NET
                    if rule_id == net_rule_id:
                        worksheet.write(row, col, value, net_number_format)
                    else:
                        worksheet.write(row, col, value, number_format)
                    grand_total[rule_id] += value

                    # Nếu đây là cột BASIC và cần hiển thị ngày công
                    if rule_id == basic_rule_id and self.show_workdays and workday_col_inserted:
                        col += 1
                        working_days = data['working_days']
                        worksheet.write(row, col, working_days, workday_number_format)
                        total_working_days += working_days

                    # Nếu đây là cột LATE-EAR và cần hiển thị đi trễ/về sớm
                    if rule_id == late_ear_rule_id and self.show_late_early and late_early_col_inserted:
                        col += 1
                        late_early_minutes = data['late_early_minutes']
                        worksheet.write(row, col, late_early_minutes, number_format)
                        total_late_early_minutes += late_early_minutes

                    # Nếu đây là cột OT_ALW và cần hiển thị tăng ca
                    if rule_id == ot_alw_rule_id and self.show_overtime and overtime_col_inserted:
                        col += 1
                        overtime_hours = data['overtime_hours']
                        worksheet.write(row, col, overtime_hours, number_format)
                        total_overtime_hours += overtime_hours

                    col += 1

                # Thêm dữ liệu tăng ca nếu được chọn và chưa được xử lý
                if self.show_overtime and 'overtime' in custom_columns:
                    overtime_hours = data['overtime_hours']
                    worksheet.write(row, col, overtime_hours, number_format)
                    col += 1
                    total_overtime_hours += overtime_hours

                # Thêm dữ liệu đi trễ/về sớm nếu được chọn và chưa được xử lý
                if self.show_late_early and 'late_early' in custom_columns:
                    late_early_minutes = data['late_early_minutes']
                    worksheet.write(row, col, late_early_minutes, number_format)
                    col += 1
                    total_late_early_minutes += late_early_minutes

                # Thêm dữ liệu ngày công nếu được chọn và chưa được xử lý
                if self.show_workdays and 'working_days' in custom_columns:
                    working_days = data['working_days']
                    worksheet.write(row, col, working_days, workday_number_format)
                    col += 1
                    total_working_days += working_days

                row += 1
                count += 1

            # Tổng chung
            col = 0
            worksheet.merge_range(row, col, row, 5, 'Tổng cộng:', total_format)
            col += 6

            for i, (rule_id, _, _) in enumerate(sorted_rules):
                # Sử dụng định dạng đặc biệt cho tổng cột NET
                if rule_id == net_rule_id:
                    worksheet.write(row, col, grand_total[rule_id], net_total_format)
                else:
                    worksheet.write(row, col, grand_total[rule_id], total_format)

                # Nếu đây là cột BASIC và cần hiển thị ngày công
                if rule_id == basic_rule_id and self.show_workdays and workday_col_inserted:
                    col += 1
                    worksheet.write(row, col, total_working_days, workday_total_format)

                # Nếu đây là cột LATE-EAR và cần hiển thị đi trễ/về sớm
                if rule_id == late_ear_rule_id and self.show_late_early and late_early_col_inserted:
                    col += 1
                    worksheet.write(row, col, total_late_early_minutes, total_format)

                # Nếu đây là cột OT_ALW và cần hiển thị tăng ca
                if rule_id == ot_alw_rule_id and self.show_overtime and overtime_col_inserted:
                    col += 1
                    worksheet.write(row, col, total_overtime_hours, total_format)

                col += 1

            # Tổng tăng ca
            if self.show_overtime and 'overtime' in custom_columns:
                worksheet.write(row, col, total_overtime_hours, total_format)
                col += 1

            # Tổng đi trễ/về sớm (nếu chưa được xử lý)
            if self.show_late_early and 'late_early' in custom_columns:
                worksheet.write(row, col, total_late_early_minutes, total_format)
                col += 1

            # Tổng ngày công (nếu chưa được xử lý)
            if self.show_workdays and 'working_days' in custom_columns:
                worksheet.write(row, col, total_working_days, workday_total_format)
                col += 1