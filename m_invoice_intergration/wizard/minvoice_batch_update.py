from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class MInvoiceBatchUpdate(models.TransientModel):
    _name = 'minvoice.batch.update'
    _description = 'M-Invoice Batch Status Update'

    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.company)
    date_from = fields.Date('From Date', required=True,
                            default=lambda self: fields.Date.today().replace(day=1))
    date_to = fields.Date('To Date', required=True,
                          default=fields.Date.today())
    status_filter = fields.Selection([
        ('pending', 'Pending Status Only'),
        ('all', 'All M-Invoice Records'),
        ('error', 'Error Status Only')
    ], string='Filter', default='pending', required=True)

    invoice_ids = fields.Many2many('account.move', string='Invoices to Update')
    total_count = fields.Integer('Total Invoices', readonly=True)
    updated_count = fields.Integer('Updated Count', readonly=True)
    error_count = fields.Integer('Error Count', readonly=True)

    @api.onchange('company_id', 'date_from', 'date_to', 'status_filter')
    def _onchange_filters(self):
        """Tự động load danh sách hóa đơn theo filter"""
        domain = [
            ('company_id', '=', self.company_id.id),
            ('invoice_date', '>=', self.date_from),
            ('invoice_date', '<=', self.date_to),
            ('minvoice_id', '!=', False),
            ('move_type', 'in', ['out_invoice', 'out_refund'])
        ]

        if self.status_filter == 'pending':
            domain.append(('minvoice_status', 'in', ['draft', 'waiting', 'signed', 'sent']))
        elif self.status_filter == 'error':
            domain.append(('minvoice_status', 'in', ['error', 'rejected']))

        invoices = self.env['account.move'].search(domain)
        self.invoice_ids = invoices
        self.total_count = len(invoices)

    def action_batch_update(self):
        """Thực hiện batch update"""
        if not self.invoice_ids:
            raise ValidationError(_('No invoices selected for update'))

        # Reset counters
        self.updated_count = 0
        self.error_count = 0

        # Process in batches of 50
        batch_size = 50
        batches = [self.invoice_ids[i:i + batch_size]
                   for i in range(0, len(self.invoice_ids), batch_size)]

        for batch in batches:
            self._process_batch(batch)

        # Show result
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Batch Update Completed'),
                'message': _('Updated: %s, Errors: %s') % (self.updated_count, self.error_count),
                'type': 'success' if self.error_count == 0 else 'warning'
            }
        }

    def _process_batch(self, invoices):
        """Xử lý một batch hóa đơn"""
        for invoice in invoices:
            try:
                old_status = invoice.minvoice_status
                invoice._update_minvoice_status()

                # Check if status changed
                if invoice.minvoice_status != old_status:
                    self.updated_count += 1

            except Exception as e:
                self.error_count += 1
                _logger.error(f"Error updating status for invoice {invoice.name}: {str(e)}")

    def action_view_results(self):
        """Xem kết quả sau khi update"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Updated Invoices'),
            'res_model': 'account.move',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.invoice_ids.ids)],
            'context': {'create': False}
        }


class MInvoiceStatusReport(models.TransientModel):
    _name = 'minvoice.status.report'
    _description = 'M-Invoice Status Report'

    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.company)
    date_from = fields.Date('From Date', required=True,
                            default=lambda self: fields.Date.today().replace(day=1))
    date_to = fields.Date('To Date', required=True,
                          default=fields.Date.today())

    # Statistics fields
    total_invoices = fields.Integer('Total Invoices', readonly=True)
    success_count = fields.Integer('Success', readonly=True)
    pending_count = fields.Integer('Pending', readonly=True)
    error_count = fields.Integer('Error', readonly=True)
    not_sent_count = fields.Integer('Not Sent', readonly=True)

    success_percentage = fields.Float('Success Rate (%)', readonly=True)

    @api.onchange('company_id', 'date_from', 'date_to')
    def _compute_statistics(self):
        """Tính toán thống kê"""
        domain = [
            ('company_id', '=', self.company_id.id),
            ('invoice_date', '>=', self.date_from),
            ('invoice_date', '<=', self.date_to),
            ('move_type', 'in', ['out_invoice', 'out_refund'])
        ]

        all_invoices = self.env['account.move'].search(domain)
        self.total_invoices = len(all_invoices)

        if self.total_invoices > 0:
            # Count by status
            self.success_count = len(all_invoices.filtered(lambda x: x.minvoice_status == 'success'))
            self.pending_count = len(all_invoices.filtered(
                lambda x: x.minvoice_status in ['draft', 'waiting', 'signed', 'sent']))
            self.error_count = len(all_invoices.filtered(
                lambda x: x.minvoice_status in ['error', 'rejected']))
            self.not_sent_count = len(all_invoices.filtered(lambda x: not x.minvoice_id))

            # Calculate success rate
            sent_invoices = self.total_invoices - self.not_sent_count
            if sent_invoices > 0:
                self.success_percentage = (self.success_count / sent_invoices) * 100
            else:
                self.success_percentage = 0

    def action_view_invoices_by_status(self):
        """Xem hóa đơn theo trạng thái"""
        action = self.env.ref('account.action_move_out_invoice_type').read()[0]

        domain = [
            ('company_id', '=', self.company_id.id),
            ('invoice_date', '>=', self.date_from),
            ('invoice_date', '<=', self.date_to),
            ('move_type', 'in', ['out_invoice', 'out_refund'])
        ]

        # Get status from context
        status = self.env.context.get('status_filter')
        if status == 'success':
            domain.append(('minvoice_status', '=', 'success'))
        elif status == 'pending':
            domain.append(('minvoice_status', 'in', ['draft', 'waiting', 'signed', 'sent']))
        elif status == 'error':
            domain.append(('minvoice_status', 'in', ['error', 'rejected']))
        elif status == 'not_sent':
            domain.append(('minvoice_id', '=', False))

        action['domain'] = domain
        return action