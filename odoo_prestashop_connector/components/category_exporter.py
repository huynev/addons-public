# components/category_exporter.py
from odoo.addons.component.core import Component
import logging
import xml.etree.ElementTree as ET
from odoo import fields

_logger = logging.getLogger(__name__)


class CategoryExporter(Component):
    _name = 'prestashop.category.exporter'
    _inherit = ['base.exporter']
    _apply_on = 'prestashop.product.category'
    _usage = 'record.exporter'

    def run(self, binding):
        self.binding = binding
        data = self._prepare_data()
        if binding.prestashop_id:
            self._update(data)
        else:
            self._create(data)

    def _prepare_data(self):
        prestashop = ET.Element('prestashop')
        prestashop.set('xmlns:xlink', 'http://www.w3.org/1999/xlink')

        category = ET.SubElement(prestashop, 'category')

        # Add name with language support
        name = ET.SubElement(category, 'name')
        lang = ET.SubElement(name, 'language')
        lang.set('id', '1')
        lang.text = f'<![CDATA[{self.binding.name}]]>'

        # Add link_rewrite
        link_rewrite = ET.SubElement(category, 'link_rewrite')
        lang = ET.SubElement(link_rewrite, 'language')
        lang.set('id', '1')
        lang.text = f'<![CDATA[{self._format_link_rewrite(self.binding.name)}]]>'

        # Add description
        description = ET.SubElement(category, 'description')
        lang = ET.SubElement(description, 'language')
        lang.set('id', '1')
        lang.text = '<![CDATA[]]>'

        # Add active status
        active = ET.SubElement(category, 'active')
        active.text = '<![CDATA[1]]>'

        # Add parent category
        if self.binding.parent_id and self.binding.parent_id.prestashop_bind_ids:
            id_parent = ET.SubElement(category, 'id_parent')
            id_parent.text = f'<![CDATA[{self.binding.parent_id.prestashop_bind_ids[0].prestashop_id}]]>'
        else:
            id_parent = ET.SubElement(category, 'id_parent')
            id_parent.text = '<![CDATA[0]]>'

        xml_str = ET.tostring(prestashop, encoding='utf-8', xml_declaration=True)
        xml_str = xml_str.decode('utf-8').replace('&lt;![CDATA[', '<![CDATA[').replace(']]&gt;', ']]>')
        return xml_str.encode('utf-8')

    def _format_link_rewrite(self, name):
        """Convert category name to URL friendly format"""
        if not name:
            return ''
        import re
        name = name.lower()
        name = re.sub(r'[^a-z0-9]+', '-', name)
        name = name.strip('-')
        return name

    def _create(self, data):
        prestashop = self.shop_id.backend_id._get_prestashop_client()
        try:
            result = prestashop.add('categories', data)
            if isinstance(result, ET.Element):
                category_elem = result.find('.//category')
                if category_elem is not None:
                    id_elem = category_elem.find('id')
                    if id_elem is not None and id_elem.text:
                        category_id = id_elem.text.strip('[]!CDATA')
                        self.binding.prestashop_id = int(category_id)
                        self.binding.date_add = fields.Datetime.now()
                        _logger.info("Created category in PrestaShop with ID: %s", category_id)
                        return
            _logger.error("Could not find category ID in PrestaShop response")
        except Exception as e:
            _logger.error("Error creating category in PrestaShop: %s", str(e))
            raise

    def _update(self, data):
        prestashop = self.shop_id.backend_id._get_prestashop_client()
        try:
            prestashop.edit('categories', self.binding.prestashop_id, data)
            self.binding.date_upd = fields.Datetime.now()
            _logger.info("Updated category in PrestaShop with ID: %s", self.binding.prestashop_id)
        except Exception as e:
            _logger.error("Error updating category in PrestaShop: %s", str(e))
            raise