from odoo import http
from odoo.http import request
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class BaseAPIController(http.Controller):
    def _get_context(self):
        """
        Retrieve and process the context from the incoming request.
        """
        context = dict(request.context)

        # Get allowed_company_ids from request params or use default
        allowed_company_ids = request.params.get('allowed_company_ids', [])
        if isinstance(allowed_company_ids, str):
            allowed_company_ids = [int(id) for id in allowed_company_ids.split(',')]
        context['allowed_company_ids'] = allowed_company_ids

        # Get default_company_id from request params or use first allowed company
        default_company_id = request.params.get('default_company_id')
        if default_company_id:
            default_company_id = int(default_company_id)
        else:
            default_company_id = allowed_company_ids[0] if allowed_company_ids else None

        if default_company_id:
            if default_company_id not in allowed_company_ids:
                raise UserError("Default company is not in allowed companies.")
            context['company_id'] = default_company_id

        return context

    def _set_context(self, additional_context=None):
        """
        Set the context for the current request.
        """
        context = self._get_context()
        if additional_context:
            context.update(additional_context)
        request.env = request.env(context=context)
        return context