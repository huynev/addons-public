from odoo.addons.component.core import Component
from odoo import fields

class MagentoBinder(Component):
    """ Binder for Magento """
    _name = 'magento.binder'
    _inherit = ['base.binder', 'magento.base.connector']
    _apply_on = [
        'magento.product.product',
        'magento.product.template',
        'magento.res.partner',
        'magento.sale.order',
        'magento.website',
        'magento.store',
        'magento.storeview',
    ]

    def to_internal(self, external_id, unwrap=False):
        """ Return the Odoo record for the external ID """
        if not external_id:
            return None

        binding = self.model.search([
            ('external_id', '=', str(external_id)),
            ('backend_id', '=', self.backend_record.id)
        ], limit=1)

        if not binding:
            return None

        if unwrap:
            return binding.odoo_id
        return binding

    def to_external(self, binding, wrap=False):
        """ Return the external ID for the binding """
        if not binding:
            return None

        if isinstance(binding, int):
            binding = self.model.browse(binding)

        if wrap:
            return binding.external_id
        return binding.external_id

    def bind(self, external_id, binding):
        """ Create the link between an external ID and an Odoo ID """
        assert external_id, "External ID is required for binding"
        binding.with_context(connector_no_export=True).write({
            'external_id': str(external_id),
            'sync_date': fields.Datetime.now(),
        })
        return True