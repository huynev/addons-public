from odoo import models, fields, api

class MagentoBinding(models.AbstractModel):
    """Abstract model for all Magento bindings."""
    _name = 'magento.binding'
    _description = 'Magento Binding (Abstract)'

    # Fields that binding models must have
    backend_id = fields.Many2one(
        comodel_name='magento.backend',
        string='Magento Backend',
        required=True,
        ondelete='cascade'
    )
    external_id = fields.Char(string='Magento ID')
    sync_date = fields.Datetime(string='Last Synchronization')
    active = fields.Boolean(string='Active', default=True)