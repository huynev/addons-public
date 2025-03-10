# -*- coding: utf-8 -*-
# Copyright 2023 Your Company
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import models, fields, tools
from odoo.addons.component.core import AbstractComponent
import logging

_logger = logging.getLogger(__name__)


class WooModelBinder(AbstractComponent):
    """Bind records and give external IDs to Odoo models.

    Bindings are the link between an external ID (e.g. a WooCommerce ID)
    and an Odoo ID. They are stored in binding models, which are
    basically Odoo models inheriting from 'woo.binding' and having
    a relation to their corresponding Odoo model.

    This component is responsible for:
    * Finding the binding between an external ID and an Odoo record
    * Creating the binding when it does not exist yet
    * Binding a newly created Odoo record to an external ID
    * Unwrapping a binding (separating the binding record from the actual record)
    """
    _name = 'woo.binder'
    _inherit = ['base.binder', 'base.woo.connector']
    _usage = 'binder'

    # Name of the external ID field on the binding model
    _external_field = 'woo_id'

    # Name of the field on the binding model pointing to the Odoo record
    _internal_field = 'odoo_id'

    def to_internal(self, external_id, unwrap=False):
        """Give the Odoo recordset for an external ID.

        :param external_id: external ID for which we want the Odoo record
        :param unwrap: if True, returns the normal record and not the binding
        :return: a recordset (may be empty) or None if the external_id is invalid
        :rtype: recordset or None
        """
        if not external_id:
            return None

        binding = self.model.with_context(active_test=False).search([
            (self._external_field, '=', str(external_id)),
            ('backend_id', '=', self.backend_record.id),
        ], limit=1)

        if not binding:
            return None

        if unwrap:
            binding.ensure_one()
            return binding.odoo_id
        return binding

    def to_external(self, binding, wrap=False):
        """Give the external ID for an Odoo binding record.

        :param binding: Odoo binding record for which we want the external ID
                        or an Odoo record if wrap is True
        :param wrap: if True, binding is a normal Odoo record, find the binding record
        :return: external ID of the record or None if the binding is not yet exported
        :rtype: str or None
        """
        if not binding:
            return None

        if wrap:
            binding_model = self.model._name
            odoo_model = binding._name

            if odoo_model != binding_model:
                # If we are given an Odoo record instead of a binding, find the binding
                binding = self.env[binding_model].search([
                    (self._internal_field, '=', binding.id),
                    ('backend_id', '=', self.backend_record.id),
                ], limit=1)

                if not binding:
                    return None

        return binding[self._external_field]

    def bind(self, external_id, binding):
        """Create the link between an external ID and an Odoo binding record.

        :param external_id: external ID to bind
        :param binding: Odoo binding record to bind
        :type binding: int or recordset
        :return: binding record
        :rtype: recordset
        """
        if isinstance(binding, models.BaseModel):
            binding.ensure_one()
            binding_id = binding.id
        else:
            binding_id = binding

        # Always check if binding already exists to avoid duplicates
        existing = self.model.with_context(active_test=False).search([
            (self._external_field, '=', str(external_id)),
            ('backend_id', '=', self.backend_record.id),
        ], limit=1)

        if existing:
            if existing.id != binding_id:
                # Update the existing binding
                existing.write({self._internal_field: binding_id})
            return existing
        else:
            # Create a new binding
            values = {
                self._external_field: str(external_id),
                self._internal_field: binding_id,
                'backend_id': self.backend_record.id,
            }
            binding = self.model.create(values)
            _logger.debug('Bound %s.%s to WooCommerce ID %s',
                          binding._name, binding.id, external_id)
            return binding

    def unwrap_binding(self, binding):
        """Return the normal record for a binding record.

        :param binding: binding record to unwrap
        :type binding: recordset
        :return: normal record
        :rtype: recordset
        """
        if isinstance(binding, models.BaseModel):
            binding.ensure_one()
        else:
            binding = self.model.browse(binding)

        return binding.odoo_id

    def unwrap_model(self):
        """Return the normal model for this binder's binding model.

        For example, if the binding model is 'woo.product.template',
        the unwrapped model would be 'product.template'.

        :return: model recordset
        :rtype: odoo.models.Model
        """
        # The _inherits attribute is a dictionary in the form {'model_name': 'field_name'}
        # For binding models, there is always one entry where field_name is the same as self._internal_field
        for model_name in self.model._inherits:
            field = self.model._inherits[model_name]
            if field == self._internal_field:
                return self.env[model_name]

        # Fallback: if no _inherits or the internal field was not found, return the model itself
        return self.env[self.model._name]