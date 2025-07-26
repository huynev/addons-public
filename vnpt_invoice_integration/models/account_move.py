# account_move.py
# -*- coding: utf-8 -*-

import logging
import json
from datetime import datetime
import xml.etree.ElementTree as ET

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = 'account.move'

    # VNPT E-invoice fields
    vnpt_invoice_id = fields.Char('VNPT Invoice ID', readonly=True, copy=False,
                                  help='Invoice ID returned from VNPT system')
    vnpt_invoice_number = fields.Char('VNPT Invoice Number', readonly=True, copy=False,
                                      help='Official invoice number from VNPT')
    vnpt_invoice_date = fields.Datetime('VNPT Invoice Date', readonly=True, copy=False,
                                        help='Date when invoice was processed by VNPT')
    vnpt_lookup_code = fields.Char('VNPT Lookup Code', readonly=True, copy=False,
                                   help='Code for invoice lookup on VNPT portal')
    vnpt_invoice_url = fields.Char('VNPT Invoice URL', readonly=True, copy=False,
                                   help='URL to view invoice on VNPT portal')

    vnpt_status = fields.Selection([
        ('draft', 'Draft'),
        ('pending', 'Pending'),
        ('published', 'Published'),
        ('cancelled', 'Cancelled'),
        ('error', 'Error'),
    ], string='VNPT Status', default='draft', copy=False,
        help='Status of invoice in VNPT system')

    vnpt_error_message = fields.Text('VNPT Error Message', readonly=True, copy=False)
    vnpt_config_id = fields.Many2one('vnpt.invoice.config', string='VNPT Configuration',
                                     copy=False, help='VNPT configuration used for this invoice')

    # Invoice template info
    vnpt_template = fields.Char('Invoice Template', copy=False)
    vnpt_serial = fields.Char('Invoice Serial', copy=False)
    vnpt_type = fields.Selection([
        ('1', 'VAT Invoice'),
        ('2', 'Sales Invoice'),
        ('3', 'Other'),
        ('4', 'Reserve Invoice'),
        ('5', 'Asset Sales Invoice'),
    ], string='VNPT Invoice Type', copy=False)

    def action_publish_to_vnpt(self):
        """Enhanced publish method with validation and better error handling"""
        for invoice in self:
            if invoice.state != 'posted':
                raise UserError(_('Only posted invoices can be published to VNPT.'))

            if invoice.move_type not in ['out_invoice', 'out_refund']:
                raise UserError(_('Only customer invoices can be published to VNPT.'))

            if invoice.vnpt_status == 'published':
                raise UserError(_('Invoice is already published to VNPT.'))

            try:
                # Get and validate VNPT configuration
                vnpt_config = invoice._get_vnpt_config()
                if not vnpt_config:
                    raise UserError(_('No VNPT configuration found for this company.'))

                # Validate all prerequisites
                invoice._validate_vnpt_prerequisites(vnpt_config)

                # Set status to pending
                invoice.vnpt_status = 'pending'

                # Publish to VNPT
                invoice._publish_to_vnpt()

            except Exception as e:
                _logger.error(f"Failed to publish invoice {invoice.name} to VNPT: {str(e)}")
                invoice.vnpt_status = 'error'
                invoice.vnpt_error_message = str(e)
                raise

    def action_test_vnpt_connection(self):
        """Test VNPT connection and configuration - FIXED VERSION"""
        vnpt_config = self._get_vnpt_config()
        if not vnpt_config:
            raise UserError(_('No VNPT configuration found'))

        try:
            client = vnpt_config._get_soap_client()

            _logger.info(f"Testing VNPT connection:")
            _logger.info(f"  WSDL URL: {vnpt_config.wsdl_url}")
            _logger.info(f"  VNPT Account: {vnpt_config.vnpt_account}")
            _logger.info(f"  VNPT Username: {vnpt_config.vnpt_username}")
            _logger.info(f"  Template: {vnpt_config.invoice_template}")
            _logger.info(f"  Serial: {vnpt_config.invoice_serial}")

            # Test simple operation first
            available_ops = self._get_available_operations(client)
            _logger.info(f"Available operations: {available_ops}")

            # Test with simple methods
            test_results = []

            if hasattr(client.service, 'getDateTimeServer'):
                try:
                    server_time = client.service.getDateTimeServer()
                    test_results.append(f"✓ getDateTimeServer: {server_time}")
                except Exception as e:
                    test_results.append(f"✗ getDateTimeServer failed: {str(e)}")

            if hasattr(client.service, 'getStatusInv'):
                try:
                    status_params = {
                        'Account': vnpt_config.vnpt_account,
                        'ACpass': vnpt_config.vnpt_password,
                        'username': vnpt_config.vnpt_username,
                        'password': vnpt_config.vnpt_user_password,
                        'xmlFkeyInv': '<Inv><Fkey>test_key</Fkey></Inv>',
                        'pattern': vnpt_config.invoice_template,
                        'serial': vnpt_config.invoice_serial
                    }
                    status_response = client.service.getStatusInv(**status_params)
                    test_results.append(f"✓ Authentication test passed: {status_response}")
                except Exception as e:
                    test_results.append(f"✗ Authentication test failed: {str(e)}")

            if hasattr(client.service, 'getCurrentNo'):
                try:
                    current_no_params = {
                        'account': vnpt_config.vnpt_username,
                        'pass': vnpt_config.vnpt_user_password,
                        'pattern': vnpt_config.invoice_template,
                        'serial': vnpt_config.invoice_serial
                    }
                    current_no = client.service.getCurrentNo(**current_no_params)
                    test_results.append(f"✓ getCurrentNo: {current_no}")
                except Exception as e:
                    error_str = str(e)
                    if 'NullReference' in error_str:
                        test_results.append(f"⚠ getCurrentNo: Pattern/Serial may not exist (NullReference)")
                    else:
                        test_results.append(f"✗ getCurrentNo failed: {error_str}")

            # Test ImportAndPublishInv availability
            if 'ImportAndPublishInv' in available_ops:
                test_results.append("✓ ImportAndPublishInv operation available")
            else:
                test_results.append("✗ ImportAndPublishInv operation NOT available")

            message = f'''VNPT Connection Test Results:

Configuration:
• WSDL URL: {vnpt_config.wsdl_url}
• VNPT Account: {vnpt_config.vnpt_account}
• VNPT Username: {vnpt_config.vnpt_username}
• Template: {vnpt_config.invoice_template}
• Serial: {vnpt_config.invoice_serial}

Available Operations: {", ".join(available_ops[:10])}{"..." if len(available_ops) > 10 else ""}

Test Results:
{chr(10).join(test_results)}

Recommendations:
• If authentication fails, verify all 4 credentials with VNPT
• If getCurrentNo shows NullReference, contact VNPT for correct Pattern/Serial
• If ImportAndPublishInv not available, contact VNPT support
• Check server logs for detailed error information'''

            self.message_post(
                body=message,
                subject='VNPT Connection Test Results'
            )

        except Exception as e:
            error_msg = f'''VNPT Connection Test FAILED:

Error: {str(e)}

Troubleshooting:
1. Check WSDL URL is accessible
2. Verify network connectivity to VNPT servers
3. Confirm VNPT service is not under maintenance
4. Validate VNPT configuration parameters

Contact VNPT support if issue persists.'''

            _logger.error(f"VNPT connection test failed: {str(e)}")
            self.message_post(
                body=error_msg,
                subject='VNPT Connection Test FAILED'
            )
            raise UserError(error_msg)

    def _validate_vnpt_prerequisites(self, vnpt_config):
        """Validate all prerequisites before sending to VNPT - ENHANCED"""
        errors = []

        # FIXED: Check VNPT configuration theo tài liệu
        if not vnpt_config.vnpt_account:
            errors.append('VNPT Account (Account) is not configured')
        if not vnpt_config.vnpt_password:
            errors.append('VNPT Password (ACpass) is not configured')
        if not vnpt_config.vnpt_username:
            errors.append('VNPT Username (username with ServiceRole) is not configured')
        if not vnpt_config.vnpt_user_password:
            errors.append('VNPT User Password (password for ServiceRole) is not configured')
        if not vnpt_config.invoice_template:
            errors.append('Invoice template (pattern) is not configured')
        if not vnpt_config.invoice_serial:
            errors.append('Invoice serial is not configured')

        # Check company information - required fields theo XML format
        if not self.company_id.vat:
            errors.append('Company tax code (MST) is required')
        if not self.company_id.name:
            errors.append('Company name (Ten) is required')
        if not self.company_id.street:
            errors.append('Company address (DChi) is required')

        # Check invoice data - required fields theo XML format
        if not self.partner_id:
            errors.append('Customer (NMua) is required')
        if not self.partner_id.name:
            errors.append('Customer name (Ten) is required')
        if not self.invoice_line_ids:
            errors.append('Invoice must have at least one line (HHDVu)')

        # Check invoice lines - required fields theo XML format
        for line in self.invoice_line_ids.filtered(lambda l: not l.display_type):
            if not line.name:
                errors.append(f'Product name (THHDVu) is required for line {line.sequence}')
            if line.quantity <= 0:
                errors.append(f'Quantity (SLuong) must be positive for line {line.sequence}')
            if line.price_unit < 0:
                errors.append(f'Unit price (DGia) cannot be negative for line {line.sequence}')

        # FIXED: Validate currency - must be VND theo tài liệu
        if self.currency_id.name != 'VND':
            errors.append('Invoice currency must be VND for VNPT e-invoice')

        # FIXED: Validate invoice date
        if not self.invoice_date:
            errors.append('Invoice date (NBKe) is required')

        # FIXED: Test VNPT connection
        try:
            client = vnpt_config._get_soap_client()
            available_ops = self._get_available_operations(client)

            if not available_ops:
                errors.append('Cannot connect to VNPT service - no operations available')
            elif 'ImportAndPublishInv' not in available_ops:
                errors.append('VNPT service does not support ImportAndPublishInv operation')

        except Exception as e:
            errors.append(f'Cannot establish VNPT connection: {str(e)}')

        if errors:
            raise UserError(
                _('Cannot send to VNPT due to validation errors:\n') +
                '\n'.join(f'• {error}' for error in errors)
            )

    def _publish_to_vnpt(self):
        """Internal method to publish invoice to VNPT"""
        self.ensure_one()

        # Get VNPT configuration
        vnpt_config = self._get_vnpt_config()
        if not vnpt_config:
            raise UserError(_('No VNPT configuration found for this company.'))

        # Prepare invoice data
        invoice_data = self._prepare_vnpt_invoice_data(vnpt_config)

        # Send to VNPT
        try:
            self.vnpt_status = 'pending'
            response = self._send_to_vnpt(vnpt_config, invoice_data)
            self._process_vnpt_response(response, vnpt_config)

        except Exception as e:
            self.vnpt_status = 'error'
            self.vnpt_error_message = str(e)
            raise

    def _get_vnpt_config(self):
        """Get VNPT configuration for this invoice"""
        if self.vnpt_config_id:
            return self.vnpt_config_id

        return self.env['vnpt.invoice.config'].get_default_config(self.company_id.id)

    def _prepare_vnpt_invoice_data(self, vnpt_config):
        """Prepare invoice data for VNPT submission - FIXED theo tài liệu"""
        self.ensure_one()

        # Store config info in invoice
        self.vnpt_config_id = vnpt_config.id
        self.vnpt_template = vnpt_config.invoice_template
        self.vnpt_serial = vnpt_config.invoice_serial
        self.vnpt_type = vnpt_config.invoice_type

        invoice_data = {
            'Account': vnpt_config.vnpt_account,
            'ACpass': vnpt_config.vnpt_password,
            'username': vnpt_config.vnpt_username,
            'password': vnpt_config.vnpt_user_password,
            'pattern': vnpt_config.invoice_template,
            'serial': vnpt_config.invoice_serial,
            'convert': 0,  # Không convert encoding

            # Invoice data for XML generation
            'invoice_lines': self._prepare_invoice_lines(),
            'company': self.company_id,
            'partner': self.partner_id,
            'invoice_date': self.invoice_date,
            'narration': self.narration or '',
            'payment_method': self._get_payment_method(),
            'totals': self._calculate_totals(),
        }

        return invoice_data

    def _prepare_invoice_lines(self):
        """Prepare invoice lines data"""
        lines = []
        for idx, line in enumerate(self.invoice_line_ids.filtered(lambda l: l.display_type), 1):
            # Calculate VAT properly
            vat_rate = 0
            vat_amount = 0
            if line.tax_ids:
                vat_rate = line.tax_ids[0].amount
                vat_amount = line.price_subtotal * vat_rate / 100

            line_data = {
                'stt': idx,
                'tchat': '1',  # 1-Hàng hóa, dịch vụ
                'mhhdvu': line.product_id.default_code or '',
                'thhdvu': line.product_id.name or line.name,
                'dvtinh': line.product_uom_id.name or 'cái',
                'sluong': line.quantity,
                'dgia': line.price_unit,
                'thtien': line.price_subtotal,  # Thành tiền chưa thuế
                'tsuat': vat_rate,
                'tthue': vat_amount,
                'tsthue': line.price_total,  # Tiền sau thuế
            }
            lines.append(line_data)
        return lines

    def _calculate_totals(self):
        """Calculate invoice totals"""
        lines = self.invoice_line_ids.filtered(lambda l: l.display_type)

        total_before_tax = sum(line.price_subtotal for line in lines)
        total_tax = sum(line.price_total - line.price_subtotal for line in lines)
        total_payment = total_before_tax + total_tax

        return {
            'tgtcthue': total_before_tax,  # Tổng tiền chưa thuế
            'tgtthue': total_tax,  # Tổng tiền thuế
            'tgtttbso': total_payment,  # Tổng tiền thanh toán bằng số
            'tgtttbchu': self._number_to_words(total_payment),  # Tổng tiền bằng chữ
        }

    def _get_partner_address(self, partner):
        """Get formatted partner address"""
        address_parts = []
        if partner.street:
            address_parts.append(partner.street)
        if partner.street2:
            address_parts.append(partner.street2)
        if partner.city:
            address_parts.append(partner.city)
        if partner.state_id:
            address_parts.append(partner.state_id.name)
        if partner.country_id:
            address_parts.append(partner.country_id.name)

        return ', '.join(address_parts) if address_parts else ''

    def _get_payment_method(self):
        """Get payment method for invoice"""
        if self.invoice_payment_term_id:
            if 'cash' in self.invoice_payment_term_id.name.lower():
                return 'Tiền mặt'
            elif 'bank' in self.invoice_payment_term_id.name.lower():
                return 'Chuyển khoản'
        return 'Tiền mặt'  # Default

    def _send_to_vnpt(self, vnpt_config, invoice_data):
        """FIXED: Send to VNPT với đúng format API theo tài liệu"""
        client = vnpt_config._get_soap_client()

        # Create XML data theo format Invoices
        xml_data = self._create_vnpt_xml_invoices(invoice_data)

        # Log the XML being sent for debugging
        _logger.info(f"VNPT XML Data for invoice {self.name}:\n{xml_data}")

        try:
            # FIXED: Call ImportAndPublishInv với đúng tham số theo tài liệu
            _logger.info(f"Calling ImportAndPublishInv for invoice {self.name}...")

            response = client.service.ImportAndPublishInv(
                Account=invoice_data['Account'],
                ACpass=invoice_data['ACpass'],
                xmlInvData=xml_data,  # XML data
                username=invoice_data['username'],
                password=invoice_data['password'],
                pattern=invoice_data['pattern'],
                serial=invoice_data['serial'],
                convert=invoice_data['convert']
            )

            # Enhanced response logging
            _logger.info(f"VNPT Response: {response}")

            # FIXED: Parse response theo format trong tài liệu
            self._parse_vnpt_response_format(response)

            return response

        except Exception as e:
            _logger.error(f"VNPT API call failed for invoice {self.name}: {str(e)}")
            raise UserError(f'VNPT service call failed: {str(e)}')

    def _parse_vnpt_response_format(self, response):
        """FIXED: Parse VNPT response theo format trong tài liệu"""
        response_str = str(response).strip()

        # Handle error responses theo tài liệu
        if response_str.startswith('ERR:'):
            error_code = response_str.split(':')[1] if ':' in response_str else '999'
            error_details = self._get_vnpt_error_details(error_code)

            self.vnpt_status = 'error'
            self.vnpt_error_message = f"VNPT Error {error_code}: {error_details['message']}"

            raise UserError(
                f"VNPT Error {error_code}: {error_details['message']}\n\n"
                f"Suggestion: {error_details['suggestion']}"
            )

        # Handle success responses theo format: OK:pattern;serial1-key1_num1,key2_num12
        elif response_str.startswith('OK:'):
            # Parse success response
            # Format: OK:01GTKT3/001;AA/12E-key1_1,key2_2,key3_3
            try:
                success_data = response_str[3:]  # Remove 'OK:'

                if ';' in success_data:
                    pattern_serial, invoice_data = success_data.split(';', 1)

                    if '-' in invoice_data:
                        serial_info, numbers_info = invoice_data.split('-', 1)

                        # Extract invoice numbers
                        if ',' in numbers_info:
                            key_numbers = numbers_info.split(',')
                            if key_numbers:
                                first_key_num = key_numbers[0]
                                if '_' in first_key_num:
                                    key, number = first_key_num.split('_', 1)
                                    self.vnpt_invoice_number = number
                                    self.vnpt_lookup_code = key

                self.vnpt_status = 'published'
                self.vnpt_invoice_date = fields.Datetime.now()
                self.vnpt_error_message = False

                self.message_post(
                    body=_('Invoice successfully published to VNPT. Response: %s') % response_str,
                    subject=_('VNPT Invoice Published')
                )

            except Exception as e:
                _logger.warning(f"Could not fully parse success response: {response_str}")
                # Still mark as published since response starts with OK:
                self.vnpt_status = 'published'
                self.vnpt_invoice_date = fields.Datetime.now()
                self.vnpt_error_message = False

        else:
            # Unknown response format
            _logger.warning(f"Unknown VNPT response format: {response_str}")
            self.vnpt_status = 'error'
            self.vnpt_error_message = f'Unknown VNPT response: {response_str}'
            raise UserError(f'Unknown VNPT response format: {response_str}')

    def _get_vnpt_error_details(self, error_code):
        """Get detailed information about VNPT error codes theo tài liệu"""
        error_map = {
            '1': {
                'message': 'Tài khoản đăng nhập sai hoặc không có quyền thêm khách hàng',
                'suggestion': '''Kiểm tra lại:
• Employee Account và Password (Account/ACpass)
• Service Username và Password (username/password với ServiceRole)
• Liên hệ VNPT để xác nhận tài khoản và quyền truy cập'''
            },
            '3': {
                'message': 'Dữ liệu xml đầu vào không đúng quy định',
                'suggestion': '''Kiểm tra lại:
• Cấu trúc XML theo đúng format TT78
• Các trường bắt buộc (*) đã đầy đủ
• Encoding UTF-8
• Sử dụng "Debug VNPT XML" để kiểm tra XML'''
            },
            '5': {
                'message': 'Không phát hành được hóa đơn',
                'suggestion': 'Lỗi không xác định, kiểm tra exception trả về. Liên hệ VNPT support.'
            },
            '6': {
                'message': 'Dải hóa đơn không đủ số hóa đơn cho lô phát hành',
                'suggestion': 'Hết số hóa đơn trong dải. Liên hệ VNPT để cấp thêm số hóa đơn.'
            },
            '7': {
                'message': 'Thông tin về Username/pass không hợp lệ',
                'suggestion': 'Kiểm tra lại Service Username và Password (tài khoản có quyền ServiceRole)'
            },
            '10': {
                'message': 'Lô có số hóa đơn vượt quá số lượng cho phép',
                'suggestion': 'Vượt quá giới hạn số hóa đơn cho phép. Liên hệ VNPT để tăng quota.'
            },
            '13': {
                'message': 'Lỗi trùng fkey',
                'suggestion': 'Fkey đã tồn tại. Kiểm tra invoice đã được phát hành trước đó chưa.'
            },
            '20': {
                'message': 'Pattern và Serial không phù hợp, hoặc không tồn tại',
                'suggestion': '''Kiểm tra lại:
• Mẫu số hóa đơn (pattern) 
• Ký hiệu hóa đơn (serial)
• Liên hệ VNPT để xác nhận pattern/serial đã đăng ký'''
            },
            '21': {
                'message': 'Lỗi trùng số hóa đơn',
                'suggestion': 'Số hóa đơn đã được sử dụng. Hệ thống sẽ tự động tạo số mới.'
            },
            '29': {
                'message': 'Lỗi chứng thư hết hạn',
                'suggestion': 'Chứng thư số đã hết hạn. Liên hệ VNPT để gia hạn chứng thư.'
            },
            '30': {
                'message': 'Danh sách hóa đơn tồn tại ngày hóa đơn nhỏ hơn ngày hóa đơn đã phát hành',
                'suggestion': 'Ngày hóa đơn không được nhỏ hơn ngày hóa đơn gần nhất đã phát hành.'
            }
        }

        return error_map.get(error_code, {
            'message': f'Mã lỗi không xác định: {error_code}',
            'suggestion': f'Liên hệ VNPT support với mã lỗi {error_code}'
        })

    def _get_available_operations(self, client):
        """Get list of available operations from VNPT service"""
        try:
            operations = []
            service_operations = [
                'ImportAndPublishInv', 'ImportInv', 'ImportInvByPattern',
                'publishInv', 'getStatusInv', 'getCurrentNo',
                'getDateTimeServer', 'cancelInv'
            ]

            for op in service_operations:
                if hasattr(client.service, op):
                    operations.append(op)

            return operations

        except Exception as e:
            _logger.warning(f"Could not get available operations: {str(e)}")
            return []

    def _create_vnpt_xml_invoices(self, invoice_data):
        """SIMPLIFIED: Create XML theo format Invoices đơn giản"""
        import xml.etree.ElementTree as ET
        from datetime import datetime

        # Create root element Invoices
        root = ET.Element('Invoices')

        # Create Inv element
        inv = ET.SubElement(root, 'Inv')

        # key element - unique invoice key (REQUIRED *)
        key = ET.SubElement(inv, 'key')
        key.text = f"ODOO_{self.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Invoice element - chứa thông tin chính của hóa đơn
        invoice_elem = ET.SubElement(inv, 'Invoice')

        # Customer Information
        # CusCode - Mã khách hàng
        cuscode = ET.SubElement(invoice_elem, 'CusCode')
        cuscode.text = invoice_data['partner'].ref or str(invoice_data['partner'].id)

        # CusName - Tên khách hàng (REQUIRED *)
        cusname = ET.SubElement(invoice_elem, 'CusName')
        cusname.text = invoice_data['partner'].name or 'Khách lẻ'

        # CusAddress - Địa chỉ khách hàng (REQUIRED *)
        cusaddress = ET.SubElement(invoice_elem, 'CusAddress')
        cusaddress.text = self._get_partner_address(invoice_data['partner']) or 'Không cung cấp'

        # PaymentMethod - Phương thức thanh toán
        paymentmethod = ET.SubElement(invoice_elem, 'PaymentMethod')
        paymentmethod.text = invoice_data['payment_method']

        # KindOfService - Tháng hóa đơn
        kindofservice = ET.SubElement(invoice_elem, 'KindOfService')
        kindofservice.text = invoice_data['invoice_date'].strftime('%m/%Y') if invoice_data['invoice_date'] else ''

        # Products section
        products = ET.SubElement(invoice_elem, 'Products')

        # Add each invoice line as Product
        for line_data in invoice_data['invoice_lines']:
            product = ET.SubElement(products, 'Product')

            # ProdName - Tên sản phẩm (REQUIRED *)
            prodname = ET.SubElement(product, 'ProdName')
            prodname.text = line_data['thhdvu']

            # ProdUnit - Đơn vị tính
            produnit = ET.SubElement(product, 'ProdUnit')
            produnit.text = line_data['dvtinh'] or 'cái'

            # ProdQuantity - Số lượng
            prodquantity = ET.SubElement(product, 'ProdQuantity')
            prodquantity.text = str(line_data['sluong'])

            # ProdPrice - Đơn giá
            prodprice = ET.SubElement(product, 'ProdPrice')
            prodprice.text = str(line_data['dgia'])

            # Amount - Tổng tiền sau thuế
            amount_prod = ET.SubElement(product, 'Amount')
            amount_prod.text = str(line_data['tsthue'])

            # Total - Tổng tiền trước thuế (REQUIRED *)
            total_prod = ET.SubElement(product, 'Total')
            total_prod.text = str(line_data['thtien'])

            # VATRate - Thuế GTGT (REQUIRED *)
            vatrate_prod = ET.SubElement(product, 'VATRate')
            vatrate_prod.text = str(line_data['tsuat'])

            # VATAmount - Tổng tiền thuế (REQUIRED *)
            vatamount_prod = ET.SubElement(product, 'VATAmount')
            vatamount_prod.text = str(line_data['tthue'])

            # IsSum - Tính chất (REQUIRED *)
            # (0-Hàng hóa, dịch vụ; 1-Khuyến mại; 2-Chiết khấu thương mại; 4-Ghi chú/diễn giải; 5-hàng hóa đặc trưng)
            issum = ET.SubElement(product, 'IsSum')
            issum.text = '0'  # Default: Hàng hóa, dịch vụ

        # Invoice totals
        totals = invoice_data['totals']

        # Total - Tổng tiền trước thuế (REQUIRED *)
        total = ET.SubElement(invoice_elem, 'Total')
        total.text = str(int(totals['tgtcthue']))

        # DiscountAmount - Tiền giảm trừ
        discountamount_inv = ET.SubElement(invoice_elem, 'DiscountAmount')
        discountamount_inv.text = '0'

        # VATRate - Thuế GTGT (REQUIRED *)
        vatrate = ET.SubElement(invoice_elem, 'VATRate')
        # Calculate weighted average VAT rate
        if totals['tgtcthue'] > 0:
            avg_vat_rate = (totals['tgtthue'] / totals['tgtcthue']) * 100
            vatrate.text = str(int(avg_vat_rate))
        else:
            vatrate.text = '0'

        # VATAmount - Tiền thuế GTGT (REQUIRED *)
        vatamount = ET.SubElement(invoice_elem, 'VATAmount')
        vatamount.text = str(int(totals['tgtthue']))

        # Amount - Tổng tiền (REQUIRED *)
        amount = ET.SubElement(invoice_elem, 'Amount')
        amount.text = str(int(totals['tgtttbso']))

        # AmountInWords - Số tiền viết bằng chữ (REQUIRED *)
        amountinwords = ET.SubElement(invoice_elem, 'AmountInWords')
        amountinwords.text = totals['tgtttbchu']

        # CurrencyUnit - Đơn vị tiền tệ
        currencyunit = ET.SubElement(invoice_elem, 'CurrencyUnit')
        currencyunit.text = 'VND'

        # Convert to string with proper encoding
        xml_str = ET.tostring(root, encoding='utf-8', method='xml')

        # Add XML declaration and format nicely
        xml_declaration = '<?xml version="1.0" encoding="utf-8"?>\n'
        formatted_xml = xml_declaration + xml_str.decode('utf-8')

        return formatted_xml

    def _number_to_words(self, amount):
        """Convert number to Vietnamese words - Enhanced version"""
        try:
            amount_int = int(amount)
            if amount_int == 0:
                return "Không đồng"

            # Từ điển số cơ bản
            ones = ['', 'một', 'hai', 'ba', 'bốn', 'năm', 'sáu', 'bảy', 'tám', 'chín']

            def read_three_digits(n, is_first_group=False):
                """Đọc 3 chữ số theo quy tắc tiếng Việt"""
                if n == 0:
                    return ''

                result = ''
                hundreds = n // 100
                remainder = n % 100
                tens = remainder // 10
                units = remainder % 10

                # Hàng trăm
                if hundreds > 0:
                    result += ones[hundreds] + ' trăm'
                    if remainder > 0:
                        result += ' '

                # Xử lý hàng chục và đơn vị
                if remainder == 0:
                    pass  # Không có gì
                elif remainder < 10:
                    # Số từ 1-9
                    if hundreds > 0:
                        result += 'lẻ ' + ones[remainder]
                    else:
                        result += ones[remainder]
                elif remainder == 10:
                    result += 'mười'
                elif remainder < 20:
                    # Số từ 11-19
                    if remainder == 15:
                        result += 'mười lăm'
                    else:
                        result += 'mười ' + ones[units]
                elif tens == 1:  # 10
                    result += 'mười'
                else:
                    # Số từ 20-99
                    result += ones[tens] + ' mười'
                    if units > 0:
                        if units == 5 and tens > 1:
                            result += ' lăm'  # 25, 35, 45... -> hai mười lăm, ba mười lăm...
                        elif units == 1 and tens > 1:
                            result += ' một'  # 21, 31, 41... -> hai mười một, ba mười một...
                        else:
                            result += ' ' + ones[units]

                return result.strip()

            def read_full_number(n):
                """Đọc số nguyên đầy đủ"""
                if n == 0:
                    return 'không'

                # Chia số thành các nhóm 3 chữ số từ phải sang trái
                groups = []
                temp = n
                while temp > 0:
                    groups.append(temp % 1000)
                    temp //= 1000

                # Tên các đơn vị
                units_names = ['', 'nghìn', 'triệu', 'tỷ']

                result_parts = []

                # Đọc từ nhóm cao nhất xuống thấp nhất
                for i in range(len(groups) - 1, -1, -1):
                    group_value = groups[i]
                    if group_value > 0:
                        is_first_group = (i == len(groups) - 1)
                        group_text = read_three_digits(group_value, is_first_group)

                        if i > 0:  # Thêm đơn vị (nghìn, triệu, tỷ)
                            if i < len(units_names):
                                group_text += ' ' + units_names[i]

                        result_parts.append(group_text)
                    elif i > 0 and any(groups[j] > 0 for j in range(i)):
                        # Xử lý trường hợp có số 0 ở giữa (ví dụ: 1.000.005)
                        continue

                return ' '.join(result_parts)

            # Chuyển đổi số thành chữ
            words = read_full_number(amount_int)

            # Chuẩn hóa kết quả
            if words:
                words = words.strip()
                # Làm sạch khoảng trắng thừa
                words = ' '.join(words.split())
                # Viết hoa chữ cái đầu
                words = words[0].upper() + words[1:] if len(words) > 1 else words.upper()
                words += ' đồng'

            return words

        except Exception as e:
            # Fallback đơn giản nếu có lỗi
            try:
                amount_int = int(amount)
                if amount_int < 1000:
                    return f"{amount_int} đồng"
                elif amount_int < 1000000:
                    return f"{amount_int // 1000} nghìn {amount_int % 1000 if amount_int % 1000 > 0 else ''} đồng".strip()
                else:
                    return f"{amount_int:,} đồng".replace(',', '.')
            except:
                return "Số tiền không hợp lệ"

    def _process_vnpt_response(self, response, vnpt_config):
        """Process response from VNPT - đã được xử lý trong _parse_vnpt_response_format"""
        pass  # Response đã được xử lý trong _send_to_vnpt

    def action_cancel_vnpt_invoice(self):
        """Cancel invoice in VNPT system"""
        for invoice in self:
            if invoice.vnpt_status != 'published':
                raise UserError(_('Only published invoices can be cancelled in VNPT.'))

            vnpt_config = invoice._get_vnpt_config()
            if not vnpt_config:
                raise UserError(_('No VNPT configuration found'))

            try:
                client = vnpt_config._get_soap_client()
                available_ops = self._get_available_operations(client)

                if 'cancelInv' in available_ops and invoice.vnpt_invoice_id:
                    cancel_params = {
                        'Account': vnpt_config.vnpt_account,
                        'ACpass': vnpt_config.vnpt_password,
                        'invIDs': [int(invoice.vnpt_invoice_id)],
                        'reason': 'Cancelled by user request'
                    }

                    cancel_response = client.service.cancelInv(**cancel_params)

                    if str(cancel_response).strip() == '0' or 'success' in str(cancel_response).lower():
                        invoice.vnpt_status = 'cancelled'
                        invoice.message_post(
                            body=_('Invoice successfully cancelled in VNPT system'),
                            subject=_('VNPT Invoice Cancelled')
                        )
                    else:
                        raise UserError(f'VNPT cancellation failed: {cancel_response}')

                else:
                    invoice.vnpt_status = 'cancelled'
                    invoice.message_post(
                        body=_('Invoice marked as cancelled (VNPT cancel operation not available)'),
                        subject=_('VNPT Invoice Cancelled')
                    )

            except Exception as e:
                _logger.error(f"Failed to cancel VNPT invoice {invoice.name}: {str(e)}")
                raise UserError(f'Failed to cancel VNPT invoice: {str(e)}')

    def action_debug_vnpt_xml(self):
        """Debug XML that will be sent to VNPT"""
        vnpt_config = self._get_vnpt_config()
        if not vnpt_config:
            raise UserError(_('No VNPT configuration found'))

        try:
            # Validate prerequisites first
            self._validate_vnpt_prerequisites(vnpt_config)

            # Prepare invoice data
            invoice_data = self._prepare_vnpt_invoice_data(vnpt_config)

            # Generate XML
            xml_data = self._create_vnpt_xml_invoices(invoice_data)

            # Log for debugging
            _logger.info(f"Generated XML for invoice {self.name}:\n{xml_data}")

            # Create attachment with XML for easy viewing
            attachment = self.env['ir.attachment'].create({
                'name': f'VNPT_XML_Debug_{self.name}.xml',
                'type': 'binary',
                'datas': xml_data.encode('utf-8'),
                'res_model': 'account.move',
                'res_id': self.id,
                'mimetype': 'application/xml'
            })

            self.message_post(
                body=f'''XML Debug Information (Invoices Format):

Invoice: {self.name}
XML Length: {len(xml_data)} characters
Key: ODOO_{self.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}

Configuration Used:
• VNPT Account: {vnpt_config.vnpt_account}
• VNPT Username: {vnpt_config.vnpt_username}
• Pattern: {vnpt_config.invoice_template}
• Serial: {vnpt_config.invoice_serial}
• Type: {vnpt_config.invoice_type}

XML file attached for review.
Check server logs for full XML content.''',
                subject='VNPT XML Debug (Invoices Format)',
                attachment_ids=[attachment.id]
            )

        except Exception as e:
            _logger.error(f"XML debug failed: {str(e)}")
            raise UserError(f'XML debug failed: {str(e)}')

    def action_sync_vnpt_status(self):
        """Synchronize invoice status with VNPT"""
        for invoice in self:
            if not invoice.vnpt_invoice_id:
                continue

            vnpt_config = invoice._get_vnpt_config()
            if not vnpt_config:
                continue

            try:
                client = vnpt_config._get_soap_client()
                available_ops = self._get_available_operations(client)

                if 'getStatusInv' in available_ops:
                    status_params = {
                        'Account': vnpt_config.vnpt_account,
                        'ACpass': vnpt_config.vnpt_password,
                        'username': vnpt_config.vnpt_username,
                        'password': vnpt_config.vnpt_user_password,
                        'xmlFkeyInv': f'<Inv><Fkey>ODOO_{invoice.id}_*</Fkey></Inv>',
                        'pattern': vnpt_config.invoice_template,
                        'serial': vnpt_config.invoice_serial
                    }

                    status_response = client.service.getStatusInv(**status_params)

                    # Process status response
                    invoice.message_post(
                        body=f'VNPT status response: {status_response}',
                        subject='VNPT Status Sync'
                    )

            except Exception as e:
                _logger.error(f"Failed to sync VNPT status for invoice {invoice.name}: {str(e)}")
                invoice.message_post(
                    body=f'VNPT status sync failed: {str(e)}',
                    subject='VNPT Status Sync Error'
                )