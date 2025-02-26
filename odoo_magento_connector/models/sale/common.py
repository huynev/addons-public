from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class MagentoSaleOrder(models.Model):
    _name = 'magento.sale.order'
    _description = 'Magento Sale Order'
    _inherit = 'magento.binding'
    _inherits = {'sale.order': 'odoo_id'}

    odoo_id = fields.Many2one(
        'sale.order',
        string='Sale Order',
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
    magento_increment_id = fields.Char(string='Magento Increment ID', help='The Magento order number')
    store_id = fields.Many2one(
        'magento.store',
        string='Magento Store'
    )
    storeview_id = fields.Many2one(
        'magento.storeview',
        string='Magento Store View'
    )
    website_id = fields.Many2one(
        'magento.website',
        related='store_id.website_id',
        string='Magento Website',
        store=True,
        readonly=True
    )
    sync_date = fields.Datetime(string='Last Synchronization')
    magento_order_line_ids = fields.One2many(
        'magento.sale.order.line',
        'magento_order_id',
        string='Magento Order Lines'
    )

    _sql_constraints = [
        ('magento_uniq', 'unique(backend_id, external_id)',
         'A sale order with the same Magento ID already exists.'),
        ('magento_increment_id_uniq', 'unique(backend_id, magento_increment_id)',
         'A sale order with the same Magento increment ID already exists.')
    ]


class MagentoSaleOrderLine(models.Model):
    _name = 'magento.sale.order.line'
    _description = 'Magento Sale Order Line'
    _inherit = 'magento.binding'
    _inherits = {'sale.order.line': 'odoo_id'}

    odoo_id = fields.Many2one(
        'sale.order.line',
        string='Sale Order Line',
        required=True,
        ondelete='cascade'
    )
    backend_id = fields.Many2one(
        'magento.backend',
        related='magento_order_id.backend_id',
        string='Magento Backend',
        store=True,
        readonly=True
    )
    external_id = fields.Char(string='Magento ID')
    magento_order_id = fields.Many2one(
        'magento.sale.order',
        string='Magento Sale Order',
        required=True,
        ondelete='cascade'
    )
    sync_date = fields.Datetime(string='Last Synchronization')

    _sql_constraints = [
        ('magento_uniq', 'unique(backend_id, external_id)',
         'A sale order line with the same Magento ID already exists.')
    ]


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    magento_bind_ids = fields.One2many(
        'magento.sale.order',
        'odoo_id',
        string='Magento Bindings'
    )

    def export_to_magento(self):
        """Export order to Magento"""
        for order in self:
            for binding in order.magento_bind_ids:
                binding.with_delay(
                    channel='root.magento.sale'
                ).export_record()
        return True


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    magento_bind_ids = fields.One2many(
        'magento.sale.order.line',
        'odoo_id',
        string='Magento Bindings'
    )