# -*- coding: utf-8 -*-
from odoo import models, fields


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
