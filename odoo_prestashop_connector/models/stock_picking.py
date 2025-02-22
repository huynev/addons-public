from odoo import models, fields, api

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    prestashop_bind_ids = fields.One2many(
        'prestashop.stock.picking',
        'odoo_id',
        string='PrestaShop Bindings'
    )

    prestashop_bind_count = fields.Integer(
        string='Number of PrestaShop Bindings',
        compute='_compute_prestashop_bind_count'
    )

    @api.depends('prestashop_bind_ids')
    def _compute_prestashop_bind_count(self):
        for record in self:
            record.prestashop_bind_count = len(record.prestashop_bind_ids)

    def action_view_prestashop_bindings(self):
        self.ensure_one()
        return {
            'name': 'PrestaShop Bindings',
            'type': 'ir.actions.act_window',
            'view_mode': 'tree,form',
            'res_model': 'prestashop.stock.picking',
            'domain': [('odoo_id', '=', self.id)],
            'context': {'default_odoo_id': self.id},
        }

class PrestashopStockPicking(models.Model):
    _name = 'prestashop.stock.picking'
    _inherit = 'prestashop.binding'
    _inherits = {'stock.picking': 'odoo_id'}
    _description = 'PrestaShop Stock Picking Binding'

    odoo_id = fields.Many2one(
        'stock.picking',
        string='Stock Picking',
        required=True,
        ondelete='cascade'
    )
    prestashop_id = fields.Integer('PrestaShop ID', readonly=True)
    prestashop_order_id = fields.Many2one(
        'prestashop.sale.order',
        string='PrestaShop Sale Order'
    )
    tracking_number = fields.Char('Tracking Number')
    carrier_name = fields.Char('Carrier Name')
    date_add = fields.Datetime('Created At')
    date_upd = fields.Datetime('Updated At')

    def export_tracking_number(self):
        """Export tracking number to PrestaShop"""
        self.ensure_one()
        with self.backend_id.work_on(self._name) as work:
            exporter = work.component(usage='record.exporter')
            return exporter.run(self)