# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ShopeeSaleOrder(models.Model):
    _name = 'shopee.sale.order'
    _description = 'Shopee Sale Order'
    _inherit = 'shopee.binding'

    odoo_id = fields.Many2one(
        comodel_name='sale.order',
        string='Sale Order',
        required=True,
        ondelete='cascade',
    )
    shopee_order_sn = fields.Char('Order SN')
    shopee_order_status = fields.Char('Order Status')
    shopee_order_date = fields.Datetime('Order Date')
    shopee_payment_method = fields.Char('Payment Method')
    shopee_shipping_carrier = fields.Char('Shipping Carrier')
    shopee_tracking_number = fields.Char('Tracking Number')
    order_line = fields.One2many(
        comodel_name='shopee.sale.order.line',
        inverse_name='shopee_order_id',
        string='Order Lines',
    )

    def export_tracking(self):
        """Export tracking to Shopee"""
        self.ensure_one()
        self.with_delay(channel='root.shopee').export_tracking_job()
        return True

    def export_tracking_job(self):
        """Job: Export tracking to Shopee"""
        with self.backend_id.work_on(self._name) as work:
            exporter = work.component(usage='tracking.exporter')
            return exporter.run(self)

    @api.model
    def import_batch(self, backend, since_date=None):
        """Import batch from Shopee"""
        with backend.work_on(self._name) as work:
            importer = work.component(usage='sale.batch.importer')
            return importer.run(since_date=since_date)

    def import_record(self, backend, external_id):
        """Import a record from Shopee"""
        with backend.work_on(self._name) as work:
            importer = work.component(usage='sale.importer')
            return importer.run(external_id)


class ShopeeSaleOrderLine(models.Model):
    _name = 'shopee.sale.order.line'
    _description = 'Shopee Sale Order Line'
    _inherit = 'shopee.binding'

    odoo_id = fields.Many2one(
        comodel_name='sale.order.line',
        string='Sale Order Line',
        required=True,
        ondelete='cascade',
    )
    shopee_order_id = fields.Many2one(
        comodel_name='shopee.sale.order',
        string='Shopee Order',
        required=True,
        ondelete='cascade',
    )
    shopee_item_id = fields.Char('Item ID')
    shopee_item_name = fields.Char('Item Name')
    shopee_item_sku = fields.Char('Item SKU')
    shopee_item_price = fields.Float('Item Price')
    shopee_item_quantity = fields.Float('Item Quantity')

    def import_record(self, backend, external_id):
        """Import a record from Shopee"""
        with backend.work_on(self._name) as work:
            importer = work.component(usage='sale.line.importer')
            return importer.run(external_id)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    shopee_bind_ids = fields.One2many(
        'shopee.sale.order',
        'odoo_id',
        string='Shopee Bindings'
    )


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    shopee_bind_ids = fields.One2many(
        'shopee.sale.order.line',
        'odoo_id',
        string='Shopee Bindings'
    )