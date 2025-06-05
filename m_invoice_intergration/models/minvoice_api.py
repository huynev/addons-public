from odoo import models, api, _
from odoo.exceptions import ValidationError
import requests
import json
import base64


class MInvoiceApi(models.AbstractModel):
    _name = 'minvoice.api'
    _description = 'M-Invoice API Helper'

    @api.model
    def create_invoice(self, invoice_data, company_id):
        """Tạo hóa đơn trên M-Invoice"""
        config = self.env['minvoice.config'].get_config(company_id)
        token = config.get_valid_token()

        url = f"{config.base_url}/api/InvoiceApi78/Save"
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }

        try:
            response = requests.post(url, json=invoice_data, headers=headers, timeout=60)
            response.raise_for_status()

            result = response.json()
            if result.get('code') == '00':
                return result.get('data')
            else:
                raise ValidationError(f"Lỗi tạo hóa đơn M-Invoice: {result.get('message', 'Unknown error')}")

        except requests.exceptions.RequestException as e:
            raise ValidationError(f"Lỗi kết nối M-Invoice: {str(e)}")

    @api.model
    def sign_and_send_invoice(self, invoice_id, company_id):
        """Ký và gửi hóa đơn lên CQT"""
        config = self.env['minvoice.config'].get_config(company_id)
        token = config.get_valid_token()

        url = f"{config.base_url}/api/InvoiceApi78/Sign"
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
            'TaxCode': config.company_id.vat or ''
        }

        data = {'hoadon68_id': invoice_id}

        try:
            response = requests.post(url, json=data, headers=headers, timeout=60)
            response.raise_for_status()

            result = response.json()
            if result.get('code') == '00':
                return True
            else:
                raise ValidationError(f"Lỗi ký hóa đơn: {result.get('message', 'Unknown error')}")

        except requests.exceptions.RequestException as e:
            raise ValidationError(f"Lỗi kết nối M-Invoice: {str(e)}")

    @api.model
    def get_invoice_info(self, invoice_id, company_id):
        """Lấy thông tin hóa đơn"""
        config = self.env['minvoice.config'].get_config(company_id)
        token = config.get_valid_token()

        url = f"{config.base_url}/api/InvoiceApi78/GetInfoInvoice?id={invoice_id}"
        headers = {
            'Authorization': f'Bearer {token}',
        }

        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()

            result = response.json()
            if result.get('code') == '00':
                return result.get('data')
            else:
                return None

        except requests.exceptions.RequestException:
            return None

    @api.model
    def print_invoice(self, invoice_id, company_id):
        """In hóa đơn"""
        config = self.env['minvoice.config'].get_config(company_id)
        token = config.get_valid_token()

        url = f"{config.base_url}/api/InvoiceApi78/PrintInvoice?id={invoice_id}"
        headers = {
            'Authorization': f'Bearer {token}',
        }

        try:
            response = requests.get(url, headers=headers, timeout=60)
            response.raise_for_status()

            if response.headers.get('content-type') == 'application/pdf':
                return base64.b64encode(response.content).decode()
            else:
                result = response.json()
                if result.get('code') != '00':
                    raise ValidationError(f"Lỗi in hóa đơn: {result.get('message', 'Unknown error')}")
                return None

        except requests.exceptions.RequestException as e:
            raise ValidationError(f"Lỗi kết nối M-Invoice: {str(e)}")

    @api.model
    def get_xml_file(self, invoice_id, company_id):
        """Lấy file XML"""
        config = self.env['minvoice.config'].get_config(company_id)
        token = config.get_valid_token()

        url = f"{config.base_url}/api/InvoiceApi78/ExportXml?id={invoice_id}"
        headers = {
            'Authorization': f'Bearer {token}',
        }

        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()

            result = response.json()
            if result.get('code') == '00':
                xml_base64 = result.get('data')
                return xml_base64
            else:
                raise ValidationError(f"Lỗi lấy XML: {result.get('message', 'Unknown error')}")

        except requests.exceptions.RequestException as e:
            raise ValidationError(f"Lỗi kết nối M-Invoice: {str(e)}")