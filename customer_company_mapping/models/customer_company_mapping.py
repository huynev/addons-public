from odoo import models, fields, api


class CustomerCompanyMapping(models.Model):
    _name = 'customer.company.mapping'
    _description = 'Customer Company Mapping'

    company_id = fields.Many2one('res.company', string='Company', required=True, ondelete='restrict')
    state_id = fields.Many2one('res.country.state', string='State', ondelete='restrict')
    district_id = fields.Many2one('res.country.district', string='District', ondelete='restrict')
    ward_id = fields.Many2one('res.country.ward', string='Ward', ondelete='restrict')
    street = fields.Char(string='Street')


class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.onchange('state_id', 'district_id', 'ward_id', 'street')
    def _onchange_address(self):
        if self.street and self.ward_id and self.district_id and self.state_id:
            domain = []
            if self.street:
                domain.append(('street', '=', self.street))
            if self.ward_id.id:
                domain.append(('ward_id', '=', self.ward_id.id))
            if self.district_id.id:
                domain.append(('district_id', '=', self.district_id.id))
            if self.state_id.id:
                domain.append(('state_id', '=', self.state_id.id))

            mapping = self.env['customer.company.mapping'].search(domain, limit=1)

            if mapping and mapping.company_id:
                self.company_id = mapping.company_id


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    @api.onchange('partner_id', 'partner_shipping_id')
    def _onchange_partner_shipping_id(self):
        super(SaleOrder, self)._onchange_partner_shipping_id()
        self._update_company_based_on_address()

    @api.onchange('partner_shipping_id.state_id', 'partner_shipping_id.district_id', 'partner_shipping_id.ward_id', 'partner_shipping_id.street')
    def _onchange_shipping_address(self):
        self._update_company_based_on_address()

    def _update_company_based_on_address(self):
        if self.partner_shipping_id:
            domain = []
            if self.partner_shipping_id.street:
                domain.append(('street', '=', self.partner_shipping_id.street))
            if self.partner_shipping_id.ward_id.id:
                domain.append(('ward_id', '=', self.partner_shipping_id.ward_id.id))
            if self.partner_shipping_id.district_id.id:
                domain.append(('district_id', '=', self.partner_shipping_id.district_id.id))
            if self.partner_shipping_id.state_id.id:
                domain.append(('state_id', '=', self.partner_shipping_id.state_id.id))

            mapping = self.env['customer.company.mapping'].search(domain, limit=1)

            if mapping and mapping.company_id:
                self.company_id = mapping.company_id