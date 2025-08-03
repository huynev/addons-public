# -*- coding: utf-8 -*-
from datetime import datetime
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
import calendar


class HrLoanBatch(models.Model):
    """Model quản lý đợt ứng lương"""
    _name = 'hr.loan.batch'
    _description = "Loan Batch"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = "date_created desc"

    name = fields.Char(string="Tên đợt", required=True, readonly=True, default="New")
    month = fields.Selection([
        ('1', 'Tháng 1'), ('2', 'Tháng 2'), ('3', 'Tháng 3'), ('4', 'Tháng 4'),
        ('5', 'Tháng 5'), ('6', 'Tháng 6'), ('7', 'Tháng 7'), ('8', 'Tháng 8'),
        ('9', 'Tháng 9'), ('10', 'Tháng 10'), ('11', 'Tháng 11'), ('12', 'Tháng 12')
    ], string="Tháng", required=True, readonly=True,
        default=lambda self: str(fields.Date.today().month))
    year = fields.Integer(string="Năm", required=True, readonly=True,
                          default=lambda self: fields.Date.today().year)

    execution_date = fields.Date(string="Ngày thực thi",
                                 help="Ngày thực thi tạo đợt ứng lương tự động")
    execution_day = fields.Integer(string="Ngày trong tháng",
                                   compute='_compute_execution_day', store=True,
                                   help="Ngày trong tháng được thực thi (1-28)")

    sequence = fields.Integer(string="Số thứ tự trong tháng", required=True, readonly=True)
    date_created = fields.Datetime(string="Ngày tạo", default=fields.Datetime.now, readonly=True)

    state = fields.Selection([
        ('draft', 'Nháp'),
        ('confirmed', 'Đã xác nhận'),
        ('done', 'Hoàn thành'),
        ('cancelled', 'Đã hủy')
    ], string="Trạng thái", default='draft', tracking=True)

    company_id = fields.Many2one('res.company', string='Công ty',
                                 default=lambda self: self.env.user.company_id)

    # Relations
    loan_ids = fields.One2many('hr.loan', 'batch_id', string="Các khoản ứng")
    auto_config_id = fields.Many2one('hr.loan.auto.config', string="Cấu hình tự động",
                                     help="Cấu hình tự động tạo đợt này (nếu có)")

    # Computed fields
    loan_count = fields.Integer(compute='_compute_loan_stats', string="Số khoản ứng", store=True)
    employee_count = fields.Integer(compute='_compute_loan_stats', string="Số nhân viên", store=True)
    total_amount = fields.Float(compute='_compute_loan_stats', string="Tổng tiền ứng", store=True)
    total_paid_amount = fields.Float(compute='_compute_loan_stats', string="Đã trả", store=True)
    total_balance_amount = fields.Float(compute='_compute_loan_stats', string="Còn lại", store=True)

    approved_loan_count = fields.Integer(compute='_compute_loan_stats', string="Đã duyệt", store=True)
    pending_loan_count = fields.Integer(compute='_compute_loan_stats', string="Chờ duyệt", store=True)
    draft_loan_count = fields.Integer(compute='_compute_loan_stats', string="Nháp", store=True)

    @api.depends('loan_ids', 'loan_ids.state', 'loan_ids.loan_amount',
                 'loan_ids.total_paid_amount', 'loan_ids.balance_amount', 'loan_ids.employee_id')
    def _compute_loan_stats(self):
        """Tính toán thống kê các khoản ứng trong đợt"""
        for batch in self:
            loans = batch.loan_ids

            # Basic counts
            batch.loan_count = len(loans)
            batch.employee_count = len(loans.mapped('employee_id'))

            # Financial amounts
            batch.total_amount = sum(loans.mapped('loan_amount'))
            batch.total_paid_amount = sum(loans.mapped('total_paid_amount'))
            batch.total_balance_amount = sum(loans.mapped('balance_amount'))

            # State-based counts
            batch.approved_loan_count = len(loans.filtered(lambda l: l.state == 'approve'))
            batch.pending_loan_count = len(loans.filtered(lambda l: l.state == 'waiting_approval_1'))
            batch.draft_loan_count = len(loans.filtered(lambda l: l.state == 'draft'))
            # batch.refused_loan_count = len(loans.filtered(lambda l: l.state == 'refuse'))
            # batch.cancelled_loan_count = len(loans.filtered(lambda l: l.state == 'cancel'))

    @api.constrains('year')
    def _check_year(self):
        """Validate year values"""
        for batch in self:
            if batch.year < 2020 or batch.year > 2050:
                raise ValidationError(_("Năm phải từ 2020 đến 2050"))
        """Tính toán thống kê các khoản ứng trong đợt"""
        for batch in self:
            loans = batch.loan_ids

            batch.loan_count = len(loans)
            batch.employee_count = len(loans.mapped('employee_id'))
            batch.total_amount = sum(loans.mapped('loan_amount'))
            batch.total_paid_amount = sum(loans.mapped('total_paid_amount'))
            batch.total_balance_amount = sum(loans.mapped('balance_amount'))

            batch.approved_loan_count = len(loans.filtered(lambda l: l.state == 'approve'))
            batch.pending_loan_count = len(loans.filtered(lambda l: l.state == 'waiting_approval_1'))
            batch.draft_loan_count = len(loans.filtered(lambda l: l.state == 'draft'))

    @api.model
    def create(self, vals):
        """Enhanced create method with execution_date consideration"""
        if vals.get('name', 'New') == 'New':
            month_str = vals.get('month', str(fields.Date.today().month))
            year = vals.get('year', fields.Date.today().year)
            company_id = vals.get('company_id', self.env.user.company_id.id)
            execution_date = vals.get('execution_date')

            month_int = int(month_str)

            # Get sequence with execution day consideration
            sequence = self._get_next_sequence_in_month_with_execution_day(
                month_str, year, company_id, execution_date
            )
            vals['sequence'] = sequence

            # Create enhanced batch name with execution day
            month_name = f"{month_int:02d}"
            if execution_date:
                execution_day = execution_date.day
                vals['name'] = f"Đợt {sequence} - {month_name}/{year} (Ngày {execution_day})"
            else:
                vals['name'] = f"Đợt {sequence} - {month_name}/{year}"

        return super(HrLoanBatch, self).create(vals)

    @api.model
    def _get_next_sequence_in_month_with_execution_day(self, month, year, company_id, execution_date=None):
        """Get next sequence considering execution day for auto-generated batches"""
        month_str = str(month) if isinstance(month, int) else month

        domain = [
            ('month', '=', month_str),
            ('year', '=', year),
            ('company_id', '=', company_id)
        ]

        existing_batches = self.search(domain)

        if existing_batches:
            return max(existing_batches.mapped('sequence')) + 1
        return 1

    @api.model
    def create_batch_for_current_month(self, auto_config_id, execution_day, company_id=None):
        """Tạo đợt mới cho tháng hiện tại"""
        today = fields.Date.today()
        company_id = company_id or self.env.user.company_id.id
        return self.create({
            'month': str(today.month),
            'year': today.year,
            'execution_date': today,
            'execution_day': execution_day,
            'auto_config_id': auto_config_id,
            'company_id': company_id
        })

    def action_confirm(self):
        """Xác nhận đợt ứng lương"""
        for batch in self:
            if not batch.loan_ids:
                raise ValidationError(_("Không thể xác nhận đợt rỗng. Vui lòng thêm ít nhất một khoản ứng."))
            batch.state = 'confirmed'

    def action_done(self):
        """Hoàn thành đợt ứng lương"""
        for batch in self:
            if batch.pending_loan_count > 0:
                raise ValidationError(
                    _("Còn %d khoản ứng chưa được duyệt. Vui lòng duyệt tất cả trước khi hoàn thành đợt.") % batch.pending_loan_count)
            batch.state = 'done'

    def action_cancel(self):
        """Hủy đợt ứng lương"""
        for batch in self:
            if batch.approved_loan_count > 0:
                raise ValidationError(_("Không thể hủy đợt có %d khoản ứng đã được duyệt.") % batch.approved_loan_count)

            # Hủy tất cả các khoản ứng trong đợt
            batch.loan_ids.filtered(lambda l: l.state in ['draft', 'waiting_approval_1']).write({'state': 'cancel'})
            batch.state = 'cancelled'

    def action_reset_to_draft(self):
        """Chuyển về trạng thái nháp"""
        for batch in self:
            if batch.state in ['done', 'cancelled']:
                batch.state = 'draft'

    def action_view_loans(self):
        """Xem các khoản ứng trong đợt"""
        self.ensure_one()
        return {
            'name': _('Khoản ứng - %s') % self.name,
            'domain': [('batch_id', '=', self.id)],
            'res_model': 'hr.loan',
            'type': 'ir.actions.act_window',
            'view_mode': 'tree,form',
            'context': {'default_batch_id': self.id}
        }

    def action_batch_approve_loans(self):
        """Duyệt tất cả khoản ứng trong đợt"""
        pending_loans = self.loan_ids.filtered(lambda l: l.state == 'waiting_approval_1')
        if pending_loans:
            return pending_loans.action_batch_approve()
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Thông báo'),
                    'message': _('Không có khoản ứng nào cần duyệt.'),
                    'type': 'warning',
                }
            }

    def action_export_excel(self):
        """Xuất danh sách ứng lương của đợt ra Excel"""
        return self._export_batch_excel()

    def action_export_excel(self):
        """Xuất danh sách ứng lương của đợt ra Excel"""
        return self._export_batch_excel()

    def _export_batch_excel(self):
        """Xuất Excel cho đợt theo format mẫu"""
        import xlsxwriter
        import base64
        from io import BytesIO

        output = BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Danh sach ung luong')

        # Define formats
        company_format = workbook.add_format({
            'bold': True, 'align': 'left', 'valign': 'vcenter',
            'font_size': 12
        })

        title_format = workbook.add_format({
            'bold': True, 'align': 'center', 'valign': 'vcenter',
            'font_size': 14
        })

        header_format = workbook.add_format({
            'bold': True, 'align': 'center', 'valign': 'vcenter',
            'bg_color': '#D7E4BC', 'border': 1, 'text_wrap': True
        })

        subheader_format = workbook.add_format({
            'bold': True, 'align': 'center', 'valign': 'vcenter',
            'bg_color': '#D7E4BC', 'border': 1, 'font_size': 10
        })

        cell_format = workbook.add_format({
            'align': 'center', 'valign': 'vcenter', 'border': 1
        })

        cell_format_name = workbook.add_format({
            'align': 'left', 'valign': 'vcenter', 'border': 1
        })

        currency_format = workbook.add_format({
            'align': 'right', 'valign': 'vcenter', 'border': 1,
            'num_format': '#,##0'
        })

        signature_format = workbook.add_format({
            'bold': True, 'align': 'center', 'valign': 'vcenter'
        })

        date_format = workbook.add_format({
            'align': 'center', 'valign': 'vcenter', 'italic': True
        })

        # Set column widths
        worksheet.set_column('A:A', 6)  # STT
        worksheet.set_column('B:B', 10)  # Mã NV
        worksheet.set_column('C:C', 25)  # Họ & Tên
        worksheet.set_column('D:D', 20)  # Phòng ban
        worksheet.set_column('E:E', 12)  # Số tiền
        worksheet.set_column('F:F', 12)  # Thực nhận
        worksheet.set_column('G:G', 20)  # Ký nhận

        # Row 1: Company name
        company_name = self.company_id.name or "Công Ty TNHH Chế Biến Nông Sản Minh Đức"
        worksheet.write('A1', company_name, company_format)

        # Row 2: Company address
        company_address = self.company_id.street or "Lô I KCN An Nghiệp, Khóm 2, Phường 7, Thành Phố Sóc Trăng, ST"
        worksheet.write('A2', company_address, company_format)

        # Row 3: Empty

        # Row 4: Title (merged A4:G4)
        month_name = dict(self._fields['month'].selection)[self.month]

        # Add execution date to title
        if self.execution_date:
            date_str = self.execution_date.strftime('%d/%m/%Y')
            title = f"DANH SÁCH ỨNG LƯƠNG CB - CNV {month_name.upper()}.{self.year} - NGÀY {date_str}"
        else:
            title = f"DANH SÁCH ỨNG LƯƠNG CB - CNV {month_name.upper()}.{self.year}"

        worksheet.merge_range('A4:G4', title, title_format)

        # Row 5: Empty

        # Row 6-7: Complex headers
        # Main headers (Row 6)
        worksheet.merge_range('A6:A7', 'STT', header_format)
        worksheet.merge_range('B6:B7', 'Mã NV', header_format)
        worksheet.merge_range('C6:C7', 'Họ & Tên', header_format)
        worksheet.merge_range('D6:D7', 'Phòng ban', header_format)

        # Get execution date for loan batch header
        if self.execution_date:
            date_str = self.execution_date.strftime('%d/%m')
        else:
            date_str = f"{fields.Date.today()}"

        worksheet.merge_range('E6:G6', date_str, header_format)

        # Sub headers (Row 7)
        worksheet.write('E7', 'SỐ TIỀN', subheader_format)
        worksheet.write('F7', 'THỰC NHẬN', subheader_format)
        worksheet.write('G7', 'KÍ NHẬN', subheader_format)

        # Data rows starting from row 8
        row = 7  # 0-indexed, so row 8 in Excel
        approved_loans = self.loan_ids.filtered(lambda l: l.state in ['approve', 'waiting_approval_1'])

        for index, loan in enumerate(approved_loans, 1):
            worksheet.write(row, 0, index, cell_format)
            worksheet.write(row, 1, loan.employee_id.employee_code or '', cell_format)
            worksheet.write(row, 2, loan.employee_id.name or '', cell_format_name)
            worksheet.write(row, 3, loan.employee_id.department_id.name or '', cell_format_name)
            worksheet.write(row, 4, loan.loan_amount, currency_format)
            worksheet.write(row, 5, '', cell_format)  # Thực nhận - empty
            worksheet.write(row, 6, '', cell_format)  # Ký nhận - empty
            row += 1

        # Add some empty rows for spacing
        row += 2

        # Total row (optional)
        if approved_loans:
            total_amount = sum(approved_loans.mapped('loan_amount'))
            worksheet.merge_range(f'A{row + 1}:D{row + 1}', 'TỔNG CỘNG', header_format)
            worksheet.write(row, 4, total_amount, currency_format)
            worksheet.write(row, 5, '', cell_format)
            worksheet.write(row, 6, '', cell_format)
            row += 3

        # Date row
        current_date = fields.Date.today()
        date_text = f"Ngày {current_date.day:02d} tháng {current_date.month:02d} năm {current_date.year}"
        worksheet.merge_range(f'F{row + 1}:G{row + 1}', date_text, date_format)
        row += 1

        # Signature section
        worksheet.merge_range(f'A{row + 1}:B{row + 1}', 'Người nhận tiền', signature_format)
        worksheet.merge_range(f'C{row + 1}:D{row + 1}', 'Thủ quỹ', signature_format)
        worksheet.merge_range(f'E{row + 1}:G{row + 1}', 'Giám đốc', signature_format)

        workbook.close()
        output.seek(0)

        # Create attachment
        filename = f"Danh_sach_ung_luong_{self.name.replace(' ', '_')}_{fields.Date.today().strftime('%Y%m%d')}.xlsx"
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'type': 'binary',
            'datas': base64.b64encode(output.read()),
            'store_fname': filename,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'new',
        }