# -*- coding: utf-8 -*-

from odoo import models, api


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to set partner_id on lot from purchase order"""
        lines = super().create(vals_list)
        
        for line in lines:
            # Check if we need to set vendor on lot
            if line.lot_id and line.product_id.track_vendor_by_lot:
                # Get vendor from purchase order if available
                partner_id = self._get_vendor_from_move(line.move_id)
                if partner_id and not line.lot_id.partner_id:
                    line.lot_id.partner_id = partner_id
        
        return lines

    def write(self, vals):
        """Override write to handle lot creation and splitting"""
        result = super().write(vals)
        
        # If lot_id or lot_name changed, update vendor
        if 'lot_id' in vals or 'lot_name' in vals:
            for line in self:
                if line.lot_id and line.product_id.track_vendor_by_lot:
                    # Get vendor from various sources
                    partner_id = self._get_vendor_for_lot(line)
                    if partner_id and not line.lot_id.partner_id:
                        line.lot_id.partner_id = partner_id
        
        return result

    def _get_vendor_from_move(self, move):
        """Get vendor from stock move (purchase order)"""
        if not move:
            return False
        
        # Check if move is from purchase order
        if move.purchase_line_id:
            return move.purchase_line_id.order_id.partner_id.id
        
        # Check origin move (for internal transfers)
        if move.origin_returned_move_id:
            return self._get_vendor_from_move(move.origin_returned_move_id)
        
        return False

    def _get_vendor_for_lot(self, line):
        """Get vendor for lot from various sources"""
        # Priority 1: From purchase order
        vendor_id = self._get_vendor_from_move(line.move_id)
        if vendor_id:
            return vendor_id
        
        # Priority 2: From parent lot (for split operations)
        if line.move_id and line.move_id.move_orig_ids:
            for orig_move in line.move_id.move_orig_ids:
                for orig_line in orig_move.move_line_ids:
                    if orig_line.lot_id and orig_line.lot_id.partner_id:
                        return orig_line.lot_id.partner_id.id
        
        # Priority 3: From existing lots of same product
        if line.location_id:
            existing_quant = self.env['stock.quant'].search([
                ('product_id', '=', line.product_id.id),
                ('location_id', '=', line.location_id.id),
                ('lot_id', '!=', False),
                ('lot_id.partner_id', '!=', False),
            ], limit=1)
            if existing_quant:
                return existing_quant.lot_id.partner_id.id
        
        return False

    def _action_done(self):
        """Override to ensure vendor is copied when lot is assigned"""
        result = super()._action_done()
        
        for line in self:
            if line.lot_id and line.product_id.track_vendor_by_lot and not line.lot_id.partner_id:
                partner_id = self._get_vendor_for_lot(line)
                if partner_id:
                    line.lot_id.partner_id = partner_id
        
        return result
