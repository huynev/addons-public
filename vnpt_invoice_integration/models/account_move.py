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
        """Validate all prerequisites before sending to VNPT - UPDATED for TT78"""
        errors = []

        # Check VNPT configuration
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

        # Check company information - seller (NBan)
        if not self.company_id.vat:
            errors.append('Company tax code (MST) is required')
        if not self.company_id.name:
            errors.append('Company name is required')

        # Check invoice data - buyer (NMua) - REQUIRED fields per TT78
        if not self.partner_id:
            errors.append('Customer (NMua) is required')
        if not self.partner_id.name:
            errors.append('Customer name (Ten) is required - TT78 mandatory field')

        # DChi - Địa chỉ is REQUIRED per TT78
        partner_address = self._get_partner_address(self.partner_id)
        if not partner_address and not self.partner_id.street:
            errors.append('Customer address (DChi) is required - TT78 mandatory field')

        # Check invoice lines - REQUIRED fields per TT78
        if not self.invoice_line_ids.filtered(lambda l: l.display_type):
            errors.append('Invoice must have at least one product/service line (HHDVu)')

        for line in self.invoice_line_ids.filtered(lambda l: not l.display_type):
            line_name = line.product_id.name or line.name
            if not line_name:
                errors.append(f'Product/service name (THHDVu) is required for line - TT78 mandatory field')
            if line.quantity <= 0:
                errors.append(f'Quantity (SLuong) must be positive for line: {line_name}')
            if line.price_unit < 0:
                errors.append(f'Unit price (DGia) cannot be negative for line: {line_name}')

        # Currency validation - TT78 format
        if self.currency_id.name != 'VND':
            errors.append('Invoice currency must be VND for VNPT e-invoice (DVTTe field requirement)')

        # Invoice date validation
        if not self.invoice_date:
            errors.append('Invoice date is required')

        # Payment method validation - TT78 requires HTTToan
        payment_method = self._get_payment_method()
        if not payment_method:
            errors.append('Payment method (HTTToan) is required - TT78 mandatory field')

        # Test VNPT connection
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
                _('Cannot send to VNPT due to TT78 validation errors:\n') +
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
        """Prepare invoice lines data - UPDATED for TT78 format"""
        lines = []
        for line in self.invoice_line_ids.filtered(lambda l: l.display_type):
            # Calculate VAT properly
            vat_rate = 0
            vat_amount = 0
            if line.tax_ids:
                # Take first tax rate (assume single tax per line)
                vat_rate = line.tax_ids[0].amount
                vat_amount = line.price_subtotal * vat_rate / 100

            line_data = {
                'stt': len(lines) + 1,
                'tchat': '1',  # 1-Hàng hóa, dịch vụ
                'mhhdvu': line.product_id.default_code or '',
                'thhdvu': line.product_id.name or line.name,  # REQUIRED *
                'dvtinh': line.product_uom_id.name if line.product_uom_id else '',
                'sluong': line.quantity,
                'dgia': line.price_unit,
                'thtien': line.price_subtotal,  # Thành tiền chưa thuế
                'tsuat': vat_rate,  # Thuế suất
                'tthue': vat_amount,  # Tiền thuế
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
        """UPDATED: Send to VNPT với format TT78 chuẩn"""
        client = vnpt_config._get_soap_client()

        # Create XML data theo format TT78
        xml_data = self._create_vnpt_xml_tt78(invoice_data)
        # Log the XML being sent for debugging
        _logger.info(f"VNPT XML Data (TT78 format) for invoice {self.name}:\n{xml_data}")

        try:
            # Call ImportAndPublishInv với XML TT78
            _logger.info(f"Calling ImportAndPublishInv (TT78 format) for invoice {self.name}...")

            response = client.service.ImportAndPublishInv(
                Account=invoice_data['Account'],
                ACpass=invoice_data['ACpass'],
                xmlInvData=xml_data,  # XML data theo format TT78
                username=invoice_data['username'],
                password=invoice_data['password'],
                pattern=invoice_data['pattern'],
                serial=invoice_data['serial'],
                convert=invoice_data['convert']
            )

            # Enhanced response logging
            _logger.info(f"VNPT Response (TT78 format): {response}")

            # Parse response theo format trong tài liệu
            self._parse_vnpt_response_format(response)

            return response

        except Exception as e:
            _logger.error(f"VNPT API call failed (TT78 format) for invoice {self.name}: {str(e)}")
            raise UserError(f'VNPT service call failed: {str(e)}')

    def _create_vnpt_xml_tt78(self, invoice_data):
        """Create XML theo format TT78 chuẩn Việt Nam - FIXED ERR:3 Issues"""
        import xml.etree.ElementTree as ET
        from datetime import datetime

        # Create root element DSHDon
        root = ET.Element('DSHDon')

        # Create HDon element
        hdon = ET.SubElement(root, 'HDon')

        # key element - unique invoice key (REQUIRED *)
        key = ET.SubElement(hdon, 'key')
        key.text = f"ODOO_{self.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # DLHDon element - Dữ liệu hóa đơn
        dlhdon = ET.SubElement(hdon, 'DLHDon')

        # TTChung - Thông tin chung
        ttchung = ET.SubElement(dlhdon, 'TTChung')

        # SHDon - Số hóa đơn (để trống rõ ràng)
        # shdon = ET.SubElement(ttchung, 'SHDon')
        # shdon.text = ''  # FIXED: Empty string instead of self-closing tag

        # DVTTe - Đơn vị tiền tệ * (REQUIRED)
        dvtte = ET.SubElement(ttchung, 'DVTTe')
        dvtte.text = 'VND'

        # HTTToan - Hình thức thanh toán * (REQUIRED)
        htttoan = ET.SubElement(ttchung, 'HTTToan')
        htttoan.text = invoice_data['payment_method']

        # HDDThu - Hóa đơn đặc thù (0-hóa đơn thường)
        hddthu = ET.SubElement(ttchung, 'HDDThu')
        hddthu.text = '0'

        # NDHDon - Nội dung hóa đơn
        ndhdon = ET.SubElement(dlhdon, 'NDHDon')

        # NBan - Thông tin người bán - FIXED: Bắt buộc có email
        nban = ET.SubElement(ndhdon, 'NBan')

        company = invoice_data['company']

        # SDThoai - REQUIRED for NBan
        if company.phone:
            sdthoai_nban = ET.SubElement(nban, 'SDThoai')
            sdthoai_nban.text = str(company.phone).strip()

        # DCTDTu - EMAIL REQUIRED for NBan - CRITICAL FIX
        if company.email:
            dctdtu_nban = ET.SubElement(nban, 'DCTDTu')
            dctdtu_nban.text = str(company.email).strip()
        else:
            # VNPT có thể yêu cầu email bắt buộc
            dctdtu_nban = ET.SubElement(nban, 'DCTDTu')
            dctdtu_nban.text = f"noreply@{company.name.lower().replace(' ', '')}.vn"

        # Website
        if company.website:
            website = ET.SubElement(nban, 'Website')
            website.text = str(company.website).strip()

        # Bank information if available
        if hasattr(company, 'bank_ids') and company.bank_ids:
            bank_account = company.bank_ids[0]
            if bank_account.acc_number:
                stkn_hang = ET.SubElement(nban, 'STKNHang')
                stkn_hang.text = str(bank_account.acc_number).strip()

            if bank_account.bank_id and bank_account.bank_id.name:
                tn_hang = ET.SubElement(nban, 'TNHang')
                tn_hang.text = str(bank_account.bank_id.name).strip()

        # TCHang - Tên cửa hàng
        if company.name:
            tc_hang = ET.SubElement(nban, 'TCHang')
            tc_hang.text = str(company.name).strip()

        # NMua - Thông tin người mua
        nmua = ET.SubElement(ndhdon, 'NMua')

        partner = invoice_data['partner']

        # CRITICAL CHECK: Ensure NBan != NMua
        if partner.id == company.partner_id.id:
            # Internal transaction - create distinct buyer info
            ten = ET.SubElement(nmua, 'Ten')
            ten.text = f"{partner.name} - Chi nhánh"

            if partner.vat:
                mst = ET.SubElement(nmua, 'MST')
                mst.text = str(partner.vat).strip()

            dchi = ET.SubElement(nmua, 'DChi')
            dchi.text = f"Chi nhánh - {self._get_partner_address(partner) or 'Địa chỉ không xác định'}"

        else:
            # External customer
            ten = ET.SubElement(nmua, 'Ten')
            ten.text = str(partner.name or 'Khách lẻ').strip()

            # MST - Mã số thuế (Bắt buộc nếu có)
            if partner.vat:
                mst = ET.SubElement(nmua, 'MST')
                mst.text = str(partner.vat).strip()

            # DChi - Địa chỉ * (REQUIRED)
            dchi = ET.SubElement(nmua, 'DChi')
            dchi.text = str(self._get_partner_address(partner) or 'Địa chỉ không xác định').strip()

        # MKHang - Mã khách hàng
        if partner.ref:
            mkhang = ET.SubElement(nmua, 'MKHang')
            mkhang.text = str(partner.ref).strip()

        # SDThoai - Số điện thoại
        if partner.phone:
            sdthoai_nmua = ET.SubElement(nmua, 'SDThoai')
            sdthoai_nmua.text = str(partner.phone).strip()

        # DCTDTu - Địa chỉ thư điện tử
        if partner.email:
            dctdtu_nmua = ET.SubElement(nmua, 'DCTDTu')
            dctdtu_nmua.text = str(partner.email).strip()

        # HVTNMHang - Họ và tên người mua hàng (Contact person) - ALWAYS ADD
        contact_name = self._get_buyer_contact_name(partner)
        hvtn_mhang = ET.SubElement(nmua, 'HVTNMHang')

        if contact_name:
            # Có contact person cụ thể
            hvtn_mhang.text = str(contact_name).strip()
            _logger.info(f"Added HVTNMHang: {contact_name}")
        elif not partner.is_company:
            # Partner là cá nhân → dùng tên chính
            hvtn_mhang.text = str(partner.name).strip()
            _logger.info(f"HVTNMHang fallback (individual): {partner.name}")
        else:
            # Company không có contact → tạo generic
            hvtn_mhang.text = f"Đại diện {partner.name}"
            _logger.info(f"HVTNMHang fallback (company): Đại diện {partner.name}")

        # Bank information for customer (if available)
        if hasattr(partner, 'bank_ids') and partner.bank_ids:
            customer_bank = partner.bank_ids[0]
            if customer_bank.acc_number:
                stkn_hang_customer = ET.SubElement(nmua, 'STKNHang')
                stkn_hang_customer.text = str(customer_bank.acc_number).strip()

            if customer_bank.bank_id and customer_bank.bank_id.name:
                tn_hang_customer = ET.SubElement(nmua, 'TNHang')
                tn_hang_customer.text = str(customer_bank.bank_id.name).strip()

        # DSHHDVu - Danh sách hàng hóa dịch vụ
        dshhvu = ET.SubElement(ndhdon, 'DSHHDVu')

        # Add each invoice line as HHDVu
        for idx, line_data in enumerate(invoice_data['invoice_lines'], 1):
            hhdvu = ET.SubElement(dshhvu, 'HHDVu')

            # TChat - Tính chất * (REQUIRED)
            tchat = ET.SubElement(hhdvu, 'TChat')
            tchat.text = '1'  # 1-Hàng hóa, dịch vụ

            # STT - Số thứ tự
            stt = ET.SubElement(hhdvu, 'STT')
            stt.text = str(idx)

            # MHHDVu - Mã hàng hóa, dịch vụ - FIXED: Always include
            mhhdvu = ET.SubElement(hhdvu, 'MHHDVu')
            mhhdvu.text = line_data.get('mhhdvu') or f"SP{str(idx).zfill(3)}"

            # THHDVu - Tên hàng hóa, dịch vụ * (REQUIRED)
            thhdvu = ET.SubElement(hhdvu, 'THHDVu')
            thhdvu.text = str(line_data['thhdvu']).strip()

            # DVTinh - Đơn vị tính - FIXED: Use standard units
            dvtinh = ET.SubElement(hhdvu, 'DVTinh')
            dvt = line_data.get('dvtinh', '').strip()
            if dvt in ['Đơn vị', '']:
                dvtinh.text = 'cái'  # Default standard unit
            else:
                dvtinh.text = dvt

            # SLuong - Số lượng - FIXED: Integer format
            if line_data.get('sluong') is not None:
                sluong = ET.SubElement(hhdvu, 'SLuong')
                sluong.text = str(int(line_data['sluong']))  # Remove decimals

            # DGia - Đơn giá - FIXED: Integer format
            if line_data.get('dgia') is not None:
                dgia = ET.SubElement(hhdvu, 'DGia')
                dgia.text = str(int(line_data['dgia']))  # Remove decimals

            # ThTien - Thành tiền - FIXED: Integer format
            thtien = ET.SubElement(hhdvu, 'ThTien')
            thtien.text = str(int(line_data['thtien']))

            # TSuat - Thuế suất
            if line_data.get('tsuat') is not None:
                tsuat = ET.SubElement(hhdvu, 'TSuat')
                tsuat.text = str(int(line_data['tsuat']))  # Remove decimals

            # TThue - Tiền thuế
            if line_data.get('tthue') is not None:
                tthue = ET.SubElement(hhdvu, 'TThue')
                tthue.text = str(int(line_data['tthue']))

            # TSThue - Tiền sau thuế
            if line_data.get('tsthue') is not None:
                tsthue = ET.SubElement(hhdvu, 'TSThue')
                tsthue.text = str(int(line_data['tsthue']))

        # TToan - Thông tin thanh toán
        ttoan = ET.SubElement(ndhdon, 'TToan')
        totals = invoice_data['totals']

        # THTTLTSuat - Tổng hợp theo từng loại thuế suất
        if any(line.get('tsuat', 0) > 0 for line in invoice_data['invoice_lines']):
            thttltsuat = ET.SubElement(ttoan, 'THTTLTSuat')

            # Group by tax rate
            tax_groups = {}
            for line_data in invoice_data['invoice_lines']:
                tax_rate = int(line_data.get('tsuat', 0))  # Integer tax rates
                if tax_rate not in tax_groups:
                    tax_groups[tax_rate] = {
                        'thtien': 0,
                        'tthue': 0
                    }
                tax_groups[tax_rate]['thtien'] += line_data.get('thtien', 0)
                tax_groups[tax_rate]['tthue'] += line_data.get('tthue', 0)

            # Create LTSuat for each tax rate
            for tax_rate, amounts in tax_groups.items():
                ltsuat = ET.SubElement(thttltsuat, 'LTSuat')

                tsuat_elem = ET.SubElement(ltsuat, 'TSuat')
                tsuat_elem.text = str(tax_rate)

                thtien_elem = ET.SubElement(ltsuat, 'ThTien')
                thtien_elem.text = str(int(amounts['thtien']))

                tthue_elem = ET.SubElement(ltsuat, 'TThue')
                tthue_elem.text = str(int(amounts['tthue']))

        # TgTCThue - Tổng tiền chưa thuế (Integer format)
        tgtcthue = ET.SubElement(ttoan, 'TgTCThue')
        tgtcthue.text = str(int(totals['tgtcthue']))

        # TgTThue - Tổng tiền thuế (Integer format)
        tgtthue = ET.SubElement(ttoan, 'TgTThue')
        tgtthue.text = str(int(totals['tgtthue']))

        # TgTTTBSo - Tổng tiền thanh toán bằng số (Integer format)
        tgtttbso = ET.SubElement(ttoan, 'TgTTTBSo')
        tgtttbso.text = str(int(totals['tgtttbso']))

        # TgTTTBChu - Tổng tiền thanh toán bằng chữ
        tgtttbchu = ET.SubElement(ttoan, 'TgTTTBChu')
        tgtttbchu.text = str(totals['tgtttbchu']).strip()

        # Convert to string with proper encoding
        xml_str = ET.tostring(root, encoding='utf-8', method='xml')

        # Add XML declaration and format nicely
        xml_declaration = '<?xml version="1.0" encoding="utf-8"?>\n'
        formatted_xml = xml_declaration + xml_str.decode('utf-8')

        return formatted_xml

    def _get_buyer_contact_name(self, partner):
        # 1. CONTACT PERSON trong child_ids (ưu tiên cao nhất)
        if partner.child_ids:
            # Tìm contact có function chứa "contact"
            contact_person = partner.child_ids.filtered(
                lambda c: c.function and 'contact' in c.function.lower()
            )
            if contact_person:
                return contact_person[0].name

            # Tìm person child đầu tiên
            person_child = partner.child_ids.filtered(lambda c: not c.is_company)
            if person_child:
                return person_child[0].name

        # 2. CUSTOM FIELD contact_name
        if hasattr(partner, 'contact_name') and partner.contact_name:
            return partner.contact_name

        # 3. PARTNER CÁ NHÂN
        if not partner.is_company and partner.name:
            return partner.name

        # 4. LINKED USERS
        if partner.user_ids:
            return partner.user_ids[0].name

        # 5. SALESPERSON (fallback)
        if self.user_id:
            return f"Đại diện: {self.user_id.name}"

        # Không tìm thấy
        return None

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
        """Debug XML that will be sent to VNPT - UPDATED for TT78 format"""
        vnpt_config = self._get_vnpt_config()
        if not vnpt_config:
            raise UserError(_('No VNPT configuration found'))

        try:
            # Validate prerequisites first
            self._validate_vnpt_prerequisites(vnpt_config)

            # Prepare invoice data
            invoice_data = self._prepare_vnpt_invoice_data(vnpt_config)

            # Generate XML theo format TT78
            xml_data = self._create_vnpt_xml_tt78(invoice_data)

            # Log for debugging
            _logger.info(f"Generated TT78 XML for invoice {self.name}:\n{xml_data}")

            # Create attachment with XML for easy viewing
            attachment = self.env['ir.attachment'].create({
                'name': f'VNPT_XML_TT78_Debug_{self.name}.xml',
                'type': 'binary',
                'datas': xml_data.encode('utf-8'),
                'res_model': 'account.move',
                'res_id': self.id,
                'mimetype': 'application/xml'
            })

            self.message_post(
                body=f'''XML Debug Information (TT78 Format):

Invoice: {self.name}
XML Length: {len(xml_data)} characters
Key: ODOO_{self.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}

Configuration Used:
• VNPT Account: {vnpt_config.vnpt_account}
• VNPT Username: {vnpt_config.vnpt_username}
• Pattern: {vnpt_config.invoice_template}
• Serial: {vnpt_config.invoice_serial}
• Type: {vnpt_config.invoice_type}

XML Structure (TT78 Standard):
• Root: DSHDon
• HDon/key: Unique invoice key
• HDon/DLHDon/TTChung: General information
• HDon/DLHDon/NDHDon/NBan: Seller information
• HDon/DLHDon/NDHDon/NMua: Buyer information
• HDon/DLHDon/NDHDon/DSHHDVu: Product/Service details
• HDon/DLHDon/NDHDon/TToan: Payment information

XML file attached for review.
Check server logs for full XML content.''',
                subject='VNPT XML Debug (TT78 Format)',
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