# vnpt_config.py
# -*- coding: utf-8 -*-

import logging
import requests
from zeep import Client, Settings, Transport
from zeep.exceptions import Fault
from requests import Session
from requests.auth import HTTPBasicAuth
import xml.etree.ElementTree as ET

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class VNPTInvoiceConfig(models.Model):
    _name = 'vnpt.invoice.config'
    _description = 'VNPT Invoice Configuration'
    _rec_name = 'name'

    name = fields.Char('Configuration Name', required=True, default='VNPT Main Config')
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.company)

    # VNPT Connection Settings - Updated based on new configuration
    vnpt_url = fields.Char('Publish Service URL', required=True,
                           default='https://admindemo.vnpt-invoice.com.vn/PublishService.asmx',
                           help='VNPT Invoice Publish Service URL')

    # Additional service URLs
    vnpt_portal_url = fields.Char('Portal Service URL',
                                  default='https://admindemo.vnpt-invoice.com.vn/PortalService.asmx',
                                  help='VNPT Portal Service URL')
    vnpt_business_url = fields.Char('Business Service URL',
                                    default='https://admindemo.vnpt-invoice.com.vn/BusinessService.asmx',
                                    help='VNPT Business Service URL')

    # Updated authentication fields based on screenshot
    vnpt_account = fields.Char('Account', required=True,
                               help='Account provided by VNPT')
    vnpt_password = fields.Char('Password', required=True,
                                help='Password provided by VNPT')
    vnpt_username = fields.Char('Username', required=True,
                                help='Username for service operations')
    vnpt_user_password = fields.Char('User Password', required=True,
                                     help='User password for service operations')

    vnpt_tax_code = fields.Char('Company Tax Code', required=True,
                                help='Company Tax Identification Number')

    # Invoice Template Settings
    invoice_template = fields.Char('Invoice Template', required=True, default='2/005',
                                   help='Invoice template registered with VNPT (e.g., 2/005)')
    invoice_serial = fields.Char('Invoice Serial', required=True, default='K25TBS',
                                 help='Invoice serial registered with VNPT (e.g., K25TBS)')
    invoice_type = fields.Selection([
        ('1', 'VAT Invoice'),
        ('2', 'Sales Invoice'),
        ('3', 'Other'),
        ('4', 'Reserve Invoice'),
        ('5', 'Asset Sales Invoice'),
    ], string='Invoice Type', default='1', required=True)

    # Test/Production Environment - Default to Test Mode as shown in screenshot
    is_test_mode = fields.Boolean('Test Mode', default=True,
                                  help='Enable test mode for VNPT integration')

    # Status and Connection Test
    connection_status = fields.Selection([
        ('not_tested', 'Not Tested'),
        ('success', 'Connected'),
        ('failed', 'Connection Failed'),
        ('auth_failed', 'Authentication Failed'),
        ('partial', 'Partial Connection'),
    ], string='Connection Status', default='not_tested', readonly=True)

    last_test_date = fields.Datetime('Last Test Date', readonly=True)
    last_error_message = fields.Text('Last Error Message', readonly=True)
    last_test_details = fields.Text('Last Test Details', readonly=True)

    # Active Configuration
    active = fields.Boolean('Active', default=True)
    is_default = fields.Boolean('Default Configuration', default=False,
                                help='Set as default configuration for this company')

    @api.constrains('is_default', 'company_id')
    def _check_default_config(self):
        """Ensure only one default configuration per company"""
        for record in self:
            if record.is_default:
                existing = self.search([
                    ('company_id', '=', record.company_id.id),
                    ('is_default', '=', True),
                    ('id', '!=', record.id)
                ])
                if existing:
                    raise ValidationError(_('Only one default VNPT configuration is allowed per company.'))

    def test_connection(self):
        """Enhanced connection test to VNPT service with new configuration"""
        self.ensure_one()

        test_results = []
        overall_status = 'failed'
        error_messages = []

        try:
            # Step 1: Test Publish Service accessibility
            _logger.info(f"Testing VNPT Publish Service connection to: {self.vnpt_url}")
            test_results.append("🔍 Testing Publish Service WSDL accessibility...")

            client = self._get_soap_client()
            test_results.append("✅ Publish Service WSDL loaded successfully")

            # Step 2: Test Portal Service if configured
            if self.vnpt_portal_url:
                test_results.append("🔍 Testing Portal Service accessibility...")
                try:
                    portal_client = self._get_portal_client()
                    test_results.append("✅ Portal Service WSDL loaded successfully")
                except Exception as e:
                    test_results.append(f"⚠️ Portal Service failed: {str(e)}")

            # Step 3: Test Business Service if configured
            if self.vnpt_business_url:
                test_results.append("🔍 Testing Business Service accessibility...")
                try:
                    business_client = self._get_business_client()
                    test_results.append("✅ Business Service WSDL loaded successfully")
                except Exception as e:
                    test_results.append(f"⚠️ Business Service failed: {str(e)}")

            # Step 4: Check available operations
            test_results.append("🔍 Checking available operations...")
            available_ops = self._get_available_operations(client)

            if available_ops:
                test_results.append(f"✅ Found {len(available_ops)} operations: {', '.join(available_ops[:5])}")
                if len(available_ops) > 5:
                    test_results.append(f"   ... and {len(available_ops) - 5} more")
            else:
                test_results.append("❌ No operations found")
                error_messages.append("No SOAP operations detected")

            # Step 5: Test server connectivity
            test_results.append("🔍 Testing server connectivity...")
            server_test = self._test_server_methods(client, available_ops)
            test_results.extend(server_test['results'])
            if server_test['errors']:
                error_messages.extend(server_test['errors'])

            # Step 6: Test authentication with new credentials
            test_results.append("🔍 Testing authentication...")
            auth_test = self._test_authentication_new(client, available_ops)
            test_results.extend(auth_test['results'])
            if auth_test['errors']:
                error_messages.extend(auth_test['errors'])

            # Step 7: Test invoice operations
            test_results.append("🔍 Testing invoice operations...")
            invoice_test = self._test_invoice_operations(client, available_ops)
            test_results.extend(invoice_test['results'])
            if invoice_test['errors']:
                error_messages.extend(invoice_test['errors'])

            # Determine overall status
            if not error_messages:
                overall_status = 'success'
                test_results.append("🎉 All tests passed!")
            elif 'ImportAndPublishInv' in available_ops and len(error_messages) <= 2:
                overall_status = 'partial'
                test_results.append("⚠️ Partial success - some issues detected")
            elif any('auth' in err.lower() for err in error_messages):
                overall_status = 'auth_failed'
                test_results.append("🔐 Authentication failed")
            else:
                overall_status = 'failed'
                test_results.append("❌ Connection test failed")

            # Update status
            self.connection_status = overall_status
            self.last_test_date = fields.Datetime.now()
            self.last_error_message = '\n'.join(error_messages) if error_messages else False
            self.last_test_details = '\n'.join(test_results)

            # Prepare response
            if overall_status == 'success':
                notification_type = 'success'
                title = 'Connection Successful'
                message = f"✅ VNPT connection fully operational!\n\n{chr(10).join(test_results[-5:])}"
            elif overall_status == 'partial':
                notification_type = 'warning'
                title = 'Partial Connection'
                message = f"⚠️ VNPT connection has some issues:\n\n{chr(10).join(test_results[-5:])}\n\nErrors: {chr(10).join(error_messages)}"
            elif overall_status == 'auth_failed':
                notification_type = 'danger'
                title = 'Authentication Failed'
                message = f"🔐 VNPT authentication failed:\n\n{chr(10).join(error_messages)}\n\nPlease check account/username and passwords"
            else:
                notification_type = 'danger'
                title = 'Connection Failed'
                message = f"❌ VNPT connection failed:\n\n{chr(10).join(error_messages)}"

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _(title),
                    'message': _(message),
                    'type': notification_type,
                }
            }

        except Exception as e:
            _logger.error(f"VNPT connection test failed with exception: {str(e)}")

            error_msg = str(e)
            test_results.append(f"💥 Critical error: {error_msg}")

            self.connection_status = 'failed'
            self.last_test_date = fields.Datetime.now()
            self.last_error_message = error_msg
            self.last_test_details = '\n'.join(test_results)

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Connection Error'),
                    'message': _('Critical error during VNPT connection test:\n%s') % error_msg,
                    'type': 'danger',
                }
            }

    def _test_authentication_new(self, client, available_ops):
        """Test authentication with new credential structure"""
        results = []
        errors = []

        if not self.vnpt_account or not self.vnpt_password:
            results.append("⚠️ No account credentials provided for auth test")

        if not self.vnpt_username or not self.vnpt_user_password:
            results.append("⚠️ No username credentials provided for auth test")

        # Test SignIn with account credentials if available
        if 'SignIn' in available_ops and self.vnpt_account and self.vnpt_password:
            try:
                signin_params = {
                    'userName': self.vnpt_account,
                    'pass': self.vnpt_password
                }
                signin_response = client.service.SignIn(**signin_params)
                response_str = str(signin_response).strip()

                if response_str.startswith('ERR:'):
                    error_code = response_str.split(':')[1] if ':' in response_str else 'unknown'
                    results.append(f"🔐 SignIn (Account) failed: {response_str}")
                    errors.append(f"Account authentication error: {response_str}")
                elif response_str in ['0', 'OK', 'SUCCESS']:
                    results.append(f"✅ SignIn (Account) successful: {response_str}")
                else:
                    results.append(f"✅ SignIn (Account) response: {response_str}")

            except Exception as e:
                error_msg = str(e)
                results.append(f"❌ SignIn (Account) exception: {error_msg}")
                errors.append(f"Account SignIn test failed: {error_msg}")

        # Test getStatusInv with username credentials (this tests service auth)
        if 'getStatusInv' in available_ops and self.vnpt_username and self.vnpt_user_password:
            try:
                status_response = client.service.getStatusInv(
                    Account=self.vnpt_username,
                    ACpass=self.vnpt_user_password,
                    invIDs=[999999]  # Dummy ID
                )
                response_str = str(status_response).strip()

                if response_str.startswith('ERR:'):
                    if 'ERR:1' in response_str:
                        results.append(f"🔐 getStatusInv (Username) auth failed: {response_str}")
                        errors.append(f"Username authentication failed: Invalid credentials")
                    else:
                        results.append(f"✅ getStatusInv (Username) auth OK (dummy ID not found): {response_str}")
                else:
                    results.append(f"✅ getStatusInv (Username) response: {response_str}")

            except Exception as e:
                error_msg = str(e)
                if 'ERR:1' in error_msg:
                    results.append(f"🔐 getStatusInv (Username) auth failed: ERR:1")
                    errors.append("Username authentication failed: Invalid credentials")
                else:
                    results.append(f"❌ getStatusInv (Username) exception: {error_msg}")

        return {'results': results, 'errors': errors}

    def _get_soap_client(self):
        """Get configured SOAP client for VNPT Publish Service"""
        self.ensure_one()

        session = Session()
        transport = Transport(session=session, timeout=30)
        settings = Settings(strict=False, xml_huge_tree=True)

        try:
            wsdl_url = self.vnpt_url
            if not wsdl_url.endswith('?wsdl'):
                wsdl_url += '?wsdl'

            _logger.info(f"Creating SOAP client for Publish Service: {wsdl_url}")
            client = Client(wsdl_url, transport=transport, settings=settings)
            return client
        except Exception as e:
            _logger.error(f"Failed to create Publish Service SOAP client: {str(e)}")
            raise UserError(
                _('Failed to connect to VNPT Publish Service: %s\n\nCheck:\n1. URL is correct\n2. VNPT service is accessible\n3. Network connectivity') % str(
                    e))

    def _get_portal_client(self):
        """Get configured SOAP client for VNPT Portal Service"""
        self.ensure_one()

        if not self.vnpt_portal_url:
            raise UserError(_('Portal Service URL not configured'))

        session = Session()
        transport = Transport(session=session, timeout=30)
        settings = Settings(strict=False, xml_huge_tree=True)

        try:
            wsdl_url = self.vnpt_portal_url
            if not wsdl_url.endswith('?wsdl'):
                wsdl_url += '?wsdl'

            _logger.info(f"Creating SOAP client for Portal Service: {wsdl_url}")
            client = Client(wsdl_url, transport=transport, settings=settings)
            return client
        except Exception as e:
            _logger.error(f"Failed to create Portal Service SOAP client: {str(e)}")
            raise UserError(_('Failed to connect to VNPT Portal Service: %s') % str(e))

    def _get_business_client(self):
        """Get configured SOAP client for VNPT Business Service"""
        self.ensure_one()

        if not self.vnpt_business_url:
            raise UserError(_('Business Service URL not configured'))

        session = Session()
        transport = Transport(session=session, timeout=30)
        settings = Settings(strict=False, xml_huge_tree=True)

        try:
            wsdl_url = self.vnpt_business_url
            if not wsdl_url.endswith('?wsdl'):
                wsdl_url += '?wsdl'

            _logger.info(f"Creating SOAP client for Business Service: {wsdl_url}")
            client = Client(wsdl_url, transport=transport, settings=settings)
            return client
        except Exception as e:
            _logger.error(f"Failed to create Business Service SOAP client: {str(e)}")
            raise UserError(_('Failed to connect to VNPT Business Service: %s') % str(e))

    def _get_available_operations(self, client):
        """Get list of available operations from VNPT service"""
        try:
            operations = []

            # PublishService operations (priority)
            publish_ops = [
                'ImportAndPublishInv', 'ImportInv', 'ImportInvByPattern',
                'ImportAndPublishAssignedNo', 'publishInv', 'getStatusInv',
                'GetInvoiceByFkey', 'updateInvoice', 'deleteInvoiceByFkey',
                'SignIn', 'getDateTimeServer', 'getCurrentNo'
            ]

            # PortalService operations (fallback)
            portal_ops = [
                'convertForStore', 'convertForVerify', 'getInvView',
                'downloadInv', 'SearchInv', 'loginportal'
            ]

            # Check all operations
            all_ops = publish_ops + portal_ops

            for op in all_ops:
                if hasattr(client.service, op):
                    operations.append(op)

            return operations

        except Exception as e:
            _logger.warning(f"Could not get available operations: {str(e)}")
            return []

    def _test_server_methods(self, client, available_ops):
        """Test basic server connectivity methods"""
        results = []
        errors = []

        # Test getDateTimeServer if available
        if 'getDateTimeServer' in available_ops:
            try:
                server_time = client.service.getDateTimeServer()
                results.append(f"✅ Server time: {server_time}")
            except Exception as e:
                error_msg = str(e)
                results.append(f"❌ getDateTimeServer failed: {error_msg}")
                errors.append(f"Server time test failed: {error_msg}")
        else:
            results.append("⚠️ getDateTimeServer not available")

        # # Test getCurrentNo if available
        # if 'getCurrentNo' in available_ops:
        #     try:
        #         # Use username credentials for service operations
        #         getCurrentNo_params = {
        #             'account': self.vnpt_username,
        #             'pass': self.vnpt_user_password,
        #             'pattern': self.invoice_template,
        #             'serial': self.invoice_serial
        #         }
        #         current_no = client.service.getCurrentNo(**getCurrentNo_params)
        #         results.append(f"✅ getCurrentNo: {current_no}")
        #     except Exception as e:
        #         error_msg = str(e)
        #         if 'ERR:' in error_msg or 'authentication' in error_msg.lower():
        #             results.append(f"🔐 getCurrentNo requires auth (expected): {error_msg}")
        #         else:
        #             results.append(f"❌ getCurrentNo failed: {error_msg}")
        #             errors.append(f"getCurrentNo test failed: {error_msg}")

        return {'results': results, 'errors': errors}

    def _test_invoice_operations(self, client, available_ops):
        """Test invoice-related operations availability"""
        results = []
        errors = []

        # Check critical operations
        critical_ops = ['ImportAndPublishInv', 'ImportInv', 'ImportInvByPattern']
        found_critical = [op for op in critical_ops if op in available_ops]

        if found_critical:
            results.append(f"✅ Invoice operations available: {', '.join(found_critical)}")
        else:
            results.append("❌ No critical invoice operations found")
            errors.append("Missing critical invoice operations (ImportAndPublishInv, ImportInv, etc.)")

        # Check supporting operations
        support_ops = ['publishInv', 'GetInvoiceByFkey', 'getStatusInv']
        found_support = [op for op in support_ops if op in available_ops]

        if found_support:
            results.append(f"✅ Support operations: {', '.join(found_support)}")
        else:
            results.append("⚠️ Limited support operations available")

        # Validate configuration
        config_issues = []
        if not self.invoice_template:
            config_issues.append("Missing invoice template")
        if not self.invoice_serial:
            config_issues.append("Missing invoice serial")
        if not self.vnpt_tax_code:
            config_issues.append("Missing company tax code")

        if config_issues:
            results.append(f"⚠️ Configuration issues: {', '.join(config_issues)}")
            errors.extend(config_issues)
        else:
            results.append("✅ Configuration appears complete")

        return {'results': results, 'errors': errors}

    def action_view_test_details(self):
        """View detailed test results"""
        self.ensure_one()

        if not self.last_test_details:
            raise UserError(_('No test details available. Run connection test first.'))

        return {
            'type': 'ir.actions.act_window',
            'name': _('VNPT Connection Test Details'),
            'res_model': 'vnpt.test.details.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_config_name': self.name,
                'default_test_date': self.last_test_date,
                'default_connection_status': self.connection_status,
                'default_test_details': self.last_test_details,
                'default_error_message': self.last_error_message,
            }
        }

    @api.model
    def get_default_config(self, company_id=None):
        """Get default VNPT configuration for company"""
        if not company_id:
            company_id = self.env.company.id

        config = self.search([
            ('company_id', '=', company_id),
            ('is_default', '=', True),
            ('active', '=', True)
        ], limit=1)

        if not config:
            config = self.search([
                ('company_id', '=', company_id),
                ('active', '=', True)
            ], limit=1)

        return config

    @property
    def wsdl_url(self):
        """Get WSDL URL for this configuration"""
        url = self.vnpt_url
        if not url.endswith('?wsdl'):
            url += '?wsdl'
        return url


# Wizard for displaying test details
class VNPTTestDetailsWizard(models.TransientModel):
    _name = 'vnpt.test.details.wizard'
    _description = 'VNPT Test Details'

    config_name = fields.Char('Configuration', readonly=True)
    test_date = fields.Datetime('Test Date', readonly=True)
    connection_status = fields.Selection([
        ('not_tested', 'Not Tested'),
        ('success', 'Connected'),
        ('failed', 'Connection Failed'),
        ('auth_failed', 'Authentication Failed'),
        ('partial', 'Partial Connection'),
    ], string='Status', readonly=True)
    test_details = fields.Text('Test Details', readonly=True)
    error_message = fields.Text('Error Messages', readonly=True)