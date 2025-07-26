# -*- coding: utf-8 -*-

import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class VNPTInvoiceWizard(models.TransientModel):
    _name = 'vnpt.invoice.wizard'
    _description = 'VNPT Invoice Publishing Wizard'

    invoice_ids = fields.Many2many('account.move', string='Invoices',
                                   domain="[('state', '=', 'posted'), ('move_type', 'in', ['out_invoice', 'out_refund']), ('vnpt_status', 'in', ['draft', False])]")
    vnpt_config_id = fields.Many2one('vnpt.invoice.config', string='VNPT Configuration',
                                     required=True,
                                     domain="[('active', '=', True)]")
    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.company)

    # Options
    ignore_errors = fields.Boolean('Continue on Error', default=False,
                                   help='Continue processing other invoices if one fails')
    test_mode = fields.Boolean('Test Mode', default=False,
                               help='Run in test mode (dry run)')

    # Results
    success_count = fields.Integer('Successful', readonly=True)
    error_count = fields.Integer('Errors', readonly=True)
    processing_log = fields.Text('Processing Log', readonly=True)

    @api.onchange('company_id')
    def _onchange_company_id(self):
        """Update VNPT config domain when company changes"""
        if self.company_id:
            default_config = self.env['vnpt.invoice.config'].get_default_config(self.company_id.id)
            if default_config:
                self.vnpt_config_id = default_config.id

        return {
            'domain': {
                'vnpt_config_id': [('company_id', '=', self.company_id.id), ('active', '=', True)],
                'invoice_ids': [('company_id', '=', self.company_id.id),
                                ('state', '=', 'posted'),
                                ('move_type', 'in', ['out_invoice', 'out_refund']),
                                ('vnpt_status', 'in', ['draft', False])]
            }
        }

    @api.model
    def default_get(self, fields_list):
        """Set default values from context"""
        res = super().default_get(fields_list)

        # Get invoices from context (if called from invoice list)
        active_ids = self.env.context.get('active_ids', [])
        active_model = self.env.context.get('active_model', '')

        if active_model == 'account.move' and active_ids:
            invoices = self.env['account.move'].browse(active_ids)
            # Filter valid invoices
            valid_invoices = invoices.filtered(
                lambda inv: inv.state == 'posted'
                            and inv.move_type in ['out_invoice', 'out_refund']
                            and inv.vnpt_status in ['draft', False]
            )
            res['invoice_ids'] = [(6, 0, valid_invoices.ids)]

        # Set default config
        company = self.env.company
        default_config = self.env['vnpt.invoice.config'].get_default_config(company.id)
        if default_config:
            res['vnpt_config_id'] = default_config.id

        return res

    def action_publish_invoices(self):
        """Publish selected invoices to VNPT"""
        if not self.invoice_ids:
            raise UserError(_('Please select at least one invoice to publish.'))

        if not self.vnpt_config_id:
            raise UserError(_('Please select a VNPT configuration.'))

        self.success_count = 0
        self.error_count = 0
        log_lines = []

        # Test connection first
        try:
            self.vnpt_config_id.test_connection()
        except Exception as e:
            raise UserError(_('VNPT connection test failed: %s') % str(e))

        # Process each invoice
        for invoice in self.invoice_ids:
            try:
                log_lines.append(f"Processing invoice {invoice.name}...")

                if self.test_mode:
                    log_lines.append(f"  [TEST MODE] Would publish invoice {invoice.name}")
                    self.success_count += 1
                else:
                    # Set the config for this invoice
                    invoice.vnpt_config_id = self.vnpt_config_id

                    # Publish to VNPT
                    invoice.action_publish_to_vnpt()

                    log_lines.append(f"  ✓ Successfully published: {invoice.vnpt_invoice_number or 'N/A'}")
                    self.success_count += 1

            except Exception as e:
                error_msg = str(e)
                log_lines.append(f"  ✗ Error: {error_msg}")
                self.error_count += 1

                if not self.ignore_errors:
                    self.processing_log = '\n'.join(log_lines)
                    raise UserError(_('Failed to publish invoice %s: %s') % (invoice.name, error_msg))

        # Update log
        self.processing_log = '\n'.join(log_lines)

        # Show results
        if self.error_count == 0:
            message = _('Successfully published %d invoices to VNPT.') % self.success_count
            notification_type = 'success'
        else:
            message = _('Published %d invoices successfully, %d failed.') % (self.success_count, self.error_count)
            notification_type = 'warning'

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('VNPT Publishing Results'),
                'message': message,
                'type': notification_type,
            }
        }

    def action_view_results(self):
        """View detailed results"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('VNPT Publishing Results'),
            'res_model': 'vnpt.invoice.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': {'show_results': True},
        }


class VNPTInvoiceSyncWizard(models.TransientModel):
    _name = 'vnpt.invoice.sync.wizard'
    _description = 'VNPT Invoice Sync Wizard'

    invoice_ids = fields.Many2many('account.move', string='Invoices',
                                   domain="[('vnpt_invoice_id', '!=', False)]")
    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.company)

    sync_count = fields.Integer('Synced', readonly=True)
    error_count = fields.Integer('Errors', readonly=True)
    sync_log = fields.Text('Sync Log', readonly=True)

    @api.model
    def default_get(self, fields_list):
        """Set default values from context"""
        res = super().default_get(fields_list)

        active_ids = self.env.context.get('active_ids', [])
        active_model = self.env.context.get('active_model', '')

        if active_model == 'account.move' and active_ids:
            invoices = self.env['account.move'].browse(active_ids)
            valid_invoices = invoices.filtered(lambda inv: inv.vnpt_invoice_id)
            res['invoice_ids'] = [(6, 0, valid_invoices.ids)]

        return res

    def action_sync_invoices(self):
        """Synchronize invoice status with VNPT"""
        if not self.invoice_ids:
            raise UserError(_('Please select at least one invoice to sync.'))

        self.sync_count = 0
        self.error_count = 0
        log_lines = []

        for invoice in self.invoice_ids:
            try:
                log_lines.append(f"Syncing invoice {invoice.name} (VNPT ID: {invoice.vnpt_invoice_id})...")

                # Call sync method (to be implemented)
                invoice.action_sync_vnpt_status()

                log_lines.append(f"  ✓ Synced successfully")
                self.sync_count += 1

            except Exception as e:
                error_msg = str(e)
                log_lines.append(f"  ✗ Sync error: {error_msg}")
                self.error_count += 1

        self.sync_log = '\n'.join(log_lines)

        message = _('Synced %d invoices, %d errors.') % (self.sync_count, self.error_count)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('VNPT Sync Results'),
                'message': message,
                'type': 'success' if self.error_count == 0 else 'warning',
            }
        }