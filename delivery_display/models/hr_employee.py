# -*- coding: utf-8 -*-
from odoo import models, fields, _
from odoo.http import request

# Session constants
SESSION_OWNER = 'delivery_display_session_owner'
EMPLOYEES_CONNECTED = 'delivery_display_employees_connected'


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    is_driver = fields.Boolean(
        string='Is Driver',
        default=False,
        help='Check this if this employee is a delivery driver'
    )

    driver_pin = fields.Char(
        string='Driver PIN',
        size=10,
        help='PIN code for driver authentication (used for delivery assignment)'
    )

    # Override barcode để dùng cho driver identification
    # hr.employee đã có sẵn field barcode

    def pin_validation(self, pin):
        """Validate driver PIN"""
        self.ensure_one()
        if not self.driver_pin:
            return False
        return str(self.driver_pin) == str(pin)

    def login(self, pin=False, set_in_session=True):
        """Login driver to session"""
        self.ensure_one()
        if self.pin_validation(pin) and set_in_session:
            self._connect_employee()
            request.session[SESSION_OWNER] = self.id
            return True
        return False

    def logout(self, pin=False, unchecked=False):
        """Logout driver from session"""
        self.ensure_one()
        employees = request.session.get(EMPLOYEES_CONNECTED, [])
        owner = request.session.get(SESSION_OWNER, False)

        if (self.pin_validation(pin) or unchecked) and self.id in employees:
            request.session[SESSION_OWNER] = self.id
            employees.remove(self.id)
            request.session[EMPLOYEES_CONNECTED] = employees

            if owner == self.id:
                owner = False
            request.session[SESSION_OWNER] = owner
            return True
        return False

    def _connect_employee(self):
        """Add employee to connected list"""
        self.ensure_one()
        employees = request.session.get(EMPLOYEES_CONNECTED, [])
        if self.id not in employees:
            employees.append(self.id)
            request.session[EMPLOYEES_CONNECTED] = employees

    def remove_session_owner(self):
        """Remove session owner"""
        self.ensure_one()
        if self.id == request.session.get(SESSION_OWNER):
            request.session[SESSION_OWNER] = False

    def is_session_owner(self):
        """Check if current employee is session owner"""
        self.ensure_one()
        return self.id == request.session.get(SESSION_OWNER, False)