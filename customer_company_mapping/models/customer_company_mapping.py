from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


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

    @api.model
    def create(self, vals):
        if 'partner_id' in vals:
            partner = self.env['res.partner'].browse(vals['partner_id'])
            company = self._get_company_based_on_address(partner)
            if company:
                vals['company_id'] = company.id
                vals = self._update_company_dependent_fields(vals, company)
        return super(SaleOrder, self).create(vals)

    def write(self, vals):
        if 'company_id' in vals or 'partner_id' in vals or 'partner_shipping_id' in vals:
            for record in self:
                company = vals.get('company_id') and self.env['res.company'].browse(vals['company_id']) or \
                          self._get_company_based_on_address(
                              vals.get('partner_shipping_id') and self.env['res.partner'].browse(
                                  vals['partner_shipping_id']) or \
                              vals.get('partner_id') and self.env['res.partner'].browse(vals['partner_id']) or \
                              record.partner_shipping_id or record.partner_id)
                if company:
                    vals['company_id'] = company.id
                    vals = self._update_company_dependent_fields(vals, company)
        return super(SaleOrder, self).write(vals)

    @api.onchange('partner_id', 'partner_shipping_id')
    def _onchange_partner_shipping_id(self):
        super(SaleOrder, self)._onchange_partner_shipping_id()
        self._update_company_based_on_address()

    @api.onchange('partner_shipping_id.state_id', 'partner_shipping_id.district_id', 'partner_shipping_id.ward_id',
                  'partner_shipping_id.street')
    def _onchange_shipping_address(self):
        self._update_company_based_on_address()

    def _update_company_based_on_address(self):
        for record in self:
            if record.partner_shipping_id:
                company = record._get_company_based_on_address(record.partner_shipping_id)
                if company and company != record.company_id:
                    record.company_id = company
                    record._update_company_dependent_fields({}, company)

    def _get_company_based_on_address(self, partner):
        domain = []
        if partner.street:
            domain.append(('street', '=', partner.street))
        if partner.ward_id.id:
            domain.append(('ward_id', '=', partner.ward_id.id))
        if partner.district_id.id:
            domain.append(('district_id', '=', partner.district_id.id))
        if partner.state_id.id:
            domain.append(('state_id', '=', partner.state_id.id))

        mapping = self.env['customer.company.mapping'].search(domain, limit=1)

        return mapping.company_id if mapping else False

    def _update_company_dependent_fields(self, vals, company):
        # Update pricelist
        pricelist = self.env['product.pricelist'].search([
            ('company_id', '=', company.id),
            ('currency_id', '=', company.currency_id.id)
        ], limit=1)
        if pricelist:
            vals['pricelist_id'] = pricelist.id

        # Update warehouse
        warehouse = self.env['stock.warehouse'].search([
            ('company_id', '=', company.id)
        ], limit=1)
        if warehouse:
            vals['warehouse_id'] = warehouse.id

        # If this method is called from an onchange method, update the record directly
        if not vals:
            self.update(vals)

        return vals

    @api.onchange('company_id')
    def _onchange_company_id(self):
        if self.company_id:
            self._update_company_dependent_fields({}, self.company_id)

    @api.constrains('company_id', 'pricelist_id', 'warehouse_id')
    def _check_company_consistency(self):
        for record in self:
            if record.pricelist_id and record.pricelist_id.company_id != record.company_id:
                raise ValidationError(_("The pricelist must belong to the same company as the sale order."))
            if record.warehouse_id and record.warehouse_id.company_id != record.company_id:
                raise ValidationError(_("The warehouse must belong to the same company as the sale order."))