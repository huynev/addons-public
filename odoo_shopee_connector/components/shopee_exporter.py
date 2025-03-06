# -*- coding: utf-8 -*-
from odoo.addons.component.core import Component
from odoo import fields
import base64
from io import BytesIO
from PIL import Image
import time
import random
import string

import logging

_logger = logging.getLogger(__name__)


class ShopeeExporter(Component):
    _name = 'shopee.exporter'
    _inherit = ['base.shopee.connector', 'base.exporter']
    _usage = 'record.exporter'
    _base_mapper_usage = 'export.mapper'

    def _get_data(self, binding):
        """Return the shopee data for export"""
        mapper = self.component(usage='export.mapper')
        return mapper.map_record(binding).values()

    def _update(self, data):
        """Update a record on shopee"""
        return self.backend_adapter.update_product(data)

    def _create(self, data):
        """Create a record on shopee"""
        return self.backend_adapter.create_product(data)

    def run(self, binding):
        """Run the export"""
        self.binding = binding
        self.external_id = binding.external_id

        try:
            if self.external_id:
                data = self._get_data(binding)
                self._update(data)
            else:
                data = self._get_data(binding)
                result = self._create(data)
                if result and not result.get('error') and result.get('item_id'):
                    self.binder.bind(result.get('item_id'), binding)
            binding.write({'sync_date': fields.Datetime.now()})
            return True
        except Exception as e:
            _logger.error(str(e))
            raise


class ShopeeTemplateExporter(Component):
    _name = 'shopee.template.exporter'
    _inherit = ['base.shopee.connector', 'base.exporter']
    _usage = 'product.exporter'
    _apply_on = 'shopee.product.template'
    _base_mapper_usage = 'export.mapper'

    def _get_data(self, binding):
        """Return the shopee data for export"""
        mapper = self.component(usage='export.mapper')
        return mapper.map_record(binding).values()

    def _update(self, data):
        """Update a record on shopee"""
        return self.backend_adapter.update_product(data)

    def _create(self, data):
        """Create a record on shopee"""
        return self.backend_adapter.create_product(data)

    def _prepare_image_data(self, binding):
        """Chuẩn bị dữ liệu hình ảnh từ sản phẩm"""
        if binding.odoo_id.image_1920:
            image_data = BytesIO(base64.b64decode(binding.odoo_id.image_1920))
            image = Image.open(image_data)

            # Kiểm tra và điều chỉnh kích thước hình ảnh
            width, height = image.size
            if width < 300 or height < 300:
                image = image.resize((max(300, width), max(300, height)))
            elif width > 4000 or height > 4000:
                image = image.resize((min(4000, width), min(4000, height)))

            # Chuyển đổi sang JPEG và giảm dung lượng nếu cần
            output = BytesIO()
            image.convert('RGB').save(output, format='JPEG', quality=95, optimize=True)
            image_data = base64.b64encode(output.getvalue()).decode('utf-8')
            image_name = f"{binding.odoo_id.default_code or 'product'}.jpg"

            if len(image_data) > 5 * 1024 * 1024:  # Nếu lớn hơn 5MB
                _logger.warning("Image size exceeds 5MB limit. Reducing quality.")
                output = BytesIO()
                image.convert('RGB').save(output, format='JPEG', quality=80, optimize=True)
                image_data = base64.b64encode(output.getvalue()).decode('utf-8')

            return image_data, image_name
        return None, None

    def _has_variants(self, binding):
        """Kiểm tra xem sản phẩm có biến thể hay không"""
        return binding.has_variants

    def _compare_tier_variations(self, existing_variations, new_variations):
        """
        So sánh cấu trúc tier variations hiện tại với cấu trúc mới

        :param existing_variations: Cấu trúc tier variations hiện có từ Shopee
        :param new_variations: Cấu trúc tier variations mới từ Odoo
        :return: True nếu cần cập nhật, False nếu không cần
        """
        # Nếu không có dữ liệu cũ hoặc không có dữ liệu mới, cần cập nhật
        if not existing_variations or not new_variations:
            return True

        # Nếu số lượng tier variations khác nhau, cần cập nhật
        if len(existing_variations) != len(new_variations):
            return True

        # So sánh tên của từng tier variation
        for i, (existing, new) in enumerate(zip(existing_variations, new_variations)):
            if existing.get('name') != new.get('name'):
                return True

            # So sánh số lượng tùy chọn
            existing_options = existing.get('option_list', [])
            new_options = new.get('options', [])

            if len(existing_options) != len(new_options):
                return True

            # So sánh từng tùy chọn (chỉ so sánh tên, không so sánh hình ảnh)
            for j, (e_opt, n_opt) in enumerate(zip(existing_options, new_options)):
                e_name = e_opt.get('option', '')
                n_name = n_opt if isinstance(n_opt, str) else n_opt.get('option', '')

                if e_name != n_name:
                    return True

        # Nếu tất cả đều giống nhau, không cần cập nhật
        return False

    def _prepare_tier_variations(self, binding):
        """
        Chuẩn bị thông tin tier variations từ sản phẩm Odoo
        Đảm bảo luôn có ít nhất một tier variation mặc định nếu không có thuộc tính
        """
        product_tmpl = binding.odoo_id
        attribute_lines = product_tmpl.attribute_line_ids

        # Kiểm tra nếu không có thuộc tính, tạo một tier variation mặc định
        if not attribute_lines:
            return [{
                'name': 'Loại',
                'options': [{'option': 'Mặc định'}]
            }]

        # Shopee chỉ hỗ trợ tối đa 2 tier variations
        tier_variations = []

        # Lấy tối đa 2 thuộc tính đầu tiên
        for idx, attr_line in enumerate(attribute_lines[:2]):
            options = []
            for value in attr_line.value_ids:
                option = {
                    'option': value.name
                }
                # Nếu có hình ảnh và đây là thuộc tính đầu tiên, upload lên Shopee
                if idx == 0 and hasattr(value, 'image') and value.image:
                    try:
                        # Xử lý hình ảnh thuộc tính
                        image_data = base64.b64encode(value.image).decode('utf-8')
                        image_result = self.backend_adapter.upload_image(image_data=image_data)

                        if not image_result.get('error') and image_result.get('response', {}):
                            image_id = (
                                    image_result.get('response', {})
                                    .get('response', {})
                                    .get('image_info', {})
                                    .get('image_id') or
                                    image_result.get('response', {})
                                    .get('response', {})
                                    .get('image_info_list', [{}])[0]
                                    .get('image_info', {})
                                    .get('image_id')
                            )
                            if image_id:
                                option['image_id'] = image_id
                    except Exception as e:
                        _logger.warning(f"Error uploading attribute image: {str(e)}")

                options.append(option)

            # Đảm bảo rằng có ít nhất một tùy chọn
            if not options:
                options = [{'option': 'Mặc định'}]

            tier_variations.append({
                'name': attr_line.attribute_id.name,
                'options': options
            })

        # Nếu không có tier variations, tạo một tier variation mặc định
        if not tier_variations:
            tier_variations = [{
                'name': 'Loại',
                'options': [{'option': 'Mặc định'}]
            }]

        return tier_variations

    def _format_tier_variations_for_api(self, tier_variations):
        """
        Chuyển đổi cấu trúc tier variations sang định dạng phù hợp cho API

        :param tier_variations: Cấu trúc tier variations từ _prepare_tier_variations
        :return: Cấu trúc tier variations phù hợp với API Shopee
        """
        formatted_tier_variations = []

        for variation in tier_variations:
            # Chuyển đổi options thành option_list
            option_list = []
            for opt in variation['options']:
                if isinstance(opt, str):
                    option_data = {'option': opt}
                else:
                    option_data = {'option': opt.get('option', '')}
                    if 'image_id' in opt:
                        option_data['image'] = {'image_id': opt['image_id']}

                option_list.append(option_data)

            # Thêm vào danh sách đã định dạng
            formatted_tier_variations.append({
                'name': variation['name'],
                'option_list': option_list
            })

        return formatted_tier_variations

    def _map_odoo_variants_to_shopee_models(self, binding, tier_variations, existing_models=None):
        """
        Ánh xạ các biến thể của Odoo sang mô hình biến thể của Shopee
        Với cách xử lý đảm bảo SKU không bị trùng lặp và cấu trúc tier_index nhất quán

        :param binding: Binding record
        :param tier_variations: Cấu trúc tier variations
        :param existing_models: Danh sách models đã tồn tại trên Shopee (nếu có)
        :return: Danh sách models cho Shopee
        """
        product_tmpl = binding.odoo_id
        attribute_lines = product_tmpl.attribute_line_ids[:2]  # Lấy tối đa 2 thuộc tính
        existing_tier_structure = None  # Cấu trúc tier_index mẫu từ models hiện có

        # Tạo mapping từ model_id (nếu có) đến variant
        existing_model_map = {}
        existing_sku_set = set()  # Tập hợp để theo dõi các SKU đã tồn tại

        if existing_models:
            for model in existing_models:
                if 'tier_index' in model:
                    tier_index_tuple = tuple(model.get('tier_index', []))
                    if tier_index_tuple:
                        existing_model_map[tier_index_tuple] = model.get('model_id')

                    # Lưu lại cấu trúc tier_index mẫu
                    if existing_tier_structure is None and model.get('tier_index'):
                        existing_tier_structure = model.get('tier_index')

                # Lưu lại SKU hiện có để tránh trùng lặp
                if model.get('model_sku'):
                    existing_sku_set.add(model.get('model_sku'))

        # Chuẩn bị danh sách model
        models = []
        processed_skus = set()  # Tập hợp để theo dõi các SKU đã xử lý trong phiên này

        # Nếu không có thuộc tính hoặc không có tier_variations, tạo một model mặc định
        if not attribute_lines or not tier_variations:
            # Tạo SKU duy nhất cho model mặc định
            if binding.odoo_id.default_code:
                model_sku = binding.odoo_id.default_code
            else:
                timestamp = int(time.time()) % 10000
                random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
                model_sku = f"SP-{binding.id}-{timestamp}-{random_str}"

            # Kiểm tra xem SKU đã tồn tại chưa
            while model_sku in existing_sku_set or model_sku in processed_skus:
                timestamp = int(time.time()) % 10000
                random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
                model_sku = f"SP-{binding.id}-{timestamp}-{random_str}"

            # Thêm vào danh sách SKU đã xử lý
            processed_skus.add(model_sku)

            # Xác định tier_index mặc định dựa trên cấu trúc hiện có (nếu có)
            default_tier_index = [0]
            if existing_tier_structure:
                default_tier_index = [0] * len(existing_tier_structure)

            # Tạo model mặc định cho biến thể đầu tiên
            main_variant = product_tmpl.product_variant_ids[0]
            model_data = {
                'tier_index': default_tier_index,
                'original_price': main_variant.lst_price,
                'model_sku': model_sku,
                'seller_stock': [
                    {
                        'stock': int(main_variant.qty_available)
                    }
                ]
            }

            # Thêm thông tin khối lượng nếu có
            if hasattr(main_variant, 'weight') and main_variant.weight:
                model_data['weight'] = main_variant.weight

            models.append(model_data)

            # Cập nhật variant_binding nếu đã có
            for variant_binding in binding.variant_ids:
                if variant_binding.odoo_id.id == main_variant.id:
                    variant_binding.write({
                        'model_sku': model_sku,
                        'tier_index': str(default_tier_index)
                    })
                    break

            return models

        # Xây dựng bảng ánh xạ từ giá trị thuộc tính đến vị trí trong tier_variation
        attribute_value_map = {}
        for tier_idx, attr_line in enumerate(attribute_lines):
            attribute_value_map[attr_line.attribute_id.id] = {}
            for option_idx, value in enumerate(attr_line.value_ids):
                attribute_value_map[attr_line.attribute_id.id][value.id] = option_idx

        # Tạo tiền tố SKU cho sản phẩm này
        timestamp = int(time.time()) % 10000
        random_suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
        prefix = binding.odoo_id.default_code or f"SP-{timestamp}-{random_suffix}"

        # Xử lý trường hợp có biến thể
        for variant_idx, variant in enumerate(product_tmpl.product_variant_ids):
            # Tạo tier_index từ giá trị thuộc tính của biến thể
            tier_index = []
            valid_variant = True

            for attr_line in attribute_lines:
                attr_id = attr_line.attribute_id.id
                # Lấy giá trị thuộc tính của biến thể này
                attr_values = variant.product_template_attribute_value_ids.filtered(
                    lambda x: x.attribute_id.id == attr_id
                )

                # Nếu không tìm thấy giá trị thuộc tính, đánh dấu là không hợp lệ
                if not attr_values:
                    valid_variant = False
                    break

                value_id = attr_values.product_attribute_value_id.id

                # Nếu không tìm thấy giá trị trong mapping, đánh dấu là không hợp lệ
                if attr_id not in attribute_value_map or value_id not in attribute_value_map[attr_id]:
                    valid_variant = False
                    break

                tier_index.append(attribute_value_map[attr_id][value_id])

            # Đảm bảo tier_index có độ dài phù hợp với tier_variations
            if len(tier_index) < len(tier_variations):
                # Nếu thiếu, thêm giá trị 0 vào cuối
                tier_index.extend([0] * (len(tier_variations) - len(tier_index)))
            elif len(tier_index) > len(tier_variations):
                # Nếu thừa, cắt bớt
                tier_index = tier_index[:len(tier_variations)]

            # Nếu sử dụng existing_tier_structure, đảm bảo tier_index có cùng độ dài
            if existing_tier_structure and len(tier_index) != len(existing_tier_structure):
                if len(tier_index) < len(existing_tier_structure):
                    tier_index.extend([0] * (len(existing_tier_structure) - len(tier_index)))
                else:
                    tier_index = tier_index[:len(existing_tier_structure)]

            # Bỏ qua biến thể không hợp lệ
            if not valid_variant:
                continue

            # Kiểm tra xem biến thể này đã tồn tại trên Shopee chưa
            tier_index_tuple = tuple(tier_index)
            model_id = existing_model_map.get(tier_index_tuple)

            # Xử lý SKU của biến thể để đảm bảo không trùng lặp
            if variant.default_code:
                # Nếu variant có default_code, ưu tiên sử dụng
                model_sku = variant.default_code
            else:
                # Tạo SKU từ prefix và thông tin biến thể
                variant_suffix = '-'.join(map(str, tier_index))
                model_sku = f"{prefix}-{variant_suffix}"

            # Kiểm tra trùng lặp với SKU đã tồn tại và với SKU đã xử lý trong phiên này
            original_sku = model_sku
            counter = 1
            while model_sku in existing_sku_set or model_sku in processed_skus:
                model_sku = f"{original_sku}-{counter}"
                counter += 1

            # Thêm vào tập hợp SKU đã xử lý
            processed_skus.add(model_sku)

            # Tìm hoặc tạo binding cho variant này
            variant_binding = self.env['shopee.product.product'].search([
                ('odoo_id', '=', variant.id),
                ('backend_id', '=', binding.backend_id.id),
                ('shopee_template_id', '=', binding.id)
            ], limit=1)

            # Nếu không có binding, tạo mới
            if not variant_binding:
                variant_binding = self.env['shopee.product.product'].create({
                    'backend_id': binding.backend_id.id,
                    'odoo_id': variant.id,
                    'shopee_template_id': binding.id,
                    'shopee_name': variant.display_name,
                    'shopee_price': variant.lst_price,
                    'model_sku': model_sku,
                    'tier_index': str(tier_index)
                })
            else:
                # Cập nhật binding hiện có
                variant_binding.write({
                    'model_sku': model_sku,
                    'tier_index': str(tier_index)
                })

            # Chuẩn bị thông tin model
            model_data = {
                'tier_index': tier_index,
                'original_price': variant.lst_price,
                'model_sku': model_sku,
                'seller_stock': [
                    {
                        'stock': int(variant.qty_available)
                    }
                ]
            }

            # Thêm model_id nếu đã tồn tại
            if model_id:
                model_data['model_id'] = model_id
                # Cập nhật model_id vào variant binding
                if variant_binding:
                    variant_binding.write({'model_id': model_id})

            # Thêm thông tin khối lượng nếu có
            if hasattr(variant, 'weight') and variant.weight:
                model_data['weight'] = variant.weight

            models.append(model_data)

        # Nếu không có models nào được tạo, tạo model mặc định
        if not models:
            default_tier_index = [0] * len(tier_variations)
            if existing_tier_structure:
                default_tier_index = [0] * len(existing_tier_structure)

            # Tạo SKU duy nhất
            timestamp = int(time.time()) % 10000
            random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
            model_sku = f"SP-DEFAULT-{binding.id}-{timestamp}-{random_str}"

            models.append({
                'tier_index': default_tier_index,
                'original_price': product_tmpl.list_price,
                'model_sku': model_sku,
                'seller_stock': [
                    {
                        'stock': int(product_tmpl.qty_available)
                    }
                ]
            })

        return models

    def run(self, binding):
        """Run the export"""
        self.binding = binding
        self.external_id = binding.external_id

        try:
            binding.write({
                'shopee_sync_status': 'syncing',
                'shopee_sync_message': 'Exporting product to Shopee...'
            })

            data = self._get_data(binding)
            data = self._validate_data(data)

            # Xử lý hình ảnh sản phẩm nếu cần
            if not data.get('images'):
                image_data, image_name = self._prepare_image_data(binding)
                if image_data:
                    # Upload hình ảnh lên Shopee
                    image_result = self.backend_adapter.upload_image(image_data)

                    # Kiểm tra kết quả upload ảnh
                    if not image_result.get('error'):
                        # Lấy image_id từ response
                        parsed_response = image_result.get('response', {})
                        image_id = (
                                parsed_response.get('response', {})
                                .get('image_info', {})
                                .get('image_id') or
                                parsed_response.get('response', {})
                                .get('response', {})
                                .get('image_info_list', [{}])[0]
                                .get('image_info', {})
                                .get('image_id')
                        )

                        if image_id:
                            data['images'] = [image_id]
                        else:
                            raise ValueError("Failed to extract image_id from Shopee response")
                    else:
                        error_msg = image_result.get('message', 'Unknown error')
                        raise ValueError(f"Failed to upload product image to Shopee: {error_msg}")

            # Kiểm tra sản phẩm có biến thể hay không
            has_variants = self._has_variants(binding)

            # Tạo hoặc cập nhật sản phẩm
            if self.external_id:
                # Đã tồn tại, cập nhật sản phẩm
                update_result = self._update(data)

                # Kiểm tra xem có lỗi liên quan đến tier_variation không
                has_tier_error = False
                if update_result and update_result.get('error'):
                    error_message = update_result.get('message', '')
                    if 'tier_variation' in error_message or 'init_tier_variation' in error_message:
                        _logger.warning(f"Product needs tier variation structure: {error_message}")
                        has_tier_error = True

                # Nếu có biến thể hoặc có lỗi tier_variation, thiết lập tier variations
                if has_variants or has_tier_error:
                    # Lấy thông tin biến thể hiện tại của sản phẩm
                    try:
                        model_list = self.backend_adapter.get_model_list(self.external_id)
                        # Lấy dữ liệu tier variations hiện tại và models hiện tại
                        existing_tier_variations = model_list.get('tier_variation', [])
                        existing_models = model_list.get('model', [])
                    except Exception as e:
                        _logger.warning(f"Error getting model list: {str(e)}")
                        existing_tier_variations = []
                        existing_models = []

                    # Chuẩn bị dữ liệu tier variations mới
                    new_tier_variations = self._prepare_tier_variations(binding)

                    # Nếu không có tier variations nhưng cần (vì lỗi), tạo một tier variation mặc định
                    if not new_tier_variations and has_tier_error:
                        new_tier_variations = [{
                            'name': 'Loại',
                            'options': [{'option': 'Mặc định'}]
                        }]

                    # So sánh cấu trúc tier variations hoặc kiểm tra lỗi
                    need_update = (has_tier_error or
                                   not existing_tier_variations or
                                   self._compare_tier_variations(existing_tier_variations, new_tier_variations))

                    if need_update:
                        # Nếu cấu trúc khác nhau hoặc có lỗi, khởi tạo lại tier variations
                        _logger.info(f"Updating tier variations for product {self.external_id}")
                        formatted_variations = self._format_tier_variations_for_api(new_tier_variations)

                        # Chuẩn bị models
                        models = self._map_odoo_variants_to_shopee_models(binding, new_tier_variations, existing_models)

                        # Gọi API init_tier_variation để thiết lập cấu trúc biến thể
                        init_result = self.backend_adapter.init_tier_variation(self.external_id, formatted_variations,
                                                                               models)

                        if init_result.get('error'):
                            _logger.error(f"Error initializing tier variations: {init_result.get('error')}")
                            raise ValueError(f"Error initializing tier variations: {init_result.get('error')}")
                    else:
                        # Nếu cấu trúc giống nhau, chỉ cập nhật thông tin models
                        _logger.info(f"Updating models for product {self.external_id} without changing tier variations")
                        models = self._map_odoo_variants_to_shopee_models(binding, new_tier_variations, existing_models)
                        update_result = self.backend_adapter.update_tier_variation(self.external_id, models)

                        # if update_result.get('error'):
                        #     _logger.error(f"Error updating models: {update_result.get('error')}")
                        #     # Nếu có lỗi khi cập nhật, thử khởi tạo lại tier variations
                        #     _logger.info(f"Trying to reinitialize tier variations for product {self.external_id}")
                        #     init_result = self.backend_adapter.init_tier_variation(self.external_id,
                        #                                                            formatted_variations, models)
                        #     if init_result.get('error'):
                        #         _logger.error(f"Error reinitializing tier variations: {init_result.get('error')}")
            else:
                # Tạo mới sản phẩm
                result = self._create(data)
                if result and result.get('response', {}).get('item_id'):
                    item_id = result['response']['item_id']
                    self.binder.bind(item_id, binding)

                    # Tạo biến thể bindings nếu chưa có
                    if has_variants and not binding.variant_ids:
                        binding.create_variant_bindings()

                    # Chuẩn bị dữ liệu tier variations
                    new_tier_variations = self._prepare_tier_variations(binding)
                    formatted_variations = self._format_tier_variations_for_api(new_tier_variations)

                    # Chuẩn bị models
                    models = self._map_odoo_variants_to_shopee_models(binding, new_tier_variations)

                    # Gọi API init_tier_variation để thiết lập cấu trúc biến thể
                    init_result = self.backend_adapter.init_tier_variation(item_id, formatted_variations, models)

                    if init_result.get('error'):
                        _logger.error(f"Error initializing tier variations: {init_result.get('error')}")
                        raise ValueError(f"Error initializing tier variations: {init_result.get('error')}")

                    # Cập nhật model_id vào các variant bindings từ trường model trong response
                    if init_result.get('response', {}).get('model'):
                        model_list = init_result['response']['model']
                        for model_info in model_list:
                            tier_index = model_info.get('tier_index')
                            model_id = model_info.get('model_id')
                            model_sku = model_info.get('model_sku')

                            if tier_index is not None and model_id:
                                # Tìm variant binding phù hợp để cập nhật
                                tier_index_str = str(tier_index)
                                for variant_binding in binding.variant_ids:
                                    # So sánh bằng model_sku (ưu tiên)
                                    if variant_binding.model_sku == model_sku:
                                        variant_binding.write({'model_id': model_id})
                                        _logger.info(f"Updated model_id {model_id} for variant with SKU {model_sku}")
                                        break
                                    # Hoặc so sánh bằng tier_index
                                    elif variant_binding.tier_index and eval(variant_binding.tier_index) == tier_index:
                                        variant_binding.write({
                                            'model_id': model_id,
                                            'model_sku': model_sku  # Cập nhật lại cả model_sku từ phản hồi
                                        })
                                        _logger.info(
                                            f"Updated model_id {model_id} for variant with tier_index {tier_index_str}")
                                        break
                                else:
                                    # Nếu không tìm thấy binding phù hợp, có thể tạo mới
                                    # Tìm product.product tương ứng với tier_index
                                    found_variant = False
                                    for variant in binding.odoo_id.product_variant_ids:
                                        variant_tier_index = []
                                        for attr_line in binding.odoo_id.attribute_line_ids[:2]:
                                            attr_id = attr_line.attribute_id.id
                                            # Lấy giá trị thuộc tính của biến thể này
                                            attr_values = variant.product_template_attribute_value_ids.filtered(
                                                lambda x: x.attribute_id.id == attr_id
                                            )
                                            if attr_values and attr_values.product_attribute_value_id:
                                                # Tìm vị trí của giá trị trong option_list
                                                for idx, value in enumerate(attr_line.value_ids):
                                                    if value.id == attr_values.product_attribute_value_id.id:
                                                        variant_tier_index.append(idx)
                                                        break

                                        # So sánh tier_index
                                        if variant_tier_index == tier_index:
                                            # Tạo binding mới
                                            self.env['shopee.product.product'].create({
                                                'backend_id': binding.backend_id.id,
                                                'odoo_id': variant.id,
                                                'shopee_template_id': binding.id,
                                                'shopee_name': variant.display_name,
                                                'shopee_price': variant.lst_price,
                                                'model_id': model_id,
                                                'model_sku': model_sku,
                                                'tier_index': str(tier_index)
                                            })
                                            _logger.info(
                                                f"Created new variant binding with model_id {model_id} for tier_index {tier_index}")
                                            found_variant = True
                                            break

                                    if not found_variant:
                                        _logger.warning(
                                            f"Could not find matching product variant for tier_index {tier_index}")

             # Cập nhật trạng thái đồng bộ
            binding.write({
                'sync_date': fields.Datetime.now(),
                'shopee_sync_status': 'synced',
                'shopee_sync_message': f"Successfully exported to Shopee at {fields.Datetime.now()}"
            })
            return True
        except Exception as e:
            error_msg = str(e)
            _logger.error(error_msg)
            # Cập nhật trạng thái lỗi
            binding.write({
                'shopee_sync_status': 'failed',
                'shopee_sync_message': f"Export failed: {error_msg}"
            })
            raise

    def _validate_data(self, data):
        """Validate the data to create records on shopee"""
        # Process category_id to ensure it's an integer
        if 'category_id' in data:
            if isinstance(data['category_id'], bool) or not data['category_id']:
                # Nếu không có danh mục, thử lấy gợi ý từ Shopee
                data = self._try_get_category_recommendation(data)
            else:
                try:
                    data['category_id'] = int(data['category_id'])
                except (ValueError, TypeError):
                    _logger.warning(f"Invalid category_id: {data['category_id']}")
                    # Nếu danh mục không hợp lệ, thử lấy gợi ý từ Shopee
                    data = self._try_get_category_recommendation(data)
        else:
            # Nếu không có trường category_id, thử lấy gợi ý từ Shopee
            data = self._try_get_category_recommendation(data)

        #for test
        data['category_id'] = 100732

        if len(data['description']) < 25:
            data['description'] = "Sản phẩm chất lượng cao, được thiết kế chuyên nghiệp, đáp ứng nhu cầu sử dụng của khách hàng. Với thiết kế tinh tế và chức năng ưu việt, sản phẩm mang đến trải nghiệm tối ưu."
        # Cắt mô tả nếu quá dài
        data['description'] = data['description'][:1000]

        # Process other numeric fields
        if 'price' in data:
            data['price'] = float(data['price'])

        if 'stock' in data:
            data['stock'] = int(data['stock'])

        # Thêm các trường bắt buộc
        if 'weight' not in data or not data['weight']:
            data['weight'] = 1.0
        else:
            data['weight'] = float(data['weight'])

        if 'package_height' not in data or not data['package_height']:
            data['package_height'] = 10
        else:
            data['package_height'] = float(data['package_height'])

        if 'package_length' not in data or not data['package_length']:
            data['package_length'] = 10
        else:
            data['package_length'] = float(data['package_length'])

        if 'package_width' not in data or not data['package_width']:
            data['package_width'] = 10
        else:
            data['package_width'] = float(data['package_width'])

        # Xử lý item_sku để đảm bảo không trùng lặp
        sku = data.get('item_sku', '')
        if self.external_id:
            # Nếu đang cập nhật, không cần thay đổi SKU
            if not sku or sku == '-':
                # Nhưng nếu SKU trống, tạo SKU mới
                timestamp = int(time.time()) % 10000
                random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
                data['item_sku'] = f"SKU-{self.binding.id}-{timestamp}-{random_str}"
        else:
            # Nếu đang tạo mới, kiểm tra và đảm bảo SKU duy nhất
            if not sku or sku == '-':
                timestamp = int(time.time()) % 10000
                random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
                data['item_sku'] = f"SKU-{self.binding.id}-{timestamp}-{random_str}"

        # Đảm bảo item status là hợp lệ
        if 'item_status' not in data or data['item_status'] not in ['NORMAL', 'UNLIST']:
            data['item_status'] = 'UNLIST'

        # Remove None/False values for API compatibility
        for key in list(data.keys()):
            if data[key] is None or (isinstance(data[key], bool) and not data[key]):
                del data[key]

        return data

    def _try_get_category_recommendation(self, data):
        """Thử lấy gợi ý danh mục từ Shopee"""
        try:
            item_name = self.binding.shopee_name or self.binding.odoo_id.name

            if not item_name:
                return data

            params = {'item_name': item_name}

            # Gọi API để lấy gợi ý danh mục
            result = self.backend_adapter.call('/api/v2/product/category_recommend', 'GET', params=params)

            if result and not result.get('error'):
                recommended_categories = result.get('response', {}).get('category_id', [])
                if recommended_categories:
                    # Dùng danh mục đầu tiên được gợi ý
                    data['category_id'] = int(recommended_categories[0])

                    # Cập nhật lại binding để lần sau không cần gợi ý lại
                    self.binding.with_context(connector_no_export=True).write({
                        'shopee_category_id': str(recommended_categories[0])
                    })

                    # Tìm danh mục tương ứng trong hệ thống
                    category = self.env['shopee.category'].search([
                        ('backend_id', '=', self.backend_record.id),
                        ('shopee_category_id', '=', str(recommended_categories[0]))
                    ], limit=1)

                    if category:
                        self.binding.with_context(connector_no_export=True).write({
                            'shopee_category': category.id
                        })

                    _logger.info("Applied recommended category ID %s for product: %s",
                                 recommended_categories[0], self.binding.shopee_name or self.binding.odoo_id.name)

        except Exception as e:
            _logger.warning("Failed to get category recommendation: %s", str(e))

        return data

class ShopeeVariantExporter(Component):
    _name = 'shopee.variant.exporter'
    _inherit = ['base.shopee.connector', 'base.exporter']
    _usage = 'variant.exporter'
    _apply_on = 'shopee.product.product'
    _base_mapper_usage = 'export.mapper'

    def run(self, binding):
        """Export a variant to Shopee"""
        self.binding = binding
        self.external_id = binding.external_id

        # Kiểm tra xem có template không
        if not binding.shopee_template_id or not binding.shopee_template_id.external_id:
            raise ValueError("Product template must be exported to Shopee first")

        # Lấy thông tin template
        template = binding.shopee_template_id
        template_id = template.external_id

        try:
            # Lấy thông tin models hiện tại
            model_list = self.backend_adapter.get_model_list(template_id)
            existing_models = model_list.get('model', [])

            # Chuẩn bị dữ liệu cho model
            if binding.tier_index:
                try:
                    # Chuyển string thành list
                    tier_index = eval(binding.tier_index)
                except:
                    tier_index = [0]
            else:
                tier_index = [0]

            model_data = {
                'tier_index': tier_index,
                'original_price': binding.odoo_id.lst_price,
                'model_sku': binding.model_sku or binding.odoo_id.default_code or f"SKU-{binding.id}-{int(time.time()) % 10000}",
                'seller_stock': [
                    {
                        'stock': int(binding.odoo_id.qty_available)
                    }
                ]
            }

            # Thêm model_id nếu đã có
            if binding.model_id:
                model_data['model_id'] = binding.model_id

            # Thêm thông tin khối lượng nếu có
            if hasattr(binding.odoo_id, 'weight') and binding.odoo_id.weight:
                model_data['weight'] = binding.odoo_id.weight

            # Cập nhật model
            result = self.backend_adapter.update_tier_variation(template_id, [model_data])

            if result.get('error'):
                _logger.error(f"Error updating variant: {result.get('error')}")
                raise ValueError(f"Error updating variant: {result.get('message', '')}")

            binding.write({'sync_date': fields.Datetime.now()})
            return True
        except Exception as e:
            _logger.error(str(e))
            raise

# class ShopeeProductExporter(Component):
#     _name = 'shopee.product.exporter'
#     _inherit = ['base.shopee.connector', 'base.exporter']
#     _usage = 'product.exporter'
#     _apply_on = 'shopee.product.template'
#     _base_mapper_usage = 'export.mapper'
#
#     def _get_data(self, binding):
#         """Return the shopee data for export"""
#         mapper = self.component(usage='export.mapper')
#         return mapper.map_record(binding).values()
#
#     def _update(self, data):
#         """Update a record on shopee"""
#         return self.backend_adapter.update_product(data)
#
#     def _create(self, data):
#         """Create a record on shopee"""
#         return self.backend_adapter.create_product(data)
#
#     def _prepare_image_data(self, binding):
#         """Chuẩn bị dữ liệu hình ảnh từ sản phẩm"""
#         if binding.odoo_id.image_1920:
#             image_data = BytesIO(base64.b64decode(binding.odoo_id.image_1920))
#             image = Image.open(image_data)
#
#             # Kiểm tra và điều chỉnh kích thước hình ảnh
#             width, height = image.size
#             if width < 300 or height < 300:
#                 image = image.resize((max(300, width), max(300, height)))
#             elif width > 4000 or height > 4000:
#                 image = image.resize((min(4000, width), min(4000, height)))
#
#             # Chuyển đổi sang JPEG và giảm dung lượng nếu cần
#             output = BytesIO()
#             image.convert('RGB').save(output, format='JPEG', quality=95, optimize=True)
#             image_data = base64.b64encode(output.getvalue()).decode('utf-8')
#             image_name = f"{binding.odoo_id.default_code or 'product'}.jpg"
#             return image_data, image_name
#
#             if len(image_data) > 5 * 1024 * 1024:  # Nếu lớn hơn 5MB
#                 raise UserError(_("Image size exceeds 5MB limit. Please use a smaller image."))
#         return None, None
#
#     def _has_variants(self, binding):
#         """Kiểm tra xem sản phẩm có biến thể hay không"""
#         product_tmpl = binding.odoo_id.product_tmpl_id
#         return product_tmpl.product_variant_count > 1
#
#     def _compare_tier_variations(self, existing_variations, new_variations):
#         """
#         So sánh cấu trúc tier variations hiện tại với cấu trúc mới
#
#         :param existing_variations: Cấu trúc tier variations hiện có từ Shopee
#         :param new_variations: Cấu trúc tier variations mới từ Odoo
#         :return: True nếu cần cập nhật, False nếu không cần
#         """
#         # Nếu không có dữ liệu cũ hoặc không có dữ liệu mới, cần cập nhật
#         if not existing_variations or not new_variations:
#             return True
#
#         # Nếu số lượng tier variations khác nhau, cần cập nhật
#         if len(existing_variations) != len(new_variations):
#             return True
#
#         # So sánh tên của từng tier variation
#         for i, (existing, new) in enumerate(zip(existing_variations, new_variations)):
#             if existing.get('name') != new.get('name'):
#                 return True
#
#             # So sánh số lượng tùy chọn
#             existing_options = existing.get('option_list', [])
#             new_options = new.get('options', [])
#
#             if len(existing_options) != len(new_options):
#                 return True
#
#             # So sánh từng tùy chọn (chỉ so sánh tên, không so sánh hình ảnh)
#             for j, (e_opt, n_opt) in enumerate(zip(existing_options, new_options)):
#                 e_name = e_opt.get('option', '')
#                 n_name = n_opt if isinstance(n_opt, str) else n_opt.get('option', '')
#
#                 if e_name != n_name:
#                     return True
#
#         # Nếu tất cả đều giống nhau, không cần cập nhật
#         return False
#
#     def _prepare_tier_variations(self, binding):
#         """Chuẩn bị thông tin tier variations từ sản phẩm Odoo"""
#         product_tmpl = binding.odoo_id.product_tmpl_id
#         attribute_lines = product_tmpl.attribute_line_ids
#
#         # Shopee chỉ hỗ trợ tối đa 2 tier variations
#         tier_variations = []
#
#         # Lấy tối đa 2 thuộc tính đầu tiên
#         for idx, attr_line in enumerate(attribute_lines[:2]):
#             options = []
#             for value in attr_line.value_ids:
#                 option = {
#                     'option': value.name
#                 }
#                 # Nếu có hình ảnh và đây là thuộc tính đầu tiên, upload lên Shopee
#                 if idx == 0 and hasattr(value, 'image') and value.image:
#                     try:
#                         # Xử lý hình ảnh thuộc tính
#                         image_data = base64.b64encode(value.image).decode('utf-8')
#                         image_result = self.backend_adapter.upload_image(image_data=image_data)
#
#                         if not image_result.get('error') and image_result.get('response', {}):
#                             image_id = (
#                                     image_result.get('response', {})
#                                     .get('response', {})
#                                     .get('image_info', {})
#                                     .get('image_id') or
#                                     image_result.get('response', {})
#                                     .get('response', {})
#                                     .get('image_info_list', [{}])[0]
#                                     .get('image_info', {})
#                                     .get('image_id')
#                             )
#                             if image_id:
#                                 option['image_id'] = image_id
#                     except Exception as e:
#                         _logger.warning(f"Error uploading attribute image: {str(e)}")
#
#                 options.append(option)
#
#             tier_variations.append({
#                 'name': attr_line.attribute_id.name,
#                 'options': options
#             })
#
#         return tier_variations
#
#     def _format_tier_variations_for_api(self, tier_variations):
#         """
#         Chuyển đổi cấu trúc tier variations sang định dạng phù hợp cho API
#
#         :param tier_variations: Cấu trúc tier variations từ _prepare_tier_variations
#         :return: Cấu trúc tier variations phù hợp với API Shopee
#         """
#         formatted_tier_variations = []
#
#         for variation in tier_variations:
#             # Chuyển đổi options thành option_list
#             option_list = []
#             for opt in variation['options']:
#                 if isinstance(opt, str):
#                     option_data = {'option': opt}
#                 else:
#                     option_data = {'option': opt.get('option', '')}
#                     if 'image_id' in opt:
#                         option_data['image'] = {'image_id': opt['image_id']}
#
#                 option_list.append(option_data)
#
#             # Thêm vào danh sách đã định dạng
#             formatted_tier_variations.append({
#                 'name': variation['name'],
#                 'option_list': option_list
#             })
#
#         return formatted_tier_variations
#
#     def _map_odoo_variants_to_shopee_models(self, binding, tier_variations, existing_models=None):
#         """
#         Ánh xạ các biến thể của Odoo sang mô hình biến thể của Shopee
#
#         :param binding: Binding record
#         :param tier_variations: Cấu trúc tier variations
#         :param existing_models: Danh sách models đã tồn tại trên Shopee (nếu có)
#         :return: Danh sách models cho Shopee
#         """
#         product_tmpl = binding.odoo_id.product_tmpl_id
#         attribute_lines = product_tmpl.attribute_line_ids[:2]  # Lấy tối đa 2 thuộc tính
#
#         # Tạo mapping từ model_id (nếu có) đến variant
#         existing_model_map = {}
#         if existing_models:
#             for model in existing_models:
#                 tier_index_tuple = tuple(model.get('tier_index', []))
#                 if tier_index_tuple:
#                     existing_model_map[tier_index_tuple] = model.get('model_id')
#
#         # Xây dựng bảng ánh xạ từ giá trị thuộc tính đến vị trí trong tier_variation
#         attribute_value_map = {}
#         for tier_idx, attr_line in enumerate(attribute_lines):
#             attribute_value_map[attr_line.attribute_id.id] = {}
#             for option_idx, value in enumerate(attr_line.value_ids):
#                 attribute_value_map[attr_line.attribute_id.id][value.id] = option_idx
#
#         # Chuẩn bị danh sách model
#         models = []
#         processed_skus = set()
#         for variant in product_tmpl.product_variant_ids:
#             # Tạo tier_index từ giá trị thuộc tính của biến thể
#             tier_index = []
#             valid_variant = True
#
#             for attr_line in attribute_lines:
#                 attr_id = attr_line.attribute_id.id
#                 # Lấy giá trị thuộc tính của biến thể này
#                 attr_values = variant.product_template_attribute_value_ids.filtered(
#                     lambda x: x.attribute_id.id == attr_id
#                 )
#
#                 # Nếu không tìm thấy giá trị thuộc tính, đánh dấu là không hợp lệ
#                 if not attr_values:
#                     valid_variant = False
#                     break
#
#                 value_id = attr_values.product_attribute_value_id.id
#
#                 # Nếu không tìm thấy giá trị trong mapping, đánh dấu là không hợp lệ
#                 if attr_id not in attribute_value_map or value_id not in attribute_value_map[attr_id]:
#                     valid_variant = False
#                     break
#
#                 tier_index.append(attribute_value_map[attr_id][value_id])
#
#             # Bỏ qua biến thể không hợp lệ
#             if not valid_variant or len(tier_index) != len(tier_variations):
#                 continue
#
#             # Kiểm tra xem biến thể này đã tồn tại trên Shopee chưa
#             tier_index_tuple = tuple(tier_index)
#             model_id = existing_model_map.get(tier_index_tuple)
#
#             # Xử lý SKU của biến thể để đảm bảo không trùng lặp
#             if variant.default_code:
#                 # Nếu variant có default_code, ưu tiên sử dụng
#                 model_sku = variant.default_code
#             else:
#                 # Tạo SKU từ prefix và thông tin biến thể
#                 variant_suffix = '-'.join(map(str, tier_index))
#                 model_sku = f"MODEL-SKU-{variant_suffix}"
#
#             # Tạo SKU duy nhất cho biến thể này
#             original_sku = model_sku
#             counter = 1
#
#             # Thêm vào tập hợp SKU đã xử lý
#
#
#             # Kiểm tra trùng lặp với SKU đã tồn tại trên Shopee và với SKU đã xử lý trong phiên này
#             while model_sku in processed_skus:
#                 model_sku = f"{original_sku}-{counter}"
#                 counter += 1
#
#             # Chuẩn bị thông tin model
#             model_data = {
#                 'tier_index': tier_index,
#                 'original_price': variant.lst_price,
#                 'model_sku': model_sku,
#                 'seller_stock': [
#                     {
#                         # 'location_id': self.backend_record.location_id or "-",
#                         'stock': int(variant.qty_available)
#                     }
#                 ]
#             }
#
#             processed_skus.add(model_sku)
#
#             # Thêm model_id nếu đã tồn tại
#             if model_id:
#                 model_data['model_id'] = model_id
#
#             # Thêm thông tin khối lượng nếu có
#             if hasattr(variant, 'weight') and variant.weight:
#                 model_data['weight'] = variant.weight
#
#             models.append(model_data)
#
#         return models
#
#     def run(self, binding):
#         """Run the export"""
#         self.binding = binding
#         self.external_id = binding.external_id
#
#         try:
#             data = self._get_data(binding)
#             data = self._validate_data(data)
#
#             # Xử lý hình ảnh sản phẩm nếu cần
#             if not data.get('images'):
#                 image_data, image_name = self._prepare_image_data(binding)
#                 if image_data:
#                     # Upload hình ảnh lên Shopee
#                     image_result = self.backend_adapter.upload_image(image_data)
#
#                     # Kiểm tra kết quả upload ảnh
#                     if not image_result.get('error'):
#                         # Lấy image_id từ response
#                         parsed_response = image_result.get('response', {})
#                         image_id = (
#                                 parsed_response.get('response', {})
#                                 .get('image_info', {})
#                                 .get('image_id') or
#                                 parsed_response.get('response', {})
#                                 .get('image_info_list', [{}])[0]
#                                 .get('image_info', {})
#                                 .get('image_id')
#                         )
#
#                         if image_id:
#                             data['images'] = [image_id]
#                         else:
#                             raise ValueError("Failed to extract image_id from Shopee response")
#                     else:
#                         error_msg = image_result.get('message', 'Unknown error')
#                         raise ValueError(f"Failed to upload product image to Shopee: {error_msg}")
#
#             # Kiểm tra sản phẩm có biến thể hay không
#             has_variants = self._has_variants(binding)
#
#             # Tạo hoặc cập nhật sản phẩm
#             if self.external_id:
#                 # Đã tồn tại, cập nhật sản phẩm
#                 self._update(data)
#
#                 # Nếu có biến thể, cập nhật thông tin biến thể
#                 if has_variants:
#                     # Lấy thông tin biến thể hiện tại của sản phẩm
#                     model_list = self.backend_adapter.get_model_list(self.external_id)
#
#                     # Chuẩn bị dữ liệu tier variations mới
#                     new_tier_variations = self._prepare_tier_variations(binding)
#
#                     # Lấy dữ liệu tier variations hiện tại
#                     existing_tier_variations = model_list.get('tier_variation', [])
#
#                     # Lấy dữ liệu models hiện tại
#                     existing_models = model_list.get('model', [])
#
#                     # So sánh cấu trúc tier variations
#                     need_update = self._compare_tier_variations(existing_tier_variations, new_tier_variations)
#
#                     if need_update:
#                         # Nếu cấu trúc khác nhau, khởi tạo lại tier variations
#                         _logger.info(f"Updating tier variations for product {self.external_id}")
#                         formatted_variations = self._format_tier_variations_for_api(new_tier_variations)
#
#                         # Chuẩn bị models
#                         models = self._map_odoo_variants_to_shopee_models(binding, new_tier_variations)
#
#                         # Gọi API init_tier_variation để thiết lập cấu trúc biến thể
#                         init_result = self.backend_adapter.init_tier_variation(self.external_id, formatted_variations, models)
#
#                         if init_result.get('error'):
#                             _logger.error(f"Error initializing tier variations: {init_result.get('error')}")
#                             raise ValueError(f"Error initializing tier variations: {init_result.get('error')}")
#                     # else:
#                     #     # Nếu cấu trúc giống nhau, chỉ cập nhật thông tin models
#                     #     _logger.info(f"Updating models for product {self.external_id} without changing tier variations")
#                     #     models = self._map_odoo_variants_to_shopee_models(binding, new_tier_variations, existing_models)
#                     #     self.backend_adapter.update_tier_variation(self.external_id, models)
#             else:
#                 result = self._create(data)
#                 if result and result.get('response', {}).get('item_id'):
#                     item_id = result['response']['item_id']
#                     self.binder.bind(item_id, binding)
#                     if has_variants:
#                         # Chuẩn bị dữ liệu tier variations
#                         new_tier_variations = self._prepare_tier_variations(binding)
#                         formatted_variations = self._format_tier_variations_for_api(new_tier_variations)
#
#                         # Chuẩn bị models
#                         models = self._map_odoo_variants_to_shopee_models(binding, new_tier_variations)
#
#                         # Gọi API init_tier_variation để thiết lập cấu trúc biến thể
#                         init_result = self.backend_adapter.init_tier_variation(item_id, formatted_variations, models)
#
#                         if init_result.get('error'):
#                             _logger.error(f"Error initializing tier variations: {init_result.get('error')}")
#                             raise ValueError(f"Error initializing tier variations: {init_result.get('error')}")
#
#             binding.write({'sync_date': fields.Datetime.now()})
#             return True
#         except Exception as e:
#             _logger.error(str(e))
#             raise
#
#     def _validate_data(self, data):
#         """Validate the data to create records on shopee"""
#         # Process category_id to ensure it's an integer
#         if 'category_id' in data:
#             if isinstance(data['category_id'], bool) or not data['category_id']:
#                 # Nếu không có danh mục, thử lấy gợi ý từ Shopee
#                 data = self._try_get_category_recommendation(data)
#             else:
#                 try:
#                     data['category_id'] = int(data['category_id'])
#                 except (ValueError, TypeError):
#                     _logger.warning(f"Invalid category_id: {data['category_id']}")
#                     # Nếu danh mục không hợp lệ, thử lấy gợi ý từ Shopee
#                     data = self._try_get_category_recommendation(data)
#         else:
#             # Nếu không có trường category_id, thử lấy gợi ý từ Shopee
#             data = self._try_get_category_recommendation(data)
#
#         # Process other numeric fields
#         if 'price' in data:
#             data['price'] = float(data['price'])
#
#         if 'stock' in data:
#             data['stock'] = int(data['stock'])
#
#         # Thêm các trường bắt buộc
#         if 'weight' not in data:
#             data['weight'] = 1.0
#
#         if 'package_height' not in data:
#             data['package_height'] = 10
#
#         if 'package_length' not in data:
#             data['package_length'] = 10
#
#         if 'package_width' not in data:
#             data['package_width'] = 10
#
#         # # Xử lý item_sku để đảm bảo không trùng lặp
#         # sku = data.get('item_sku', '')
#         # if self.external_id:
#         #     # Nếu đang cập nhật, không cần thay đổi SKU
#         #     if not sku or sku == '-':
#         #         # Nhưng nếu SKU trống, tạo SKU mới
#         #         data['item_sku'] = self.backend_adapter.generate_unique_sku(f"SKU-{self.binding.id}")
#         # else:
#         #     # Nếu đang tạo mới, kiểm tra và đảm bảo SKU duy nhất
#         #     data['item_sku'] = self.backend_adapter.generate_unique_sku(sku)
#
#         # Remove None/False values for API compatibility
#         for key in list(data.keys()):
#             if data[key] is None or (isinstance(data[key], bool) and not data[key]):
#                 del data[key]
#
#         return data
#
#     def _try_get_category_recommendation(self, data):
#         """Thử lấy gợi ý danh mục từ Shopee"""
#         try:
#             item_name = self.binding.shopee_name or self.binding.odoo_id.name
#
#             if not item_name:
#                 return data
#
#             params = {'item_name': item_name}
#
#             # Gọi API để lấy gợi ý danh mục
#             result = self.backend_adapter.call('/api/v2/product/category_recommend', 'GET', params=params)
#
#             if result and not result.get('error'):
#                 recommended_categories = result.get('response', {}).get('category_id', [])
#                 if recommended_categories:
#                     # Dùng danh mục đầu tiên được gợi ý
#                     data['category_id'] = int(recommended_categories[0])
#
#                     # Cập nhật lại binding để lần sau không cần gợi ý lại
#                     self.binding.with_context(connector_no_export=True).write({
#                         'shopee_category_id': str(recommended_categories[0])
#                     })
#
#                     # Tìm danh mục tương ứng trong hệ thống
#                     category = self.env['shopee.category'].search([
#                         ('backend_id', '=', self.backend_record.id),
#                         ('shopee_category_id', '=', str(recommended_categories[0]))
#                     ], limit=1)
#
#                     if category:
#                         self.binding.with_context(connector_no_export=True).write({
#                             'shopee_category': category.id
#                         })
#
#                     _logger.info("Applied recommended category ID %s for product: %s",
#                                  recommended_categories[0], self.binding.shopee_name or self.binding.odoo_id.name)
#
#         except Exception as e:
#             _logger.warning("Failed to get category recommendation: %s", str(e))
#
#         return data

class ShopeeInventoryExporter(Component):
    _name = 'shopee.inventory.exporter'
    _inherit = ['base.shopee.connector', 'base.exporter']
    _usage = 'inventory.exporter'
    _apply_on = 'shopee.product.template'

    def run(self, binding):
        """Run the inventory export"""
        self.binding = binding
        self.external_id = binding.external_id

        try:
            stock = binding.shopee_stock
            result = self.backend_adapter.update_stock(self.external_id, stock)
            binding.write({'sync_date': fields.Datetime.now()})
            return result
        except Exception as e:
            _logger.error(str(e))
            raise

class ShopeeTrackingExporter(Component):
    _name = 'shopee.tracking.exporter'
    _inherit = ['base.shopee.connector', 'base.exporter']
    _usage = 'tracking.exporter'
    _apply_on = 'shopee.sale.order'

    def run(self, binding):
        """Run the tracking export"""
        self.binding = binding
        self.external_id = binding.external_id

        try:
            order_sn = binding.shopee_order_sn
            tracking_number = binding.shopee_tracking_number
            carrier_id = self._get_carrier_id(binding.shopee_shipping_carrier)
            result = self.backend_adapter.update_shipping_status(
                order_sn, tracking_number, carrier_id)
            binding.write({'sync_date': fields.Datetime.now()})
            return result
        except Exception as e:
            _logger.error(str(e))
            raise

    def _get_carrier_id(self, carrier_name):
        """Map carrier name to Shopee carrier ID"""
        # This is a simplified mapping, needs to be extended
        carrier_map = {
            'GHTK': 1,
            'GHN': 2,
            'J&T': 3,
            # Add more carriers as needed
        }
        return carrier_map.get(carrier_name, 1)