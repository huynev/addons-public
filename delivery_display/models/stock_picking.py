# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.http import request


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    driver_id = fields.Many2one('hr.employee', string='Driver', tracking=True)

    def action_validate_delivery_picking(self):
        """
        Safe validation method for delivery display module.
        Validates only this specific picking in isolation.
        Checks session owner for security.
        """
        self.ensure_one()

        # Security check: Only session owner can validate their deliveries
        session_owner_id = request.session.get('delivery_display_session_owner', False)
        if self.driver_id and session_owner_id:
            if self.driver_id.id != session_owner_id:
                return {
                    'success': False,
                    'message': _(
                        'You can only validate your own deliveries. Please select your name in the driver panel first.')
                }

        # Validate using _action_done() with proper user tracking
        try:
            # Get driver employee from session
            driver_employee = None
            if session_owner_id:
                driver_employee = self.env['hr.employee'].browse(session_owner_id)

            # If driver has related user account, execute validation as that user
            # This ensures chatter tracking shows driver's name instead of Administrator
            if driver_employee and driver_employee.user_id:
                # Execute validation as driver's user for proper tracking
                picking_as_driver = self.with_user(driver_employee.user_id)
                # Validate as driver user (this will track as driver in chatter)
                picking_as_driver.button_validate()
            else:
                # Use internal method to avoid UI wizards and global side effects
                self.button_validate()

                # Post message showing driver name (even without user account)
                if driver_employee:
                    self.message_post(
                        body=_("✓ Validated by driver: <b>%s</b> (no user account)") % driver_employee.name,
                        message_type='notification',
                        subtype_xmlid='mail.mt_note',
                    )
                elif self.driver_id:
                    self.message_post(
                        body=_("✓ Validated by driver: <b>%s</b>") % self.driver_id.name,
                        message_type='notification',
                        subtype_xmlid='mail.mt_note',
                    )

            return {
                'success': True,
                'message': _('Picking validated successfully')
            }

        except UserError as e:
            return {
                'success': False,
                'message': str(e)
            }
        except Exception as e:
            return {
                'success': False,
                'message': _('Validation error: %s') % str(e)
            }