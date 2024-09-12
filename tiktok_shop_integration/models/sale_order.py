from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare, float_is_zero

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    tiktok_user_id = fields.Char(string='TikTok User ID')
    tiktok_order_id = fields.Char(string='TikTok Order ID', readonly=True)
    tiktok_status = fields.Char(string='TikTok Status', readonly=True)
    auto_transfer_picking_ids = fields.Many2many('stock.picking', string='Auto Transfer Pickings', copy=False)
    auto_transfer_count = fields.Integer(string='Auto Transfer Count', compute='_compute_auto_transfer_count')

    _sql_constraints = [
        ('tiktok_order_id_unique', 'unique(tiktok_order_id)', 'TikTok Order ID must be unique!')
    ]

    @api.constrains('tiktok_order_id')
    def _check_tiktok_order_id_unique(self):
        for record in self:
            if record.tiktok_order_id:
                duplicate = self.search([
                    ('tiktok_order_id', '=', record.tiktok_order_id),
                    ('id', '!=', record.id)
                ])
                if duplicate:
                    raise ValidationError(
                        _('TikTok Order ID must be unique. The ID %s is already used.') % record.tiktok_order_id)

    @api.depends('auto_transfer_picking_ids')
    def _compute_auto_transfer_count(self):
        for order in self:
            order.auto_transfer_count = len(order.auto_transfer_picking_ids)

    def action_view_auto_transfers(self):
        self.ensure_one()
        action = self.env.ref('stock.action_picking_tree_all').read()[0]
        action['domain'] = [('id', 'in', self.auto_transfer_picking_ids.ids)]
        action['context'] = {'default_origin': self.name}
        return action

    def action_confirm(self):
        res = super(SaleOrder, self).action_confirm()
        for order in self:
            order.check_and_create_internal_transfer()
        return res

    def check_and_create_internal_transfer(self):
        tiktok_shop = self.env['tiktok.shop'].search([], limit=1)
        if not tiktok_shop:
            return

        company_warehouse = tiktok_shop.company_warehouse_id
        tiktok_warehouse = tiktok_shop.tiktok_warehouse_id

        if self.warehouse_id == company_warehouse:
            source_warehouse = tiktok_warehouse
            dest_warehouse = company_warehouse
        elif self.warehouse_id == tiktok_warehouse:
            source_warehouse = company_warehouse
            dest_warehouse = tiktok_warehouse
        else:
            return

        moves_to_create = []
        for line in self.order_line:
            if line.product_id.type != 'product':
                continue

            available_qty = self.env['stock.quant']._get_available_quantity(
                line.product_id,
                self.warehouse_id.lot_stock_id
            )
            needed_qty = line.product_uom_qty - available_qty

            if float_compare(needed_qty, 0, precision_rounding=line.product_uom.rounding) > 0:
                source_available_qty = self.env['stock.quant']._get_available_quantity(
                    line.product_id,
                    source_warehouse.lot_stock_id
                )
                transfer_qty = min(needed_qty, source_available_qty)

                if float_compare(transfer_qty, 0, precision_rounding=line.product_uom.rounding) > 0:
                    moves_to_create.append({
                        'name': f'Auto transfer for {self.name}',
                        'product_id': line.product_id.id,
                        'product_uom_qty': transfer_qty,
                        'product_uom': line.product_uom.id,
                        'location_id': source_warehouse.lot_stock_id.id,
                        'location_dest_id': dest_warehouse.lot_stock_id.id,
                    })

        if moves_to_create:
            picking_type = self.env['stock.picking.type'].search([
                ('code', '=', 'internal'),
                ('default_location_src_id', '=', source_warehouse.lot_stock_id.id),
                ('default_location_dest_id', '=', dest_warehouse.lot_stock_id.id)
            ], limit=1)

            if not picking_type:
                tiktok_shop._ensure_internal_picking_types()
                picking_type = self.env['stock.picking.type'].search([
                    ('code', '=', 'internal'),
                    ('default_location_src_id', '=', source_warehouse.lot_stock_id.id),
                    ('default_location_dest_id', '=', dest_warehouse.lot_stock_id.id)
                ], limit=1)

            if not picking_type:
                raise UserError(_("No appropriate picking type found for transfer between warehouses."))

            picking = self.env['stock.picking'].create({
                'picking_type_id': picking_type.id,
                'location_id': source_warehouse.lot_stock_id.id,
                'location_dest_id': dest_warehouse.lot_stock_id.id,
                'origin': self.name,
            })

            # Liên kết picking với đơn hàng
            self.write({'auto_transfer_picking_ids': [(4, picking.id)]})

            for move in moves_to_create:
                move['picking_id'] = picking.id

            self.env['stock.move'].create(moves_to_create)
            picking.action_confirm()
            picking.action_assign()

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    tiktok_order_line_id = fields.Char(string='TikTok Order Line ID', readonly=True)