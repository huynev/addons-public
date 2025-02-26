from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)


class MagentoResPartner(models.Model):
    _name = 'magento.res.partner'
    _description = 'Magento Customer'
    _inherit = 'magento.binding'
    _inherits = {'res.partner': 'odoo_id'}

    odoo_id = fields.Many2one(
        'res.partner',
        string='Partner',
        required=True,
        ondelete='cascade'
    )
    backend_id = fields.Many2one(
        'magento.backend',
        string='Magento Backend',
        required=True,
        ondelete='cascade'
    )
    external_id = fields.Char(string='Magento ID')
    sync_date = fields.Datetime(string='Last Synchronization')

    _sql_constraints = [
        ('magento_uniq', 'unique(backend_id, external_id)',
         'A partner with the same Magento ID already exists.'),
    ]


class ResPartner(models.Model):
    _inherit = 'res.partner'

    magento_bind_ids = fields.One2many(
        'magento.res.partner',
        'odoo_id',
        string='Magento Bindings'
    )

    def export_to_magento(self):
        """Export partner to Magento"""
        for partner in self:
            for binding in partner.magento_bind_ids:
                binding.with_delay(
                    channel='root.magento.partner'
                ).export_record()
        return True