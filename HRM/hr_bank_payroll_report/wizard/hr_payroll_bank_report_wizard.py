from odoo import models, fields, api, _
from odoo.exceptions import UserError
import base64
import io
import logging
from datetime import datetime

_logger = logging.getLogger(__name__)

try:
    import xlsxwriter
except ImportError:
    _logger.warning("Thư viện xlsxwriter không được cài đặt!")


class HrPayrollBankReportWizard(models.TransientModel):
    _name = 'hr.payroll.bank.report.wizard'
    _description = 'Báo cáo chuyển lương qua ngân hàng'

    date_from = fields.Date(string='Từ ngày', required=True)
    date_to = fields.Date(string='Đến ngày', required=True)
    company_id = fields.Many2one('res.company', string='Công ty',
                                 required=True, default=lambda self: self.env.company)
    payslip_run_id = fields.Many2one('hr.payslip.run', string='Đợt lương')
    include_draft = fields.Boolean(string='Bao gồm phiếu lương nháp', default=False)
    salary_rule_code = fields.Char(string='Mã lương thực lãnh', help='Mã lương thực lãnh. Mặc định là NET',
                                   default='NET')

    report_file = fields.Binary(string='Báo cáo', readonly=True)
    report_filename = fields.Char(string='Tên file')
    state = fields.Selection([
        ('draft', 'Nháp'),
        ('generated', 'Đã tạo báo cáo')
    ], default='draft')

    @api.onchange('payslip_run_id')
    def onchange_payslip_run(self):
        if self.payslip_run_id:
            self.date_from = self.payslip_run_id.date_start
            self.date_to = self.payslip_run_id.date_end

    def action_generate_report(self):
        self.ensure_one()

        # Lấy các phiếu lương dựa vào điều kiện
        domain = [
            ('date_from', '>=', self.date_from),
            ('date_to', '<=', self.date_to),
            ('company_id', '=', self.company_id.id),
        ]

        if self.payslip_run_id:
            domain.append(('payslip_run_id', '=', self.payslip_run_id.id))

        if not self.include_draft:
            domain.append(('state', 'in', ['done', 'paid']))

        payslips = self.env['hr.payslip'].search(domain)

        if not payslips:
            raise UserError(_("Không tìm thấy phiếu lương phù hợp với điều kiện!"))

        # Tạo báo cáo Excel
        report_content = self._generate_excel_report(payslips)

        # Lưu file báo cáo
        self.write({
            'report_file': base64.b64encode(report_content),
            'report_filename': f'Bao_cao_chuyen_luong_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx',
            'state': 'generated'
        })

        return {
            'name': _('Báo cáo chuyển lương'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.payroll.bank.report.wizard',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }

    def _generate_excel_report(self, payslips):
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output)

        # Định nghĩa các style
        header_style = workbook.add_format({
            'bold': True,
            'align': 'center',
            'valign': 'vcenter',
            'border': 1,
            'font_size': 11,
            'bg_color': '#D3D3D3'
        })

        title_style = workbook.add_format({
            'bold': True,
            'align': 'center',
            'valign': 'vcenter',
            'font_size': 14,
        })

        date_style = workbook.add_format({
            'num_format': 'dd/mm/yyyy',
            'border': 1,
        })

        number_style = workbook.add_format({
            'num_format': '#,##0',
            'border': 1,
        })

        text_style = workbook.add_format({
            'border': 1,
            'text_wrap': True,
        })

        # Nhóm phiếu lương theo ngân hàng
        bank_payslips = {}
        unknown_bank_payslips = []

        for payslip in payslips:
            # Kiểm tra thông tin ngân hàng
            bank_account = payslip.employee_id.bank_account_id
            if not bank_account:
                unknown_bank_payslips.append(payslip)
                continue

            bank_name = bank_account.bank_id.name or "Ngân hàng không xác định"

            if bank_name not in bank_payslips:
                bank_payslips[bank_name] = []

            bank_payslips[bank_name].append(payslip)

        # Tạo sheet cho từng ngân hàng
        for bank_name, bank_slips in bank_payslips.items():
            self._create_bank_sheet(workbook, bank_name, bank_slips,
                                    header_style, title_style, date_style,
                                    number_style, text_style)

        # Tạo sheet cho nhân viên không có thông tin ngân hàng
        if unknown_bank_payslips:
            self._create_bank_sheet(workbook, "Không có thông tin ngân hàng",
                                    unknown_bank_payslips, header_style, title_style,
                                    date_style, number_style, text_style)

        workbook.close()
        output.seek(0)
        return output.read()

    def _create_bank_sheet(self, workbook, sheet_name, payslips, header_style,
                           title_style, date_style, number_style, text_style):
        # Tạo một sheet mới cho ngân hàng
        safe_sheet_name = sheet_name[:31]  # Excel giới hạn tên sheet tối đa 31 ký tự
        worksheet = workbook.add_worksheet(safe_sheet_name)

        # Thiết lập độ rộng cột
        worksheet.set_column('A:A', 5)  # STT
        worksheet.set_column('B:B', 20)  # Họ tên
        worksheet.set_column('C:C', 20)  # Số tài khoản
        worksheet.set_column('D:D', 15)  # Chi nhánh
        worksheet.set_column('E:E', 15)  # Số tiền
        worksheet.set_column('F:F', 30)  # Nội dung

        # Tiêu đề báo cáo
        worksheet.merge_range('A1:F1', f'DANH SÁCH CHUYỂN LƯƠNG - {sheet_name}', title_style)
        worksheet.merge_range('A2:F2',
                              f'Kỳ lương: {self.date_from.strftime("%d/%m/%Y")} - {self.date_to.strftime("%d/%m/%Y")}',
                              title_style)

        # Header
        headers = ['STT', 'Họ và tên', 'Số tài khoản', 'Chi nhánh', 'Số tiền', 'Nội dung']
        for col, header in enumerate(headers):
            worksheet.write(3, col, header, header_style)

        # Dữ liệu
        row = 4
        total_amount = 0

        for idx, payslip in enumerate(payslips, 1):
            employee = payslip.employee_id
            bank_account = employee.bank_account_id

            # Tính tổng lương (Thực lĩnh)
            net_amount = payslip.get_net_amount(self.salary_rule_code)
            total_amount += net_amount

            # Nội dung chuyển khoản
            content = f"Lương tháng {self.date_from.month}/{self.date_from.year} - {employee.name}"

            worksheet.write(row, 0, idx, text_style)
            worksheet.write(row, 1, employee.name, text_style)

            if bank_account:
                worksheet.write(row, 2, bank_account.acc_number or '', text_style)
                worksheet.write(row, 3, bank_account.bank_id.bic or '', text_style)
            else:
                worksheet.write(row, 2, '', text_style)
                worksheet.write(row, 3, '', text_style)

            worksheet.write(row, 4, net_amount, number_style)
            worksheet.write(row, 5, content, text_style)

            row += 1

        # Tổng cộng
        worksheet.merge_range(f'A{row + 1}:D{row + 1}', 'TỔNG CỘNG', header_style)
        worksheet.write(row, 4, total_amount, number_style)

        # Thông tin phía dưới
        row += 3
        current_date = datetime.now().strftime("%d/%m/%Y")
        worksheet.write(row, 4, f"Ngày {current_date}")
        row += 1
        worksheet.write(row, 0, "Người lập biểu")
        worksheet.write(row, 4, "Kế toán trưởng")

        return worksheet

    def action_reset_wizard(self):
        """Reset wizard to draft state to create a new report"""
        self.ensure_one()

        # Lưu lại các giá trị hiện tại để sử dụng lại
        date_from = self.date_from
        date_to = self.date_to
        company_id = self.company_id.id
        payslip_run_id = self.payslip_run_id.id if self.payslip_run_id else False
        include_draft = self.include_draft

        # Reset về trạng thái nháp
        self.write({
            'state': 'draft',
            'report_file': False,
            'report_filename': False,
        })

        # Cập nhật lại các giá trị đã lưu
        self.write({
            'date_from': date_from,
            'date_to': date_to,
            'company_id': company_id,
            'payslip_run_id': payslip_run_id,
            'include_draft': include_draft,
        })

        return {
            'name': _('Báo cáo chuyển lương'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.payroll.bank.report.wizard',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
            'context': self.env.context,
        }