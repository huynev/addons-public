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

        try:
            # Kiểm tra category parent trước
            if self.binding.parent_id:
                # Tìm prestashop binding của parent
                parent_binding = self.env['prestashop.product.category'].search([
                    ('odoo_id', '=', self.binding.parent_id.id),
                    ('shop_id', '=', self.binding.shop_id.id)
                ], limit=1)

                # Nếu parent chưa có binding, tạo binding và export
                if not parent_binding:
                    parent_binding = self.env['prestashop.product.category'].create({
                        'odoo_id': self.binding.parent_id.id,
                        'shop_id': self.binding.shop_id.id,
                    })
                    parent_binding.export_record()

                # Nếu parent chưa có prestashop_id, export parent trước
                elif not parent_binding.prestashop_id:
                    parent_binding.export_record()

            # Export category hiện tại
            data = self._prepare_data()
            if self.binding.prestashop_id:
                self._update(data)
            else:
                self._create(data)

            # Export tất cả category con
            child_categories = self.env['product.category'].search([
                ('parent_id', '=', self.binding.odoo_id.id)
            ])

            for child in child_categories:
                # Tìm hoặc tạo binding cho child
                child_binding = self.env['prestashop.product.category'].search([
                    ('odoo_id', '=', child.id),
                    ('shop_id', '=', self.binding.shop_id.id)
                ], limit=1)

                if not child_binding:
                    child_binding = self.env['prestashop.product.category'].create({
                        'odoo_id': child.id,
                        'shop_id': self.binding.shop_id.id,
                    })

                # Export child category
                child_binding.export_record()

        except Exception as e:
            _logger.error(f"Error exporting category {self.binding.name}: {str(e)}")
            raise

    def _prepare_data(self):
        prestashop = ET.Element('prestashop')
        prestashop.set('xmlns:xlink', 'http://www.w3.org/1999/xlink')
        category = ET.SubElement(prestashop, 'category')

        def create_cdata_element(parent, tag, value=''):
            elem = ET.SubElement(parent, tag)
            elem.text = f'<![CDATA[{value}]]>'
            return elem

        # Add ID if updating
        if self.binding.prestashop_id:
            create_cdata_element(category, 'id', str(self.binding.prestashop_id))

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

        # Add description (empty by default)
        description = ET.SubElement(category, 'description')
        lang = ET.SubElement(description, 'language')
        lang.set('id', '1')
        lang.text = f'<![CDATA[{self.binding.description or ""}]]>'

        # Add active status
        create_cdata_element(category, 'active', '1')

        # Add parent category
        if self.binding.parent_id:
            parent_binding = self.env['prestashop.product.category'].search([
                ('odoo_id', '=', self.binding.parent_id.id),
                ('shop_id', '=', self.binding.shop_id.id)
            ], limit=1)
            if parent_binding and parent_binding.prestashop_id:
                create_cdata_element(category, 'id_parent', str(parent_binding.prestashop_id))
            else:
                create_cdata_element(category, 'id_parent', '2')  # Root category in PrestaShop
        else:
            create_cdata_element(category, 'id_parent', '2')  # Root category in PrestaShop

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
        prestashop = self.binding.shop_id.backend_id._get_prestashop_client()
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
        prestashop = self.binding.shop_id.backend_id._get_prestashop_client()
        try:
            resource = f'categories/{self.binding.prestashop_id}'
            prestashop.edit(resource, data)
            self.binding.date_upd = fields.Datetime.now()
            _logger.info("Updated category in PrestaShop with ID: %s", self.binding.prestashop_id)
        except Exception as e:
            _logger.error("Error updating category in PrestaShop: %s", str(e))
            raise