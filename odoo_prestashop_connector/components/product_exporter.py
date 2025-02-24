from odoo.addons.component.core import Component
import logging
import base64
import xml.etree.ElementTree as ET

from odoo import fields

_logger = logging.getLogger(__name__)


class ProductExporter(Component):
    _name = 'prestashop.product.exporter'
    _inherit = ['base.exporter']
    _apply_on = 'prestashop.product.template'
    _usage = 'record.exporter'

    def run(self, binding):
        """ Export the product to PrestaShop """
        self.binding = binding
        prestashop = self.binding.shop_id.backend_id._get_prestashop_client()

        try:
            # Kiểm tra sản phẩm tồn tại bằng reference
            reference = self.binding.main_reference or self.binding.default_code
            if reference:
                # Tìm sản phẩm có reference trùng khớp trên PrestaShop
                filters = {'filter[reference]': str(reference)}
                try:
                    all_products = prestashop.get('products', options=filters)
                    products = all_products.findall('.//product')

                    if len(products) > 1:
                        # Nếu có nhiều sản phẩm, lấy danh sách ID
                        prestashop_ids = [p.attrib.get('id') for p in products if p.attrib.get('id')]
                        note_message = f"WARNING: Found multiple products on PrestaShop with reference {reference}. Product IDs: {', '.join(prestashop_ids)}"
                        self.binding.note = note_message
                        return

                    elif len(products) == 1:
                        prestashop_id = products[0].attrib.get('id')
                        if prestashop_id:
                            self.binding.prestashop_id = int(prestashop_id)
                            data = self._prepare_data()
                            self._update(data)

                            if self.binding.attribute_line_ids:
                                for variant in self.binding.product_variant_ids:
                                    if variant.default_code:
                                        # Tìm combination với reference của variant
                                        combination_filters = {
                                            'filter[id_product]': str(prestashop_id),
                                            'filter[reference]': str(variant.default_code)
                                        }
                                        combinations = prestashop.get('combinations', options=combination_filters)
                                        combination = combinations.find('.//combination')

                                        if combination is not None:
                                            # Biến thể đã tồn tại, update
                                            combination_id = combination.get('id')
                                            combination_data = self._prepare_combination_data(variant, combination_id)
                                            prestashop.edit(f'combinations/{combination_id}', combination_data)
                                            _logger.info(f"Updated combination for variant {variant.default_code}")
                                        else:
                                            # Biến thể chưa tồn tại, tạo mới
                                            combination_data = self._prepare_combination_data(variant)
                                            prestashop.add('combinations', combination_data)
                                            _logger.info(f"Created new combination for variant {variant.default_code}")

                            # Cập nhật kho sau khi đã xử lý biến thể
                            self._update_stock()
                            _logger.info(
                                f"Updated existing product on PrestaShop with reference {reference} (ID: {prestashop_id})")
                            return

                except Exception as e:
                    _logger.warning(f"Error checking existing product by reference: {str(e)}")

            # Nếu không tìm thấy sản phẩm hoặc không có reference, thực hiện logic thông thường
            data = self._prepare_data()
            if self.binding.prestashop_id:
                self._update(data)
            else:
                self._create(data)
                self._upload_images()

            if self.binding.attribute_line_ids:
                self._create_combinations()
            self._update_stock()

        except Exception as e:
            _logger.error(f"Error during product export: {str(e)}")
            raise

    def _prepare_data(self):
        """ Prepare product data for export """
        prestashop = ET.Element('prestashop')
        prestashop.set('xmlns:xlink', 'http://www.w3.org/1999/xlink')
        product = ET.SubElement(prestashop, 'product')

        def create_cdata_element(parent, tag, value=''):
            elem = ET.SubElement(parent, tag)
            elem.text = f'<![CDATA[{value}]]>'
            return elem

        price = self.binding.price

        if self.binding.prestashop_id:
            create_cdata_element(product, 'id', str(self.binding.prestashop_id))

        # Get PrestaShop category from Odoo category
        category_obj = self.env['prestashop.product.category']
        category_bindings = category_obj.search([
            ('odoo_id', '=', self.binding.odoo_id.categ_id.id),
            ('shop_id', '=', self.binding.shop_id.id)
        ], limit=1)

        # Technical fields
        # create_cdata_element(product, 'id_manufacturer', '1')
        # create_cdata_element(product, 'id_supplier', '1')
        create_cdata_element(product, 'available_for_order', '1')

        # Get PrestaShop category from Odoo category
        category_obj = self.env['prestashop.product.category']
        category_bindings = category_obj.search([
            ('odoo_id', '=', self.binding.odoo_id.categ_id.id),
            ('shop_id', '=', self.binding.shop_id.id)
        ], limit=1)

        # Set default category
        default_category_id = category_bindings.prestashop_id if category_bindings else self.binding.shop_id.default_category_id.id
        create_cdata_element(product, 'id_category_default', str(default_category_id))

        create_cdata_element(product, 'new', '1')

        if self.binding.attribute_line_ids:
            # Sản phẩm có biến thể
            create_cdata_element(product, 'id_default_combination', '1')
            create_cdata_element(product, 'product_type', 'standard')
        else:
            # Sản phẩm không có biến thể
            create_cdata_element(product, 'id_default_combination', '0')
            create_cdata_element(product, 'product_type', '')

        if self.binding.taxes_id:
            tax_mapping = self.env['prestashop.tax.mapping'].search([
                ('shop_id', '=', self.binding.shop_id.id),
                ('tax_id', '=', self.binding.taxes_id[0].id)  # Lấy thuế đầu tiên
            ], limit=1)

            if tax_mapping:
                create_cdata_element(product, 'id_tax_rules_group', str(tax_mapping.prestashop_tax_group_id))
            else:
                _logger.warning(
                    f"No tax mapping found for tax {self.binding.taxes_id[0].name} in shop {self.binding.shop_id.name}"
                )
                create_cdata_element(product, 'id_tax_rules_group', '1')  # Default tax group
        else:
            # Nếu không có thuế, sử dụng default tax group
            create_cdata_element(product, 'id_tax_rules_group', '')

        create_cdata_element(product, 'type', '1')
        create_cdata_element(product, 'id_shop_default', '1')

        # Basic fields
        if self.binding.default_code:
            unique_reference = self.binding.default_code
        else:
            if self.binding.main_reference:
                reference = self.binding.main_reference
            else:
                reference = f"PROD-{self.binding.id}"
            # Kiểm tra và tạo reference duy nhất
            unique_reference = self._get_unique_reference(reference)

        create_cdata_element(product, 'reference', unique_reference)

        # Cập nhật main_reference nếu nó được tạo tự động
        if not self.binding.main_reference:
            self.binding.main_reference = unique_reference

        create_cdata_element(product, 'supplier_reference', '')
        create_cdata_element(product, 'ean13', self.binding.barcode or '')
        create_cdata_element(product, 'state', '1')
        create_cdata_element(product, 'price', str(price))
        create_cdata_element(product, 'unit_price', str(price))
        create_cdata_element(product, 'show_price', '1')
        create_cdata_element(product, 'on_sale', '0')
        create_cdata_element(product, 'active', '1')

        # Language fields
        for lang_field in ['meta_description', 'meta_keywords', 'meta_title',
                           'link_rewrite', 'name', 'description', 'description_short']:
            field_elem = ET.SubElement(product, lang_field)
            lang = ET.SubElement(field_elem, 'language')
            lang.set('id', '1')

            if lang_field == 'name':
                value = self.binding.name or ''
            elif lang_field == 'description':
                value = self.binding.description or ''
            elif lang_field == 'description_short':
                value = self.binding.description_sale or ''
            elif lang_field == 'link_rewrite':
                value = self._format_link_rewrite(self.binding.name)
            else:
                value = ''
            lang.text = f'<![CDATA[{value}]]>'

        # Associations
        associations = ET.SubElement(product, 'associations')
        categories = ET.SubElement(associations, 'categories')

        # Add product's category to associations
        if category_bindings:
            category = ET.SubElement(categories, 'category')
            create_cdata_element(category, 'id', str(category_bindings.prestashop_id))

        xml_str = ET.tostring(prestashop, encoding='utf-8', xml_declaration=True)
        xml_str = xml_str.decode('utf-8').replace('&lt;![CDATA[', '<![CDATA[').replace(']]&gt;', ']]>')
        return xml_str.encode('utf-8')

    def _get_prestashop_option_id(self, attribute):
        """Get or create PrestaShop attribute (option) ID"""
        prestashop = self.binding.shop_id.backend_id._get_prestashop_client()

        try:
            # Tìm attribute theo tên
            filters = {'filter[name]': str(attribute.name)}
            result = prestashop.get('product_options', options=filters)
            existing_options = result.findall('.//product_option')

            if existing_options:
                return existing_options[0].get('id')

            # Tạo attribute mới
            option_schema = (
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                '<prestashop xmlns:xlink="http://www.w3.org/1999/xlink">\n'
                '    <product_option>\n'
                '        <name>\n'
                '            <language id="1"><![CDATA[{}]]></language>\n'
                '        </name>\n'
                '        <public_name>\n'
                '            <language id="1"><![CDATA[{}]]></language>\n'
                '        </public_name>\n'
                '        <group_type>select</group_type>\n'
                '    </product_option>\n'
                '</prestashop>'.format(attribute.name, attribute.name)
            ).encode('utf-8')

            result = prestashop.add('product_options', option_schema)
            return result.find('.//id').text

        except Exception as e:
            _logger.error(f"Error handling PrestaShop option: {str(e)}")
            raise

    def _get_prestashop_option_value_id(self, value, option_id):
        """Get or create PrestaShop attribute value ID"""
        prestashop = self.binding.shop_id.backend_id._get_prestashop_client()

        try:
            # Tìm value theo tên và option ID
            filters = {
                'filter[id_attribute_group]': str(option_id),
                'filter[name]': str(value.name)
            }
            result = prestashop.get('product_option_values', options=filters)
            existing_values = result.findall('.//product_option_value')

            if existing_values:
                return existing_values[0].get('id')

            # Tạo value mới
            value_schema = (
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                '<prestashop xmlns:xlink="http://www.w3.org/1999/xlink">\n'
                '    <product_option_value>\n'
                '        <id_attribute_group><![CDATA[{}]]></id_attribute_group>\n'
                '        <name>\n'
                '            <language id="1"><![CDATA[{}]]></language>\n'
                '        </name>\n'
                '    </product_option_value>\n'
                '</prestashop>'.format(option_id, value.name)
            ).encode('utf-8')

            result = prestashop.add('product_option_values', value_schema)
            return result.find('.//id').text

        except Exception as e:
            _logger.error(f"Error handling PrestaShop option value: {str(e)}")
            raise

    def _get_prestashop_attribute_id(self, attribute):
        """Get or create PrestaShop attribute ID"""
        prestashop = self.binding.shop_id.backend_id._get_prestashop_client()

        try:
            # Tìm feature theo tên trước
            filters = {'filter[name]': str(attribute.name)}
            result = prestashop.get('product_features', options=filters)
            existing_features = result.findall('.//product_feature')

            if existing_features:
                # Trả về ID nếu feature đã tồn tại
                feature_id = existing_features[0].get('id')
                return feature_id

            # Xử lý tên thuộc tính để đảm bảo UTF-8
            attribute_name = attribute.name.encode('utf-8').decode('utf-8')

            # Tạo feature mới
            feature_schema = (
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                '<prestashop xmlns:xlink="http://www.w3.org/1999/xlink">\n'
                '    <product_feature>\n'
                '        <name>\n'
                '            <language id="1"><![CDATA[{}]]></language>\n'
                '        </name>\n'
                '    </product_feature>\n'
                '</prestashop>'.format(attribute_name)
            )

            # Chuyển string thành bytes với encoding UTF-8
            feature_schema = feature_schema.encode('utf-8')

            # Thêm feature mới
            result = prestashop.add('product_features', feature_schema)
            new_feature_id = result.find('.//id').text
            return new_feature_id

        except Exception as e:
            _logger.error(f"Error handling PrestaShop feature: {str(e)}")
            raise

    def _get_prestashop_attribute_value_id(self, value):
        """Get or create PrestaShop attribute value ID"""
        prestashop = self.binding.shop_id.backend_id._get_prestashop_client()

        try:
            # Lấy feature ID
            feature_id = self._get_prestashop_attribute_id(value.attribute_id)

            # Tìm feature value theo tên và feature ID
            filters = {
                'filter[id_feature]': str(feature_id),
                'filter[value]': str(value.name)
            }
            result = prestashop.get('product_feature_values', options=filters)
            existing_values = result.findall('.//product_feature_value')

            if existing_values:
                # Trả về ID nếu value đã tồn tại
                value_id = existing_values[0].get('id')
                return value_id

            # Xử lý tên giá trị để đảm bảo UTF-8
            value_name = value.name.encode('utf-8').decode('utf-8')

            # Tạo feature value mới
            value_schema = (
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                '<prestashop xmlns:xlink="http://www.w3.org/1999/xlink">\n'
                '    <product_feature_value>\n'
                '        <id_feature><![CDATA[{}]]></id_feature>\n'
                '        <value>\n'
                '            <language id="1"><![CDATA[{}]]></language>\n'
                '        </value>\n'
                '    </product_feature_value>\n'
                '</prestashop>'.format(feature_id, value_name)
            )

            # Chuyển string thành bytes với encoding UTF-8
            value_schema = value_schema.encode('utf-8')

            # Thêm feature value mới
            result = prestashop.add('product_feature_values', value_schema)
            new_value_id = result.find('.//id').text
            return new_value_id

        except Exception as e:
            _logger.error(f"Error handling PrestaShop feature value: {str(e)}")
            raise

    def _create_combinations(self):
        """Create combinations for product on PrestaShop"""
        prestashop = self.binding.shop_id.backend_id._get_prestashop_client()

        try:
            # Lặp qua các biến thể của sản phẩm
            for variant in self.binding.product_variant_ids:
                # Tạo combination mới
                combination_data = self._prepare_combination_data(variant)
                result = prestashop.add('combinations', combination_data)

                if result is not None:
                    _logger.info(f"Created combination for product {self.binding.prestashop_id} variant {variant.id}")

        except Exception as e:
            _logger.error(f"Error creating combinations: {str(e)}")
            raise

    def _prepare_combination_data(self, variant, combination_id=None):
        """Prepare combination data for export"""
        prestashop = ET.Element('prestashop')
        prestashop.set('xmlns:xlink', 'http://www.w3.org/1999/xlink')
        combination = ET.SubElement(prestashop, 'combination')

        def create_cdata_element(parent, tag, value=''):
            elem = ET.SubElement(parent, tag)
            elem.text = f'<![CDATA[{value}]]>'
            return elem

        if combination_id:
            create_cdata_element(combination, 'id', str(combination_id))

        # Required fields
        create_cdata_element(combination, 'id_product', str(self.binding.prestashop_id))
        # Kiểm tra và tạo reference mặc định nếu không có
        default_code = variant.default_code or f"COMBI-{variant.id}"
        unique_reference = self._get_unique_reference(default_code, combination=True)
        create_cdata_element(combination, 'reference', unique_reference)

        create_cdata_element(combination, 'ean13', variant.barcode or '')
        create_cdata_element(combination, 'mpn', variant.default_code or '')
        create_cdata_element(combination, 'supplier_reference', '')

        # Tính giá chênh lệch so với sản phẩm gốc
        price_variant = variant.price_extra + self.binding.price
        create_cdata_element(combination, 'price', str(price_variant))

        create_cdata_element(combination, 'minimal_quantity', '0')

        # Add associations with option values
        associations = ET.SubElement(combination, 'associations')
        option_values = ET.SubElement(associations, 'product_option_values')
        option_values.set('nodeType', 'product_option_value')
        option_values.set('api', 'product_option_values')

        # Add each attribute value
        for attr_value in variant.product_template_attribute_value_ids:
            # Lấy option_id cho attribute
            option_id = self._get_prestashop_option_id(attr_value.attribute_id)
            if option_id:
                # Lấy value_id với option_id tương ứng
                value_id = self._get_prestashop_option_value_id(
                    attr_value.product_attribute_value_id,
                    option_id
                )
                if value_id:
                    value_elem = ET.SubElement(option_values, 'product_option_value')
                    create_cdata_element(value_elem, 'id', str(value_id))

        xml_str = ET.tostring(prestashop, encoding='utf-8', xml_declaration=True)
        xml_str = xml_str.decode('utf-8').replace('&lt;![CDATA[', '<![CDATA[').replace(']]&gt;', ']]>')
        return xml_str.encode('utf-8')

    def _format_link_rewrite(self, name):
        """Convert name to URL friendly format"""
        if not name:
            return ''
        import re
        # Chuyển các ký tự có dấu sang không dấu
        name = name.lower()
        name = re.sub(r'[àáạảãâầấậẩẫăằắặẳẵ]', 'a', name)
        name = re.sub(r'[èéẹẻẽêềếệểễ]', 'e', name)
        name = re.sub(r'[ìíịỉĩ]', 'i', name)
        name = re.sub(r'[òóọỏõôồốộổỗơờớợởỡ]', 'o', name)
        name = re.sub(r'[ùúụủũưừứựửữ]', 'u', name)
        name = re.sub(r'[ỳýỵỷỹ]', 'y', name)
        name = re.sub(r'đ', 'd', name)
        # Thay thế các ký tự không phải chữ cái/số bằng dấu gạch ngang
        name = re.sub(r'[^a-z0-9]+', '-', name)
        # Xóa dấu gạch ngang ở đầu và cuối
        name = name.strip('-')
        return name

    def _get_unique_reference(self, reference, combination=False):
        prestashop = self.binding.shop_id.backend_id._get_prestashop_client()
        unique_reference = reference
        counter = 0

        while True:
            try:
                if combination:
                    filters = {'filter[reference]': str(unique_reference)}
                    result = prestashop.get('combinations', options=filters)
                else:
                    filters = {'filter[reference]': str(unique_reference)}
                    result = prestashop.get('products', options=filters)

                if result.find('.//product') is None and result.find('.//combination') is None:
                    break
                else:
                    unique_reference = f"{reference}-{counter}"
                    counter += 1

            except Exception as e:
                _logger.error(f"Error checking unique reference: {str(e)}")
                break

        return unique_reference

    def _create(self, data):
        """ Create product in PrestaShop """
        prestashop = self.binding.shop_id.backend_id._get_prestashop_client()
        try:
            result = prestashop.add('products', data)
            if isinstance(result, ET.Element):
                product_elem = result.find('.//product')
                if product_elem is not None:
                    id_elem = product_elem.find('id')
                    if id_elem is not None and id_elem.text:
                        # Lấy text từ CDATA section
                        product_id = id_elem.text.strip('[]!CDATA')
                        self.binding.prestashop_id = int(product_id)
                        self.binding.date_add = fields.Datetime.now()
                        _logger.info("Created product in PrestaShop with ID: %s", product_id)
                        return

            _logger.error("Could not find product ID in PrestaShop response")
        except Exception as e:
            _logger.error("Error creating product in PrestaShop: %s", str(e))
            raise

    def _update(self, data):
        """ Update product in PrestaShop """
        prestashop = self.binding.shop_id.backend_id._get_prestashop_client()
        try:
            prestashop.edit('products', data)
            self.binding.date_upd = fields.Datetime.now()
            _logger.info("Updated product in PrestaShop with ID: %s", self.binding.prestashop_id)

        except Exception as e:
            _logger.error("Error updating product in PrestaShop: %s", str(e))
            raise

    def _upload_images(self):
        prestashop = self.binding.shop_id.backend_id._get_prestashop_client()
        image = self.binding.odoo_id.image_1920

        if image:
            try:
                # Decode the base64 image
                image_binary = base64.b64decode(image)
                # Generate a safe filename
                filename = f"{self.binding.odoo_id.name.replace(' ', '_')}.jpg"
                # Prepare image data
                image_data = ('image', filename, image_binary)
                try:
                    try:
                        result = prestashop.encode_multipart_formdata([image_data])
                        if len(result) == 2:
                            headers, body = result
                            _logger.info("Received 2 values from encode_multipart_formdata")
                        else:
                            headers, content_type, body = result
                            headers['Content-Type'] = content_type

                    except TypeError:
                        result = prestashop.encode_multipart_formdata(image_data)
                        if len(result) == 2:
                            headers, body = result
                        else:
                            headers, content_type, body = result
                            headers['Content-Type'] = content_type

                except Exception as encode_error:
                    _logger.error(f"Error in multipart form data encoding: {encode_error}")
                    raise

                base_url = self.binding.shop_id.backend_id.url.rstrip('/')
                resource_url = f"{base_url}/api/images/products/{self.binding.prestashop_id}"

                # Execute upload
                try:
                    response = prestashop._execute(resource_url, 'POST', data=body, add_headers=headers)

                    if response.status_code == 200:
                        _logger.info(f"Successfully uploaded image for product ID: {self.binding.prestashop_id}")
                    else:
                        _logger.error(f"Image upload failed - Status: {response.status_code}")
                        _logger.error(f"Response content: {response.content}")

                except Exception as upload_error:
                    _logger.error(f"Upload execution error: {upload_error}")
                    raise

            except Exception as e:
                _logger.error(f"Comprehensive image upload error for product {self.binding.prestashop_id}: {str(e)}")
                raise

    def _update_stock(self, binding=None):
        """Update stock quantity in PrestaShop"""
        if not binding:
            binding = self.binding

        prestashop = binding.shop_id.backend_id._get_prestashop_client()

        try:
            # Kiểm tra nếu sản phẩm có biến thể
            if binding.attribute_line_ids:
                # Cập nhật kho cho từng biến thể
                for variant in binding.product_variant_ids:
                    # Tìm combination ID trên PrestaShop
                    combination_filters = {
                        'filter[id_product]': str(binding.prestashop_id),
                        'filter[reference]': str(variant.default_code or '')
                    }
                    try:
                        combinations = prestashop.get('combinations', options=combination_filters)
                        combination = combinations.find('.//combination')
                        if combination is not None:
                            combination_id = combination.get('id')

                            # Tìm stock_available cho combination
                            stock_filters = {
                                'filter[id_product]': str(binding.prestashop_id),
                                'filter[id_product_attribute]': str(combination_id)
                            }
                            stock_data = prestashop.get('stock_availables', options=stock_filters)
                            stock_available = stock_data.find('.//stock_available')

                            if stock_available is not None:
                                stock_id = stock_available.get('id')

                                # Tạo XML để cập nhật kho
                                stock_xml = ET.Element('prestashop')
                                stock_xml.set('xmlns:xlink', 'http://www.w3.org/1999/xlink')
                                stock = ET.SubElement(stock_xml, 'stock_available')

                                def create_cdata_element(parent, tag, value=''):
                                    elem = ET.SubElement(parent, tag)
                                    elem.text = f'<![CDATA[{value}]]>'
                                    return elem

                                # Thêm các trường bắt buộc
                                create_cdata_element(stock, 'id', stock_id)
                                create_cdata_element(stock, 'quantity', str(int(variant.qty_available)))

                                # Thêm các trường bổ sung
                                ET.SubElement(stock, 'id_product').text = str(binding.prestashop_id)
                                ET.SubElement(stock, 'id_product_attribute').text = str(combination_id)
                                ET.SubElement(stock, 'depends_on_stock').text = '0'
                                ET.SubElement(stock, 'out_of_stock').text = '1'
                                ET.SubElement(stock, 'id_shop').text = '1'

                                # Chuyển đổi thành string
                                xml_str = ET.tostring(stock_xml, encoding='utf-8', xml_declaration=True)
                                xml_str = xml_str.decode('utf-8').replace('&lt;![CDATA[', '<![CDATA[').replace(']]&gt;',
                                                                                                               ']]>')

                                # Cập nhật số lượng tồn kho
                                resource_path = f'stock_availables/{stock_id}'
                                prestashop.edit(resource_path, xml_str.encode('utf-8'))
                                _logger.info(
                                    f"Updated stock quantity for variant {variant.default_code} to {variant.qty_available}")

                    except Exception as e:
                        _logger.error(f"Error updating stock for variant {variant.default_code}: {str(e)}")
                        continue

            else:
                # Cập nhật kho cho sản phẩm không có biến thể
                filters = {'filter[id_product]': str(binding.prestashop_id)}
                stock_data = prestashop.get('stock_availables', options=filters)

                stock_available = stock_data.find('.//stock_available')
                if stock_available is not None:
                    stock_id = stock_available.get('id')

                    # Tạo XML cập nhật kho
                    stock_xml = ET.Element('prestashop')
                    stock_xml.set('xmlns:xlink', 'http://www.w3.org/1999/xlink')
                    stock = ET.SubElement(stock_xml, 'stock_available')

                    def create_cdata_element(parent, tag, value=''):
                        elem = ET.SubElement(parent, tag)
                        elem.text = f'<![CDATA[{value}]]>'
                        return elem

                    # Thêm các trường bắt buộc
                    create_cdata_element(stock, 'id', stock_id)
                    create_cdata_element(stock, 'quantity', str(int(binding.qty_available)))

                    # Thêm các trường bổ sung
                    ET.SubElement(stock, 'id_product').text = str(binding.prestashop_id)
                    ET.SubElement(stock, 'id_product_attribute').text = '0'
                    ET.SubElement(stock, 'depends_on_stock').text = '0'
                    ET.SubElement(stock, 'out_of_stock').text = '1'
                    ET.SubElement(stock, 'id_shop').text = '1'

                    # Chuyển đổi thành string
                    xml_str = ET.tostring(stock_xml, encoding='utf-8', xml_declaration=True)
                    xml_str = xml_str.decode('utf-8').replace('&lt;![CDATA[', '<![CDATA[').replace(']]&gt;', ']]>')

                    # Cập nhật số lượng tồn kho
                    resource_path = f'stock_availables/{stock_id}'
                    prestashop.edit(resource_path, xml_str.encode('utf-8'))
                    _logger.info(
                        f"Updated stock quantity for product {binding.prestashop_id} to {binding.qty_available}")

        except Exception as e:
            _logger.error(f"Error updating stock for product {binding.prestashop_id}: {str(e)}")
            raise
