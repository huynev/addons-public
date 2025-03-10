from odoo import models, fields, api


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    woo_auto_export_product_changes = fields.Boolean(
        string='Automatically Export Product Changes',
        help='Export product changes to WooCommerce automatically',
        default=True,
    )

    @api.model
    def get_values(self):
        res = super().get_values()

        params = self.env['ir.config_parameter'].sudo()
        res.update(woo_auto_export_product_changes=params.get_param('woo_connector.auto_export_product_changes',
                                                                    'True') == 'True')

        return res

    def set_values(self):
        super().set_values()

        params = self.env['ir.config_parameter'].sudo()
        params.set_param('woo_connector.auto_export_product_changes', str(self.woo_auto_export_product_changes))
