from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class MagentoStoreview(models.Model):
    _name = 'magento.storeview'
    _description = 'Magento Store View'

    name = fields.Char(string='Name', required=True)
    code = fields.Char(string='Code', required=True)
    external_id = fields.Char(string='Magento ID', required=True)
    store_id = fields.Many2one(
        'magento.store',
        string='Magento Store',
        required=True,
        ondelete='cascade'
    )
    website_id = fields.Many2one(
        'magento.website',
        string='Magento Website',
        related='store_id.website_id',
        store=True,
        readonly=True
    )
    backend_id = fields.Many2one(
        'magento.backend',
        string='Magento Backend',
        related='store_id.backend_id',
        store=True,
        readonly=True
    )
    lang_id = fields.Many2one(
        'res.lang',
        string='Language',
        help='Language for this storeview'
    )
    active = fields.Boolean(
        string='Active',
        default=True
    )

    _sql_constraints = [
        ('magento_uniq', 'unique(store_id, external_id)',
         'A storeview with the same Magento ID already exists for this store.'),
    ]