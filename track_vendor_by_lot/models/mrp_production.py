# -*- coding: utf-8 -*-

from odoo import models, api


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    def _cal_price(self, consumed_moves):
        """Override to copy vendor from consumed material lots to finished product lots"""
        result = super()._cal_price(consumed_moves)
        self._copy_vendor_to_finished_lots(consumed_moves)
        return result

    def _copy_vendor_to_finished_lots(self, consumed_moves):
        """Copy vendor from consumed material lots to finished and byproduct lots"""
        for production in self:
            # Get vendors from consumed raw materials
            vendor_ids = self._get_vendors_from_consumed_moves(consumed_moves)
            
            if not vendor_ids:
                continue
            
            # Use the first vendor found (or implement your own logic)
            main_vendor_id = vendor_ids[0]
            
            # Copy to finished product lots
            self._set_vendor_on_lots(
                production.move_finished_ids.move_line_ids.lot_id,
                main_vendor_id
            )
            
            # Copy to byproduct lots
            byproduct_moves = production.move_finished_ids.filtered(
                lambda m: m.product_id != production.product_id
            )
            self._set_vendor_on_lots(
                byproduct_moves.move_line_ids.lot_id,
                main_vendor_id
            )

    def _get_vendors_from_consumed_moves(self, consumed_moves):
        """Get vendor IDs from consumed material lots"""
        vendor_ids = []
        
        for move in consumed_moves:
            if not move.product_id.track_vendor_by_lot:
                continue
            
            for move_line in move.move_line_ids:
                if move_line.lot_id and move_line.lot_id.partner_id:
                    if move_line.lot_id.partner_id.id not in vendor_ids:
                        vendor_ids.append(move_line.lot_id.partner_id.id)
        
        return vendor_ids

    def _set_vendor_on_lots(self, lots, vendor_id):
        """Set vendor on lots if product tracks vendor by lot"""
        for lot in lots:
            if not lot:
                continue
            
            # Only set if product tracks vendor by lot and lot doesn't have vendor yet
            if lot.product_id.track_vendor_by_lot and not lot.partner_id:
                lot.partner_id = vendor_id

    def button_mark_done(self):
        """Override to ensure vendors are copied when production is completed"""
        result = super().button_mark_done()
        
        for production in self:
            # Get all consumed moves
            consumed_moves = production.move_raw_ids.filtered(lambda m: m.state == 'done')
            
            # Copy vendors to finished and byproduct lots
            self._copy_vendor_to_finished_lots(consumed_moves)
        
        return result

    def _post_inventory(self, cancel_backorder=False):
        """Override to handle vendor copying during production completion"""
        result = super()._post_inventory(cancel_backorder=cancel_backorder)
        
        for production in self:
            # Get vendors from consumed materials
            consumed_moves = production.move_raw_ids.filtered(lambda m: m.state == 'done')
            vendor_ids = self._get_vendors_from_consumed_moves(consumed_moves)
            
            if vendor_ids:
                main_vendor_id = vendor_ids[0]
                
                # Set vendor on finished product lots
                for move in production.move_finished_ids:
                    if move.product_id.track_vendor_by_lot:
                        for move_line in move.move_line_ids:
                            if move_line.lot_id and not move_line.lot_id.partner_id:
                                move_line.lot_id.partner_id = main_vendor_id
        
        return result



