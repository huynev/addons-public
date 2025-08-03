# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class HrLoanAutoGenerationWizard(models.TransientModel):
    """Wizard for manual triggering of automatic loan generation"""
    _name = 'hr.loan.auto.generation.wizard'
    _description = "Generate Automatic Loans Wizard"

    config_id = fields.Many2one('hr.loan.auto.config', string="Configuration",
                                required=True, readonly=True)

    def generate_loans(self):
        """Manually trigger loan generation for the selected configuration"""
        self.ensure_one()

        # Call the auto generation functionality for this specific config
        auto_gen = self.env['hr.loan.auto.generation']
        today = fields.Date.today()

        log_vals = {
            'config_id': self.config_id.id,
            'execution_date': fields.Datetime.now(),
            'loan_count': 0,
            'state': 'success',
            'note': 'Manual execution',
        }

        created_loans = 0
        error_notes = ['Manual execution triggered by user.']

        # Get active employee lines from this config
        employee_lines = self.env['hr.loan.auto.employee.line'].search([
            ('config_id', '=', self.config_id.id),
            ('active', '=', True)
        ])

        batch = self.env['hr.loan.batch'].search([
            ('month', '=', today.month),
            ('year', '=', today.year),
            ('execution_day', '=', self.config_id.execution_day),
            ('state', 'in', ['draft', 'confirmed'])
        ], limit=1, order='sequence desc')

        if not batch:
            batch = self.env['hr.loan.batch'].create_batch_for_current_month(self.config_id.id, self.config_id.execution_day)
            print(f"{batch}")

        for line in employee_lines:
            employee = line.employee_id

            # Check if employee already has a pending loan
            existing_loan = self.env['hr.loan'].search_count([
                ('employee_id', '=', employee.id),
                ('state', 'in', ['approve', 'waiting_approval_1']),
                ('balance_amount', '!=', 0),
                ('auto_config_id', '=', self.config_id.id),
                ('batch_id', '=', batch.id),
            ])

            if existing_loan:
                error_notes.append(
                    f"Employee {employee.name} already has a pending loan. Skipped.")
                continue

            # Create the loan
            try:
                loan_vals = {
                    'employee_id': employee.id,
                    'loan_amount': line.loan_amount,
                    'installment': self.config_id.installment,
                    'payment_date': today,
                    'is_auto_generated': True,
                    'auto_config_id': self.config_id.id,
                    'batch_id': batch.id,
                    'state': 'draft',
                }

                loan = self.env['hr.loan'].create(loan_vals)

                # Compute installments
                loan.action_compute_installment()

                # Submit for approval
                loan.action_submit()

                created_loans += 1

            except Exception as e:
                error_notes.append(
                    f"Failed to create loan for {employee.name}: {str(e)}")

        # Update log
        log_vals['loan_count'] = created_loans
        if len(error_notes) > 1:  # More than just the manual execution note
            log_vals['note'] = '\n'.join(error_notes)
            if created_loans == 0:
                log_vals['state'] = 'failed'
            else:
                log_vals['state'] = 'partial'
        else:
            log_vals['note'] = f"Successfully created {created_loans} loans. (Manual execution)"

        # Create the log entry
        log = self.env['hr.loan.auto.log'].create(log_vals)

        # Update created loans with log reference
        if created_loans > 0:
            loans = self.env['hr.loan'].search([
                ('is_auto_generated', '=', True),
                ('auto_config_id', '=', self.config_id.id),
                ('auto_log_id', '=', False)
            ])
            loans.write({'auto_log_id': log.id})

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Loan Generation'),
                'message': _('%s loans have been created.') % created_loans,
                'sticky': False,
                'next': {
                    'type': 'ir.actions.act_window_close',
                }
            }
        }