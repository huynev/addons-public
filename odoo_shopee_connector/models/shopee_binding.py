# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ShopeeBinding(models.AbstractModel):
    """Abstract model for Shopee bindings"""
    _name = 'shopee.binding'
    _description = 'Shopee Binding (abstract)'

    backend_id = fields.Many2one(
        comodel_name='shopee.backend',
        string='Shopee Backend',
        required=True,
        ondelete='restrict',
    )
    external_id = fields.Char(string='External ID')
    sync_date = fields.Datetime(string='Last Sync')

    @api.model
    def import_record(self, backend, external_id):
        """Import a record from Shopee"""
        with backend.work_on(self._name) as work:
            importer = work.component(usage='record.importer')
            return importer.run(external_id)

    def export_record(self):
        """Export a record to Shopee"""
        self.ensure_one()
        # self.with_delay(channel='root.shopee').export_record_job()
        self.export_record_job()
        return True

    def export_record_job(self):
        """Job: Export a record to Shopee"""
        with self.backend_id.work_on(self._name) as work:
            exporter = work.component(usage='product.exporter')
            return exporter.run(self)

    def resync(self):
        """Resync record with Shopee"""
        self.ensure_one()
        self.with_delay(channel='root.shopee').import_record(self.backend_id, self.external_id)
        return True