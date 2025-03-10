from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class StockMove(models.Model):
    _inherit = 'stock.move'

    @api.model
    def create(self, vals):
        move = super().create(vals)
        if move.state == 'done':
            move._woo_export_stock_if_needed()
        return move

    def write(self, vals):
        res = super().write(vals)
        if 'state' in vals and vals['state'] == 'done':
            for move in self:
                move._woo_export_stock_if_needed()
        return res

    def _woo_export_stock_if_needed(self):
        """
        Export the stock to WooCommerce if this move affected
        a product that is bound to WooCommerce
        """
        if not self.product_id:
            return

        product_template = self.product_id.product_tmpl_id
        bindings = product_template.woo_bind_ids.filtered(
            lambda b: b.backend_id.state == 'active'
        )

        for binding in bindings:
            binding.with_delay(priority=20).export_stock()