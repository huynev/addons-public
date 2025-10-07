from datetime import datetime
from odoo import models, fields, api
from random import randint
from odoo.http import request
from odoo.exceptions import UserError
import base64
from io import BytesIO
import xlsxwriter
from PIL import Image


class CustomQuotation(models.Model):
    _name = 'custom.quotation'
    _description = 'Custom Quotation'
    _inherit = ['portal.mixin']

    name = fields.Char('Reference', required=True, copy=False, readonly=True,
                       default=lambda self: ('New'))
    description = fields.Char(string='Mô tả')
    partner_id = fields.Many2one('res.partner', string='Customer')
    pricelist_id = fields.Many2one('product.pricelist', string='Price List',
                                   compute='_compute_pricelist', store=True, readonly=False)
    date = fields.Date(string='Quotation Date', default=fields.Date.today)
    validity_date = fields.Date(string='Expiration Date')
    quotation_line_ids = fields.One2many('custom.quotation.line', 'quotation_id',
                                         string='Quotation Lines')
    excel_file = fields.Binary(string='Excel File', readonly=True)
    excel_filename = fields.Char(string='Excel Filename', readonly=True)
    pdf_file = fields.Binary(string='PDF File', readonly=True)
    pdf_filename = fields.Char(string='PDF Filename', readonly=True)

    access_token = fields.Char('Security Token', copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('custom.quotation') or 'New'
            if not vals.get('access_token'):
                vals['access_token'] = randint(100000000, 999999999)
        return super().create(vals_list)

    @api.onchange('pricelist_id')
    def _onchange_pricelist(self):
        if self.pricelist_id and self.quotation_line_ids:
            try:
                for line in self.quotation_line_ids:
                    if line.product_id:
                        price = self.pricelist_id._get_product_price(
                            product=line.product_id,
                            quantity=1.0,
                            partner=self.partner_id,
                            date=fields.Date.today(),
                            uom_id=line.product_id.uom_id
                        )
                        if price is not None:  # Kiểm tra giá trị price
                            line.price_unit = price
                        else:
                            line.price_unit = line.product_id.list_price
            except Exception as e:
                # Log lỗi nếu cần
                # Giữ nguyên giá cũ nếu có lỗi xảy ra
                pass

    def action_print_quotation(self):
        self.ensure_one()

        # Generate PDF content
        pdf_content = self.env.ref('custom_quotation.action_report_quotation')._render_qweb_pdf(self.id)[0]

        # Save PDF file to record
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        pdf_filename = f'Báo giá - {self.name} - {timestamp}.pdf'
        self.write({
            'pdf_file': base64.b64encode(pdf_content),
            'pdf_filename': pdf_filename
        })

        # Create attachment for PDF
        self.env['ir.attachment'].create({
            'name': pdf_filename,
            'type': 'binary',
            'datas': base64.b64encode(pdf_content),
            'res_model': self._name,
            'res_id': self.id,
        })

        # Return report action
        return self.env.ref('custom_quotation.action_report_quotation').report_action(self)

    def action_preview_quotation(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'target': 'new',
            'url': '/my/quotation/preview/%s?access_token=%s' % (self.id, self.access_token),
        }

    def action_generate_files(self):
        self.ensure_one()

        # Xóa file cũ
        self.excel_file = False
        self.excel_filename = False
        self.pdf_file = False
        self.pdf_filename = False

        # Xóa attachments cũ
        domain = [
            ('res_model', '=', self._name),
            ('res_id', '=', self.id),
            ('name', 'in', ['Báo giá%', '%.pdf', '%.xlsx']),
        ]
        old_attachments = self.env['ir.attachment'].search(domain)
        if old_attachments:
            old_attachments.unlink()

        # Tạo file Excel
        self.action_export_excel()

        # Tạo file PDF
        pdf_content = request.env['ir.actions.report'].sudo()._render_qweb_pdf('custom_quotation.action_report_custom_quotation',
                                                                 [self.id])[0]
        # Lưu file PDF
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        pdf_filename = f'Báo giá - {self.name} - {timestamp}.pdf'
        self.write({
            'pdf_file': base64.b64encode(pdf_content),
            'pdf_filename': pdf_filename
        })

        # Tạo attachment cho PDF
        self.env['ir.attachment'].create({
            'name': pdf_filename,
            'type': 'binary',
            'datas': base64.b64encode(pdf_content),
            'res_model': self._name,
            'res_id': self.id,
        })

        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
            'params': {
                'effect': {
                    'type': 'rainbow_man',
                    'message': 'File báo giá đã được tạo thành công!'
                }
            }
        }

    def action_open_product_list(self):
        self.ensure_one()
        action = self.env.ref('custom_quotation.action_product_selection').read()[0]

        # Lấy danh sách sản phẩm đã có trong báo giá
        existing_products = self.quotation_line_ids.mapped('product_id').ids

        action.update({
            'context': {
                'quotation_id': self.id,
                'search_default_filter_to_sell': True,
            },
            # Thêm điều kiện loại bỏ sản phẩm đã có trong báo giá
            'domain': [
                ('sale_ok', '=', True),
                ('id', 'not in', existing_products)
            ]
        })
        return action

    @api.depends('partner_id')
    def _compute_pricelist(self):
        for quotation in self:
            if quotation.partner_id:
                # Chỉ set pricelist từ khách hàng nếu chưa có giá trị hoặc đổi khách hàng
                if not quotation.pricelist_id or quotation._origin.partner_id != quotation.partner_id:
                    quotation.pricelist_id = quotation.partner_id.property_product_pricelist
            elif not quotation.pricelist_id:
                # Set pricelist mặc định chỉ khi không có giá trị
                quotation.pricelist_id = self.env['product.pricelist'].search([], limit=1)

    def action_export_excel(self):
        output = BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Báo giá')

        # Định dạng
        header_format = workbook.add_format({
            'bold': True,
            'align': 'center',
            'valign': 'vcenter',
            'border': 1,
            'bg_color': '#D3D3D3'
        })

        cell_format = workbook.add_format({
            'align': 'left',
            'valign': 'vcenter',
            'border': 1
        })

        number_format = workbook.add_format({
            'align': 'right',
            'valign': 'vcenter',
            'border': 1,
            'num_format': '#,##0'
        })

        center_format = workbook.add_format({
            'align': 'center',
            'valign': 'vcenter',
            'border': 1
        })

        # Header
        current_row = 0
        worksheet.merge_range(f'A{current_row + 1}:H{current_row + 1}', 'Báo giá: ' + self.name, header_format)
        current_row += 1

        if self.partner_id:
            worksheet.merge_range(f'A{current_row + 1}:H{current_row + 1}', 'Khách hàng: ' + self.partner_id.name,
                                  header_format)
            current_row += 1

        worksheet.merge_range(f'A{current_row + 1}:H{current_row + 1}', 'Ngày: ' + str(self.date), header_format)
        current_row += 1

        # Tiêu đề cột
        headers = ['STT', 'Hình ảnh', 'Sản phẩm', 'ĐVT', 'Quy cách đóng gói', 'Đơn giá', 'Thuế', 'Giá bao gồm thuế']
        for col, header in enumerate(headers):
            worksheet.write(current_row + 1, col, header, header_format)
        current_row += 1

        # Thiết lập kích thước cột
        worksheet.set_column(0, 0, 5)  # Cột STT
        worksheet.set_column(1, 1, 20)  # Cột hình ảnh
        worksheet.set_column(2, 2, 40)  # Cột sản phẩm
        worksheet.set_column(3, 3, 10)  # Cột ĐVT
        worksheet.set_column(4, 4, 30)  # Cột quy cách đóng gói
        worksheet.set_column(5, 6, 15)  # Các cột còn lại
        worksheet.set_column(7, 7, 30)  # Giá bao gồm thuế

        # Nội dung
        row = current_row + 1
        cell_height = 90  # Chiều cao cố định cho mỗi cell

        for index, line in enumerate(self.quotation_line_ids, 1):
            # Set chiều cao hàng
            worksheet.set_row(row, cell_height)

            # STT
            worksheet.write(row, 0, index, center_format)

            # Xử lý hình ảnh
            if line.product_id.image_1920:
                try:
                    image_data = BytesIO(base64.b64decode(line.product_id.image_1920))
                    image = Image.open(image_data)

                    # Tính toán tỷ lệ co giãn để ảnh vừa với cell
                    max_width = 140  # Pixels - điều chỉnh để vừa với cột B
                    max_height = cell_height - 6  # Pixels - để lại margin

                    # Tính tỷ lệ co giãn
                    width_ratio = max_width / image.width
                    height_ratio = max_height / image.height
                    scale = min(width_ratio, height_ratio)  # Chọn tỷ lệ nhỏ hơn để ảnh không bị méo

                    # Tính offset để căn giữa ảnh trong cell
                    x_offset = 5  # Pixels từ mép trái của cell
                    y_offset = (cell_height - (image.height * scale)) / 2  # Căn giữa theo chiều dọc

                    worksheet.insert_image(
                        row, 1,
                        'product_image.png',
                        {
                            'image_data': image_data,
                            'x_scale': scale,
                            'y_scale': scale,
                            'x_offset': x_offset,
                            'y_offset': y_offset,
                            'positioning': 1  # 1 = di chuyển và co giãn với cells
                        }
                    )
                except Exception as e:
                    # Log lỗi nếu cần
                    print(f"Error processing image: {e}")

            # Các thông tin khác
            product_name = str(line.product_id.display_name) or line.name
            worksheet.write(row, 2, product_name, cell_format)
            worksheet.write(row, 3, line.product_id.uom_id.name, cell_format)
            worksheet.write(row, 4, line.packaging_info or '', cell_format)
            worksheet.write(row, 5, line.price_unit, number_format)
            taxes = ' + '.join([str(tax.amount) + '%' for tax in line.tax_ids])
            worksheet.write(row, 6, taxes, cell_format)
            worksheet.write(row, 7, line.price_with_tax, cell_format)

            row += 1

        # Ghi chú
        row += 1
        worksheet.merge_range(f'A{row + 1}:H{row + 1}', 'Ghi chú:', header_format)
        row += 1
        worksheet.merge_range(f'A{row + 1}:H{row + 1}', '- Giá trên chưa bao gồm thuế VAT', cell_format)
        if self.validity_date:
            row += 1
            worksheet.merge_range(f'A{row + 1}:G{row + 1}',
                                  f'- Báo giá có hiệu lực đến: {self.validity_date}', cell_format)

        workbook.close()

        # Lưu file excel vào record
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        xlsx_data = output.getvalue()
        filename = f'Báo giá - {self.name} - {timestamp}.xlsx'

        self.write({
            'excel_file': base64.b64encode(xlsx_data),
            'excel_filename': filename
        })

        # Xóa các attachments cũ
        domain = [
            ('res_model', '=', self._name),
            ('res_id', '=', self.id),
            ('name', 'like', 'Báo giá%'),  # Chỉ xóa các file có tên bắt đầu bằng "Báo giá"
        ]
        old_attachments = self.env['ir.attachment'].search(domain)
        if old_attachments:
            old_attachments.unlink()

        # Tạo attachment mới
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'type': 'binary',
            'datas': base64.b64encode(xlsx_data),
            'res_model': self._name,
            'res_id': self.id,
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }

