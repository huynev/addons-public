from odoo import models, fields, api

class PrestashopImportProducts(models.TransientModel):
    _name = 'prestashop.import.products'
    _description = 'Import Products from PrestaShop'

    backend_id = fields.Many2one(
        'prestashop.backend',
        'PrestaShop Backend',
        required=True
    )
    from_date = fields.Datetime('From Date')

    def import_products(self):
        self.ensure_one()
        backend = self.backend_id
        from_date = self.from_date

        with backend.work_on('prestashop.product.template') as work:
            importer = work.component(usage='batch.importer')
            filters = {'date': from_date} if from_date else None
            importer.run(filters=filters)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Success',
                'message': 'Product import started. Check the queue jobs.',
                'type': 'success',
            }
        }