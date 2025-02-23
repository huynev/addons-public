import xml.etree.ElementTree as ET

from odoo import models, fields

from odoo import models, fields, api


class ResPartner(models.Model):
    _inherit = 'res.partner'

    prestashop_bind_ids = fields.One2many(
        'prestashop.res.partner',
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
            'res_model': 'prestashop.res.partner',
            'domain': [('odoo_id', '=', self.id)],
            'context': {'default_odoo_id': self.id},
        }

class PrestashopResPartner(models.Model):
    _name = 'prestashop.res.partner'
    _inherit = 'prestashop.binding'
    _inherits = {'res.partner': 'odoo_id'}
    _description = 'PrestaShop Partner Binding'

    odoo_id = fields.Many2one(
        'res.partner',
        string='Partner',
        required=True,
        ondelete='cascade'
    )
    property_product_pricelist = fields.Many2one(
        'product.pricelist',
        string='Pricelist',
        related='odoo_id.property_product_pricelist',
        store=True,
        readonly=True
    )
    prestashop_id = fields.Integer('PrestaShop ID')
    shop_id = fields.Many2one(
        'prestashop.shop',
        'PrestaShop Shop',
        required=True,
    )
    prestashop_email = fields.Char('PrestaShop Email')
    prestashop_default_group = fields.Char('PrestaShop Default Group')
    date_add = fields.Datetime('Created At')
    date_upd = fields.Datetime('Updated At')

    def action_sync_customer_details(self):
        """
        Đồng bộ thông tin chi tiết khách hàng từ PrestaShop
        """
        for record in self:
            try:
                if not record.backend_id:
                    raise ValueError("Không tìm thấy backend PrestaShop")

                prestashop = record.backend_id._get_prestashop_client()
                try:
                    customer_details = prestashop.get('customers', record.prestashop_id)
                except Exception as e:
                    raise ValueError(f"Lỗi lấy thông tin khách hàng: {str(e)}")

                # Cập nhật thông tin khách hàng Odoo
                partner = record.odoo_id
                partner_vals = self._prepare_partner_vals(customer_details)
                partner.write(partner_vals)

                # Cập nhật thông tin liên kết PrestaShop
                record_vals = self._prepare_prestashop_partner_vals(customer_details)
                record.write(record_vals)

                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Đồng Bộ Thành Công',
                        'message': f'Đã cập nhật thông tin khách hàng {partner.name}',
                        'type': 'success',
                        'sticky': False,
                    }
                }

            except Exception as e:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Lỗi Đồng Bộ',
                        'message': str(e),
                        'type': 'danger',
                        'sticky': True,
                    }
                }

    def _prepare_partner_vals(self, prestashop_elem):
        """
        Chuẩn bị giá trị cập nhật cho đối tượng res.partner
        """
        try:
            # Trích xuất phần tử customer
            customer = prestashop_elem.find('customer')
            if customer is None:
                return {}

            return {
                'name': f"{customer.findtext('firstname', '')} {customer.findtext('lastname', '')}".strip(),
                'email': customer.findtext('email', ''),
                'customer_rank': 1 if customer.findtext('newsletter') == '1' else 0,
                'create_date': customer.findtext('date_add'),
                'write_date': customer.findtext('date_upd'),
            }
        except Exception as e:
            _logger.error(f"Lỗi parse thông tin khách hàng: {str(e)}")

    def _prepare_prestashop_partner_vals(self, prestashop_elem):
        """
        Chuẩn bị giá trị cập nhật cho đối tượng prestashop.res.partner
        """
        try:
            customer = prestashop_elem.find('customer')
            if customer is None:
                _logger.error("Không tìm thấy phần tử customer")
                return {}

            groups = []
            associations = customer.find('associations')
            if associations is not None:
                groups_elem = associations.find('groups')
                if groups_elem is not None:
                    groups = [group.findtext('id') for group in groups_elem.findall('group')]

            return {
                'prestashop_id': customer.findtext('id'),
                'prestashop_email': customer.findtext('email', ''),
                'prestashop_default_group': ','.join(groups) if groups else '',
                'date_add': customer.findtext('date_add'),
                'date_upd': customer.findtext('date_upd'),
            }
        except Exception as e:
            return {}

    # Đăng ký hành động để hiển thị trong view
    def action_prestashop_partner_sync(self):
        """
        Hành động để hiển thị nút đồng bộ trong view
        """
        return self.action_sync_customer_details()