# -*- coding: utf-8 -*-
from odoo import models, fields, api


class AddDriverWizard(models.TransientModel):
    _name = 'delivery.display.add.driver.wizard'
    _description = 'Add Drivers Wizard'

    employee_ids = fields.Many2many(
        'hr.employee',
        string='Select Employees to Add as Drivers',
        domain=[('active', '=', True), ('is_driver', '=', False)]
    )

    def action_add_drivers(self):
        """Set selected employees as drivers"""
        if self.employee_ids:
            self.employee_ids.write({'is_driver': True})
        return {'type': 'ir.actions.act_window_close'}
