from odoo import http
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal
import base64


class CustomerPortalQuotation(CustomerPortal):
    @http.route(['/my/quotation/preview/<int:quotation_id>'], type='http', auth="public", website=True)
    def portal_my_quotation(self, quotation_id, access_token=None, **kw):
        try:
            quotation_sudo = self._document_check_access('custom.quotation', quotation_id, access_token)
        except:
            return request.redirect('/my')

        values = {
            'quotation': quotation_sudo,
            'page_name': 'quotation',
        }
        return request.render("custom_quotation.portal_my_quotation", values)

    @http.route(['/my/quotation/download/<int:quotation_id>'], type='http', auth="public", website=True)
    def download_quotation_pdf(self, quotation_id, access_token=None, **kw):
        try:
            # Verify access token
            quotation_sudo = self._document_check_access('custom.quotation', quotation_id, access_token)
        except:
            return request.redirect('/my')

        if not quotation_sudo.pdf_file:
            return request.redirect('/my')

        # Return the stored PDF file
        return request.make_response(
            base64.b64decode(quotation_sudo.pdf_file),
            headers=[
                ('Content-Type', 'application/pdf'),
                ('Content-Disposition', 'attachment; filename=%s' % quotation_sudo.pdf_filename or 'quotation.pdf')
            ]
        )