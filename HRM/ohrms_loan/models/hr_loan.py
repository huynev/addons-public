# -*- coding: utf-8 -*-
#############################################################################
#    A part of Open HRMS Project <https://www.openhrms.com>
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2023-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
#    Author: Cybrosys Techno Solutions(<https://www.cybrosys.com>)
#
#    You can modify it under the terms of the GNU LESSER
#    GENERAL PUBLIC LICENSE (LGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU LESSER GENERAL PUBLIC LICENSE (LGPL v3) for more details.
#
#    You should have received a copy of the GNU LESSER GENERAL PUBLIC LICENSE
#    (LGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
#############################################################################
from datetime import datetime
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class HrLoan(models.Model):
    """ Model for managing loan requests."""
    _name = 'hr.loan'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Loan Request"

    @api.model
    def default_get(self, field_list):
        """ Function used to pass employee corresponding to current login user
            as default employee while creating new loan request
            :param field_list : Fields and values for the model hr.loan"""
        result = super(HrLoan, self).default_get(field_list)
        if result.get('user_id'):
            user_id = result['user_id']
        else:
            user_id = self.env.context.get('user_id', self.env.user.id)
        result['employee_id'] = self.env['hr.employee'].search(
            [('user_id', '=', user_id)], limit=1).id
        return result

    name = fields.Char(string="Loan Name", default="New", readonly=True,
                       help="Name of the loan")
    date = fields.Date(string="Date", default=fields.Date.today(),
                       readonly=True, help="Date of the loan request")
    employee_id = fields.Many2one('hr.employee', string="Employee",
                                  required=True, help="Employee Name")
    department_id = fields.Many2one('hr.department',
                                    related="employee_id.department_id",
                                    readonly=True,
                                    string="Department",
                                    help="The department to which the "
                                         "employee belongs.")
    installment = fields.Integer(string="No Of Installments", default=1,
                                 help="Number of installments")
    payment_date = fields.Date(string="Payment Start Date", required=True,
                               default=fields.Date.today(),
                               help="Date of the payment")
    loan_lines = fields.One2many('hr.loan.line', 'loan_id',
                                 string="Loan Line",
                                 help="Details of installment lines "
                                      "associated with the loan.",
                                 index=True)
    company_id = fields.Many2one('res.company', string='Company',
                                 help="Company",
                                 default=lambda self: self.env.user.company_id)
    currency_id = fields.Many2one('res.currency', string='Currency',
                                  required=True, help="Currency",
                                  default=lambda self: self.env.user.
                                  company_id.currency_id)
    job_position = fields.Many2one('hr.job',
                                   related="employee_id.job_id",
                                   readonly=True, string="Job Position",
                                   help="Job position of the employee")
    loan_amount = fields.Float(string="Loan Amount", required=True,
                               help="Loan amount")
    total_amount = fields.Float(string="Total Amount", store=True,
                                readonly=True, compute='_compute_total_amount',
                                help="The total amount of the loan")
    balance_amount = fields.Float(string="Balance Amount", store=True,
                                  compute='_compute_total_amount',
                                  help="""The remaining balance amount of the 
                                  loan after deducting 
                                  the total paid amount.""")
    total_paid_amount = fields.Float(string="Total Paid Amount", store=True,
                                     compute='_compute_total_amount',
                                     help="The total amount that has been "
                                          "paid towards the loan.")
    state = fields.Selection(
        [('draft', 'Draft'), ('waiting_approval_1', 'Submitted'),
         ('approve', 'Approved'), ('refuse', 'Refused'), ('cancel', 'Canceled'),
         ], string="State", default='draft', help="The current state of the "
                                                  "loan request.", copy=False)

    # Batch fields
    batch_id = fields.Many2one('hr.loan.batch', string="Đợt ứng lương", required=True,
                               help="Đợt ứng lương mà khoản ứng này thuộc về")

    # Auto generation fields (moved from extension)
    is_auto_generated = fields.Boolean(string="Auto Generated", default=False, readonly=True,
                                       help="Whether this loan was automatically generated")
    auto_config_id = fields.Many2one('hr.loan.auto.config', string="Auto Configuration",
                                     readonly=True,
                                     help="Configuration that generated this loan")
    auto_log_id = fields.Many2one('hr.loan.auto.log', string="Generation Log",
                                  readonly=True,
                                  help="Log entry of the automatic generation")

    def _compute_total_amount(self):
        """ Compute total loan amount,balance amount and total paid amount"""
        total_paid = 0.0
        for loan in self:
            for line in loan.loan_lines:
                if line.paid:
                    total_paid += line.amount
            balance_amount = loan.loan_amount - total_paid
            loan.total_amount = loan.loan_amount
            loan.balance_amount = balance_amount
            loan.total_paid_amount = total_paid

    @api.model
    def create(self, values):
        """ Check whether any pending loan is for the employee and calculate
            the sequence
            :param values : Dictionary which contain fields and values"""
        loan_count = self.env['hr.loan'].search_count(
            [('employee_id', '=', values['employee_id']),
             ('batch_id', '=', values['batch_id']),
             ('balance_amount', '!=', 0)])
        if loan_count:
            raise ValidationError(
                _("The Employee has already a pending installment"))
        else:
            values['name'] = self.env['ir.sequence'].get('hr.loan.seq') or ' '

            # Auto assign to current month batch if not specified and not auto-generated
            values['batch_id'] = self._get_or_create_current_batch(values.get('batch_id'))

            return super(HrLoan, self).create(values)

    def _get_or_create_current_batch(self, batch_id=None):
        """Lấy hoặc tạo đợt cho tháng hiện tại"""
        today = fields.Date.today()
        company_id = self.env.user.company_id.id

        # Tìm đợt đang mở (draft hoặc confirmed) cho tháng hiện tại
        batch = self.env['hr.loan.batch'].browse(batch_id) if batch_id else self.env['hr.loan.batch'].search([
            ('month', '=', today.month),
            ('year', '=', today.year),
            ('company_id', '=', company_id),
            ('state', 'in', ['draft', 'confirmed'])
        ], limit=1, order='sequence desc')

        if not batch:
            # Tạo đợt mới nếu chưa có
            batch = self.env['hr.loan.batch'].create_batch_for_current_month(None, None, company_id)

        return batch.id

    @api.onchange('batch_id')
    def _onchange_batch_id(self):
        """Cập nhật payment_date theo batch nếu có"""
        if self.batch_id and not self.payment_date:
            # Đặt payment_date là ngày đầu tháng của batch
            first_day = datetime(self.batch_id.year, self.batch_id.month, 1).date()
            self.payment_date = first_day

    def action_compute_installment(self):
        """This automatically create the installment the employee need to pay to
            company based on payment start date and the no of installments.
            """
        for loan in self:
            loan.loan_lines.unlink()
            date_start = datetime.strptime(str(loan.payment_date), '%Y-%m-%d')
            amount = loan.loan_amount / loan.installment
            for i in range(1, loan.installment + 1):
                self.env['hr.loan.line'].create({
                    'date': date_start,
                    'amount': amount,
                    'employee_id': loan.employee_id.id,
                    'loan_id': loan.id})
                date_start = date_start + relativedelta(months=1)
            loan._compute_total_amount()
        return True

    def action_refuse(self):
        """ Function to reject loan request"""
        return self.write({'state': 'refuse'})

    def action_submit(self):
        """ Function to submit loan request"""
        self.write({'state': 'waiting_approval_1'})

    def action_cancel(self):
        """ Function to cancel loan request"""
        self.write({'state': 'cancel'})

    def action_draft(self):
        """ Function to cancel loan request"""
        self.write({'state': 'draft'})

    def action_approve(self):
        """ Function to approve loan request"""
        for data in self:
            if not data.loan_lines:
                raise ValidationError(_("Please Compute installment"))
            else:
                self.write({'state': 'approve'})

    def unlink(self):
        """ Function which restrict the deletion of approved or submitted
                loan request"""
        for loan in self:
            if loan.state not in ('draft', 'cancel', 'refuse', 'waiting_approval_1'):
                raise UserError(_(
                    'You cannot delete a loan which is not in draft '
                    'or cancelled or refuse or waiting_approval_1 state'))
        return super(HrLoan, self).unlink()

    def action_batch_submit(self):
        """ Function to submit multiple loan requests at once"""
        submitted_count = 0
        approved_count = 0
        skipped_count = 0

        for record in self:
            if record.state == 'approve':
                approved_count += 1
            elif record.state == 'draft':
                record.write({'state': 'waiting_approval_1'})
                submitted_count += 1
            else:
                skipped_count += 1

        messages = []
        if submitted_count > 0:
            messages.append(_("%d loan(s) submitted successfully.") % submitted_count)
        if approved_count > 0:
            messages.append(_("%d approved loan(s) cannot be changed.") % approved_count)
        if skipped_count > 0:
            messages.append(_("%d loan(s) skipped (invalid state).") % skipped_count)

        message = " ".join(messages) if messages else _('No valid loans to submit.')
        message_type = 'success' if submitted_count > 0 else 'warning'

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Batch Submit Result'),
                'message': message,
                'type': message_type,
                'sticky': False,
            }
        }

    def action_batch_approve(self):
        """ Function to approve multiple loan requests at once"""
        approved_count = 0
        already_approved_count = 0
        skipped_count = 0
        missing_installments = []

        for record in self:
            if record.state == 'approve':
                already_approved_count += 1
            elif record.state == 'waiting_approval_1':
                if not record.loan_lines:
                    missing_installments.append(record.name)
                else:
                    record.write({'state': 'approve'})
                    approved_count += 1
            else:
                skipped_count += 1

        # Raise error if there are loans without installments
        if missing_installments:
            loan_names = ', '.join(missing_installments)
            raise ValidationError(_("Please compute installments for the following loans first: %s") % loan_names)

        messages = []
        if approved_count > 0:
            messages.append(_("%d loan(s) approved successfully.") % approved_count)
        if already_approved_count > 0:
            messages.append(_("%d loan(s) already approved.") % already_approved_count)
        if skipped_count > 0:
            messages.append(_("%d loan(s) skipped (invalid state).") % skipped_count)

        message = " ".join(messages) if messages else _('No valid loans to approve.')
        message_type = 'success' if approved_count > 0 else 'warning'

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Batch Approve Result'),
                'message': message,
                'type': message_type,
                'sticky': False,
            }
        }

    def action_batch_refuse(self):
        """ Function to refuse multiple loan requests at once"""
        refused_count = 0
        approved_count = 0
        skipped_count = 0

        for record in self:
            if record.state == 'approve':
                approved_count += 1
            elif record.state in ['draft', 'waiting_approval_1']:
                record.write({'state': 'refuse'})
                refused_count += 1
            else:
                skipped_count += 1

        messages = []
        if refused_count > 0:
            messages.append(_("%d loan(s) refused successfully.") % refused_count)
        if approved_count > 0:
            messages.append(_("%d approved loan(s) cannot be refused.") % approved_count)
        if skipped_count > 0:
            messages.append(_("%d loan(s) skipped (invalid state).") % skipped_count)

        message = " ".join(messages) if messages else _('No valid loans to refuse.')
        message_type = 'success' if refused_count > 0 else 'warning'

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Batch Refuse Result'),
                'message': message,
                'type': message_type,
                'sticky': False,
            }
        }

    def action_batch_cancel(self):
        """ Function to cancel multiple loan requests at once"""
        cancelled_count = 0
        approved_count = 0
        skipped_count = 0

        for record in self:
            if record.state == 'approve':
                approved_count += 1
            elif record.state == 'draft':
                record.write({'state': 'cancel'})
                cancelled_count += 1
            else:
                skipped_count += 1

        messages = []
        if cancelled_count > 0:
            messages.append(_("%d loan(s) cancelled successfully.") % cancelled_count)
        if approved_count > 0:
            messages.append(_("%d approved loan(s) cannot be cancelled.") % approved_count)
        if skipped_count > 0:
            messages.append(_("%d loan(s) skipped (invalid state).") % skipped_count)

        message = " ".join(messages) if messages else _('No valid loans to cancel.')
        message_type = 'success' if cancelled_count > 0 else 'warning'

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Batch Cancel Result'),
                'message': message,
                'type': message_type,
                'sticky': False,
            }
        }

    def action_batch_reset_to_draft(self):
        """ Function to reset multiple loan requests to draft state"""
        reset_count = 0
        approved_count = 0
        skipped_count = 0

        for record in self:
            if record.state == 'approve':
                approved_count += 1
            elif record.state in ['refuse', 'cancel']:
                record.write({'state': 'draft'})
                reset_count += 1
            else:
                skipped_count += 1

        messages = []
        if reset_count > 0:
            messages.append(_("%d loan(s) reset to draft successfully.") % reset_count)
        if approved_count > 0:
            messages.append(_("%d approved loan(s) cannot be reset.") % approved_count)
        if skipped_count > 0:
            messages.append(_("%d loan(s) skipped (invalid state).") % skipped_count)

        message = " ".join(messages) if messages else _('No valid loans to reset to draft.')
        message_type = 'success' if reset_count > 0 else 'warning'

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Batch Reset Result'),
                'message': message,
                'type': message_type,
                'sticky': False,
            }
        }


class HrLoanLine(models.Model):
    """ Model for managing details of loan request installments"""
    _name = "hr.loan.line"
    _description = "Installment Line"

    date = fields.Date(string="Payment Date", required=True,
                       help="Date of the payment")
    employee_id = fields.Many2one('hr.employee', string="Employee",
                                  help="Employee")
    amount = fields.Float(string="Amount", required=True, help="Amount")
    paid = fields.Boolean(string="Paid", help="Indicates whether the "
                                              "installment has been paid.")
    loan_id = fields.Many2one('hr.loan', string="Loan Ref.",
                              help="Reference to the associated loan.")
    payslip_id = fields.Many2one('hr.payslip', string="Payslip Ref.",
                                 help="Reference to the associated "
                                      "payslip, if any.")