# -*- coding: utf-8 -*-
from odoo import models, fields, api


class AddDriverWizard(models.TransientModel):
    _name = 'delivery.display.add.driver.wizard'
    _description = 'Add Drivers Wizard'

    partner_ids = fields.Many2many(
        'res.partner',
        string='Select Partners to Add as Drivers',
        domain=[('active', '=', True), ('is_company', '=', False), ('is_driver', '=', False)]
    )

    def action_add_drivers(self):
        """Set selected partners as drivers"""
        if self.partner_ids:
            self.partner_ids.write({'is_driver': True})
        return {'type': 'ir.actions.act_window_close'}
