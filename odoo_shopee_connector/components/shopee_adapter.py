# -*- coding: utf-8 -*-
import hashlib
import hmac
import time
import requests
import logging
import random
import string
from odoo.addons.component.core import Component

_logger = logging.getLogger(__name__)


class ShopeeAdapter(Component):
    _name = 'shopee.adapter'
    _inherit = 'base.backend.adapter'
    _usage = 'backend.adapter'

    def _make_timestamp(self):
        """Return current timestamp"""
        return int(time.time())

    def _generate_signature(self, path):
        """Generate signature for Shopee API v2 according to official documentation"""
        timestamp = self._make_timestamp()
        partner_id = self.backend_record.partner_id
        partner_key = self.backend_record.partner_key

        # Tạo base string đúng cách theo định dạng:
        # Với Shop APIs: partner_id + api path + timestamp + access_token + shop_id
        base_string = f"{partner_id}{path}{timestamp}"

        # Thêm access_token và shop_id nếu đây không phải là public API
        # (auth/token/get là public API không cần thêm)
        if path not in ['auth/token/get']:
            base_string += f"{self.backend_record.access_token}{self.backend_record.shop_id}"

        sign = hmac.new(
            partner_key.encode('utf-8'),
            base_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        _logger.info(f"Generated signature for path {path}: {sign}")
        return sign, timestamp

    def _make_request(self, path, method='GET', params=None, json_data=None):
        url = self.backend_record.api_url + path

        sign, timestamp = self._generate_signature(path)
        common_params = {
            'partner_id': self.backend_record.partner_id,
            'timestamp': timestamp,
            'sign': sign,
            'shop_id': self.backend_record.shop_id,
            'access_token': self.backend_record.access_token
        }

        if params:
            common_params.update(params)

        headers = {
            'Content-Type': 'application/json',
            'x-tts-access-token': self.backend_record.access_token,
        }

        try:

            if method == 'GET':
                response = requests.get(url, params=common_params, headers=headers)
            elif method in ['POST', 'PUT']:
                response = requests.request(method, url, params=common_params, headers=headers, json=json_data)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            _logger.error(f"API call error: {str(e)}")
            raise

    def call(self, path, method='GET', params=None, body=None):
        """Make API call to Shopee with correct parameters"""
        # Check and refresh token if needed, except for auth endpoints
        if path not in ['auth/token/get', '/api/v2/auth/token/get']:
            self.backend_record.check_and_refresh_token()

        sign, timestamp = self._generate_signature(path)

        url = self.backend_record.api_url + path
        common_params = {
            'partner_id': self.backend_record.partner_id,
            'timestamp': timestamp,
            'sign': sign,
        }

        # Chỉ thêm shop_id và access_token cho các API không phải public
        if path not in ['auth/token/get']:
            common_params['shop_id'] = self.backend_record.shop_id
            common_params['access_token'] = self.backend_record.access_token

        if params:
            common_params.update(params)

        headers = {
            'Content-Type': 'application/json',
        }

        try:
            if method == 'GET':
                response = requests.get(url, params=common_params, headers=headers, timeout=30)
            elif method == 'POST':
                response = requests.post(
                    url, params=common_params, headers=headers, json=body or {}, timeout=30)
            else:
                raise ValueError(f'Unsupported method {method}')

            # Log response để debug
            _logger.info(f"Response status: {response.status_code}")
            _logger.info(f"Response text: {response.text[:500]}")  # Log 500 ký tự đầu tiên

            if response.status_code != 200:
                _logger.error(f"Shopee API error: {response.text}")
                return {'error': response.text}

            return response.json()
        except Exception as e:
            _logger.error(f"API call error: {str(e)}")
            raise

    # Products
    def get_products(self, since_date=None):
        """Get products from Shopee"""
        body = {
            'page_size': 100,
            'page': 0,
        }
        if since_date:
            body['update_time_from'] = int(since_date.timestamp())
            body['update_time_to'] = int(time.time())

        return self.call('/api/v2/product/get_item_list', 'POST', body)

    def get_product_detail(self, item_id):
        """Get product detail from Shopee"""
        body = {
            'item_id_list': [int(item_id)],
        }
        return self.call('/api/v2/product/get_item_base_info', 'POST', body)

    def create_product(self, data):
        """Create product on Shopee with full JSON structure"""
        # Lấy danh sách kênh logistics
        logistics_channels = self.get_available_logistics()
        if not logistics_channels:
            _logger.error("No logistics channels available")
            raise ValueError("No logistics channels found. Please check Shopee Seller Center.")
        logistic_info = []
        for logistics_channel in logistics_channels:
            logistics_channel_id = logistics_channel.get('logistics_channel_id', '')
            logistic_info_detail = {
                "logistic_id": logistics_channel_id,
                "enabled": True,
                "is_free": False,
                "size_id": 1,
                "shipping_fee": 0
            }
            logistic_info.append(logistic_info_detail)

        item_name = self.format_product_name(data.get('item_name', ''))
        # Xử lý mô tả sản phẩm
        description = data.get('description', '').strip()
        # Nếu mô tả trống hoặc quá ngắn sau khi loại bỏ, thêm mô tả mặc định
        if len(description) < 25:
            description = "Sản phẩm chất lượng cao, được thiết kế chuyên nghiệp, đáp ứng nhu cầu sử dụng của khách hàng. Với thiết kế tinh tế và chức năng ưu việt, sản phẩm mang đến trải nghiệm tối ưu."
        # Cắt mô tả nếu quá dài
        description = description[:1000]

        # Chuẩn bị dữ liệu theo đúng cấu trúc JSON mẫu
        formatted_data = {
            "original_price": float(data.get('price', 0.0)),
            "description": description,
            "weight": float(data.get('weight', 1.1)),
            "item_name": item_name,
            "item_status": data.get('item_status', 'UNLIST'),
            "logistic_info": logistic_info,
            "category_id": 100732,
            "image": data.get('image', {
                "image_id_list": data.get('images', '-')
            }),
            "item_sku": data.get('item_sku', '-'),
            "condition": data.get('condition', 'NEW'),
            "brand": data.get('brand', {
                'brand_id': 0,  # Mặc định brand_id là 0 nếu không có
                'original_brand_name': data.get('item_name', 'Unknown Brand')
            }),
            "seller_stock": [{
                'stock': max(5, min(int(data.get('stock', 5)), 10000000))
            }],
        }

        tax_info = {
            "ncm": "",
            "same_state_cfop": "",
            "diff_state_cfop": "",
            "csosn": "",
            "origin": "0",
            "cest": "",
            "measure_unit": "pc"
        }
        formatted_data["tax_info"] = tax_info
        formatted_data["tax_exempt"] = True

        try:
            response = self.call('/api/v2/product/add_item', 'POST', body=formatted_data)
            return response
        except Exception as e:
            _logger.error(f"Error creating product: {str(e)}")
            raise

    def format_product_name(self, product_name):
        """
        Format tên sản phẩm theo chuẩn Shopee:
        - Loại bỏ HTML tags
        - Loại bỏ các ký tự đặc biệt không được phép
        - Xử lý độ dài tên (3-120 ký tự)
        - Chuẩn hóa định dạng (viết hoa đầu câu, không viết hoa toàn bộ)
        - Loại bỏ các từ khóa bị cấm
        - Loại bỏ emoji và ký tự Unicode đặc biệt

        :param product_name: Tên sản phẩm gốc
        :return: Tên sản phẩm đã được format chuẩn
        """
        if not product_name:
            return "Sản phẩm"

        import re

        # 1. Loại bỏ tất cả HTML tags
        clean_name = re.sub(r'<[^>]+>', '', product_name)

        # 2. Loại bỏ các ký tự không hợp lệ theo quy định Shopee
        # Shopee chỉ cho phép chữ cái, số, và một số ký tự đặc biệt nhất định
        clean_name = re.sub(r'[^\w\s.,;:!?()[\]{}"\'-+*/=<>%$#@&|\\~`^]', '', clean_name)

        # 3. Loại bỏ các emoji và ký tự Unicode đặc biệt
        # Regex này loại bỏ phần lớn emoji và ký tự Unicode bất thường
        clean_name = re.sub(
            r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F700-\U0001F77F\U0001F780-\U0001F7FF\U0001F800-\U0001F8FF\U0001F900-\U0001F9FF\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF\U00002702-\U000027B0\U000024C2-\U0001F251]+',
            '', clean_name)

        # 4. Loại bỏ các từ khóa bị cấm trong tên sản phẩm Shopee
        banned_keywords = [
            'giả', 'nhái', 'fake', 'super fake', 'super', 'siêu cấp', 'loại 1', 'cấp 1',
            'rep', 'replica', 'knockoff', 'counterfeit', 'imitation', 'copy',
            'miễn phí', 'free', 'tặng kèm', 'khuyến mãi', 'sale off', 'giảm giá sốc',
            'rẻ nhất', 'giá rẻ', 'giá tốt nhất', 'best price', 'cheapest',
            'chính hãng', 'authentic', 'real', 'genuine'  # Từ chính hãng vẫn dùng được nhưng để an toàn
        ]

        for keyword in banned_keywords:
            # Sử dụng regex với word boundary để tránh thay thế từ trong từ khác
            # \b đánh dấu ranh giới từ
            clean_name = re.sub(r'\b' + re.escape(keyword) + r'\b', '', clean_name, flags=re.IGNORECASE)

        # 5. Xử lý khoảng trắng thừa
        clean_name = re.sub(r'\s+', ' ', clean_name).strip()

        # 6. Viết hoa chữ đầu câu, không viết hoa toàn bộ
        if clean_name and clean_name.isupper():
            clean_name = clean_name.capitalize()

        # 7. Đảm bảo độ dài tên từ 3-120 ký tự theo quy định Shopee
        if len(clean_name) < 3:
            clean_name = f"Sản phẩm {clean_name}"
        elif len(clean_name) > 120:
            clean_name = clean_name[:117] + "..."

        # 8. Đảm bảo không có ký tự đặc biệt ở đầu tên sản phẩm
        clean_name = re.sub(r'^[^\w\s]+', '', clean_name).strip()

        # 9. Thêm xử lý các trường hợp đặc biệt theo quy định của Shopee
        # - Không cho phép quá 5 dấu ! liên tiếp
        clean_name = re.sub(r'!{5,}', '!!!!', clean_name)

        # - Loại bỏ quá nhiều dấu chấm than hoặc dấu chấm hỏi liên tiếp
        clean_name = re.sub(r'[!?]{3,}', '!!', clean_name)

        # - Giới hạn số dấu chấm, dấu phẩy liên tiếp
        clean_name = re.sub(r'[.,]{3,}', '...', clean_name)

        # 10. Nếu tên trống sau khi xử lý, sử dụng tên mặc định
        if not clean_name or len(clean_name.strip()) < 3:
            clean_name = "Sản phẩm"

        return clean_name

    def update_product(self, data):
        """Update product on Shopee following the API documentation

        :param data: Dictionary containing the product data to update
        :return: API response from Shopee
        """
        # Kiểm tra item_id (bắt buộc)
        if not data.get('item_id'):
            raise ValueError("Missing item_id for update operation")

        # Gọi API Shopee để cập nhật sản phẩm
        return self.call('/api/v2/product/update_item', 'POST', body=data)

    def upload_image(self, image_data=None, image_path=None):
        """
        Upload image to Shopee Media Space

        :param image_data: Base64 encoded image data (optional)
        :param image_path: Path to image file (optional)
        :return: Parsed response from Shopee API
        """
        path = '/api/v2/media_space/upload_image'

        # Generate signature and timestamp
        sign, timestamp = self._generate_signature(path)

        # Prepare common parameters
        params = {
            'partner_id': self.backend_record.partner_id,
            'timestamp': timestamp,
            'sign': sign,
            'shop_id': self.backend_record.shop_id,
            'access_token': self.backend_record.access_token
        }

        # Prepare headers
        headers = {
            'x-tts-access-token': self.backend_record.access_token
        }

        # Prepare payload and files
        payload = {}
        files = None

        # Prioritize image_path if provided
        if image_path:
            files = [
                ('image', ('image', open(image_path, 'rb'), 'application/octet-stream'))
            ]
        # Fallback to image_data if provided and no image_path
        elif image_data:
            # Decode base64 to bytes and create file-like object
            import io
            import base64
            image_bytes = base64.b64decode(image_data)
            files = [
                ('image', ('image', io.BytesIO(image_bytes), 'application/octet-stream'))
            ]
        else:
            raise ValueError("Either image_data or image_path must be provided")

        try:
            # Construct full URL
            url = self.backend_record.api_url + path

            # Make the request
            response = requests.post(
                url,
                params=params,
                headers=headers,
                data=payload,
                files=files,
                allow_redirects=False
            )

            # Close the file if opened
            if files and hasattr(files[0][1][1], 'close'):
                files[0][1][1].close()

            # Check for successful response
            response.raise_for_status()

            # Parse JSON response
            parsed_response = response.json()

            # Log the full response for debugging
            _logger.info(f"Image upload response: {parsed_response}")

            # Wrap parsed response to ensure .get() method works
            return {
                'response': parsed_response,
                'error': parsed_response.get('error', ''),
                'message': parsed_response.get('message', '')
            }

        except Exception as e:
            _logger.error(f"Image upload error: {str(e)}")
            # Log the full error details for debugging
            if hasattr(e, 'response'):
                _logger.error(f"Response content: {e.response.text}")

            # Return a standardized error response
            return {
                'error': str(e),
                'response': None,
                'message': str(e)
            }

    def update_stock(self, item_id, stock, model_id=0, location_id="-"):
        """
        Update product stock on Shopee

        :param item_id: ID của sản phẩm trên Shopee
        :param stock: Số lượng tồn kho cần cập nhật
        :param model_id: ID của biến thể sản phẩm (mặc định là 0 cho sản phẩm không có biến thể)
        :param location_id: ID của kho hàng (mặc định là "-")
        :return: Kết quả từ API Shopee
        """
        body = {
            "item_id": int(item_id),
            "stock_list": [
                {
                    "model_id": int(model_id),
                    "seller_stock": [
                        {
                            "location_id": location_id,
                            "stock": int(stock)
                        }
                    ]
                }
            ]
        }

        return self.call('/api/v2/product/update_stock', 'POST', body=body)

    # Orders
    def get_orders(self, since_date=None):
        """Get orders from Shopee"""
        time_from = int(since_date.timestamp()) if since_date else int(time.time() - 30 * 24 * 3600)
        time_to = int(time.time())

        params = {
            'time_range_field': 'create_time',
            'time_from': time_from,
            'time_to': time_to,
            'page_size': 100,
            'page': 0,
            'order_status': 'READY_TO_SHIP'
        }
        response = self.call('/api/v2/order/get_order_list', 'GET', params)
        return response

    def get_order_detail(self, order_sn_list):
        """Get order detail from Shopee"""
        params = {
            'order_sn_list': order_sn_list,
            'request_order_status_pending': 'true',
            'response_optional_fields': 'item_list,recipient_address,package_list,shipping_carrier,buyer_user_id,buyer_username,estimated_shipping_fee,actual_shipping_fee,note'
        }
        response = self.call('/api/v2/order/get_order_detail', 'GET', params)
        return response

    def update_shipping_status(self, order_sn, tracking_number, carrier_id):
        """Update shipping status on Shopee"""
        body = {
            'order_sn': order_sn,
            'tracking_number': tracking_number,
            'carrier_id': carrier_id,
        }
        return self.call('/api/v2/logistics/ship_order', 'POST', body)

    def get_categories(self, language='vi'):
        """Get all categories from Shopee"""
        body = {
            'language': language,
        }
        return self.call('/api/v2/product/get_category', 'GET', body)

    def get_available_logistics(self):
        """
        Lấy danh sách các kênh logistics có sẵn
        """
        body = {
            'language': 'vi',
        }
        try:
            result = self.call('/api/v2/logistics/get_channel_list', 'GET', body)
            if result and not result.get('error'):
                logistics_channels = result.get('response', {}).get('logistics_channel_list', [])
                return logistics_channels
            else:
                return []

        except Exception as e:
            _logger.error(f"Failed to get logistics channels: {str(e)}")
            return []

    def get_model_list(self, item_id):
        """
        Lấy thông tin về các model (biến thể) của sản phẩm

        :param item_id: ID sản phẩm trên Shopee
        :return: Thông tin về các tier variations và models của sản phẩm
        """
        # Kiểm tra input
        if not item_id:
            raise ValueError("Missing item_id")

        # Chuẩn bị tham số
        params = {
            'item_id': int(item_id)
        }

        # Gọi API
        try:
            response = self.call('/api/v2/product/get_model_list', 'GET', params=params)

            if response.get('error'):
                _logger.error(f"Error getting model list for product {item_id}: {response.get('error')}")

            # Trả về dữ liệu từ response
            return response.get('response', {})
        except Exception as e:
            _logger.error(f"Exception when getting model list for product {item_id}: {str(e)}")
            return {}

    def init_tier_variation(self, item_id, tier_variations, models=None, standardise_tier_variations=None):
        """
        Khởi tạo các tier variation (thuộc tính biến thể) cho sản phẩm

        :param item_id: ID sản phẩm trên Shopee
        :param tier_variations: Danh sách các tier variation cần thiết lập
        :param models: Danh sách các model cần khởi tạo (bắt buộc theo API Shopee)
        :param standardise_tier_variations: Danh sách các standardise tier variation (tùy chọn)
        :return: Kết quả từ API Shopee

        Định dạng chuẩn theo API Shopee:
        {
            "item_id": 1000,
            "tier_variation": [
                {
                    "name": "Color",
                    "option_list": [
                        {
                            "option": "Red",
                            "image": {
                                "image_id": "82becb4830bd2ee90ad6acf8a9dc26d7"
                            }
                        }
                    ]
                }
            ],
            "model": [
                {
                    "tier_index": [0],
                    "original_price": 38.3,
                    "model_sku": "SKU",
                    "seller_stock": [
                        {
                            "location_id": "-",
                            "stock": 0
                        }
                    ]
                }
            ]
        }
        """
        if not item_id:
            raise ValueError("Missing item_id")

        if models:
            for model in models:
                if 'tier_index' not in model:
                    model['tier_index'] = [0]

        body = {
            'item_id': int(item_id),
            'tier_variation': tier_variations,
            'model': models
        }

        if standardise_tier_variations:
            body['standardise_tier_variation'] = standardise_tier_variations

        try:
            response = self.call('/api/v2/product/init_tier_variation', 'POST', body=body)
            if response.get('error'):
                _logger.error(f"Error initializing tier variations for product {item_id}: {response.get('error')}")
            return response
        except Exception as e:
            _logger.error(f"Exception when initializing tier variations for product {item_id}: {str(e)}")
            raise

    def update_tier_variation(self, item_id, model_list):
        """
        Cập nhật hoặc thêm mới các model (biến thể) cho sản phẩm có tier variation

        :param item_id: ID sản phẩm trên Shopee
        :param model_list: Danh sách các model cần cập nhật hoặc thêm mới
        :return: Kết quả từ API Shopee

        Cấu trúc model_list:
        [
            {
                'tier_index': [0, 1],  # Tương ứng với các vị trí trong tier_variation
                'model_sku': 'SP-RED-M',
                'original_price': 150000.0,
                'seller_stock': [
                    {
                        'location_id': 'VNZ',
                        'stock': 10
                    }
                ],
                'gtin_code': '123456789012',  # Tùy chọn
                'weight': 1.1,  # Tùy chọn
                'dimension': {  # Tùy chọn
                    'package_height': 10,
                    'package_length': 20,
                    'package_width': 15
                },
                'pre_order': {  # Tùy chọn
                    'is_pre_order': False,
                    'days_to_ship': 7
                }
            }
        ]
        """
        if not item_id:
            raise ValueError("Missing item_id")

        if not model_list or not isinstance(model_list, list):
            raise ValueError("model_list must be a list of model information")

        # Lấy thông tin tier variation hiện tại của sản phẩm để đảm bảo tính nhất quán
        try:
            current_model_info = self.get_model_list(item_id)
            current_tier_variations = current_model_info.get('tier_variation', [])

            # Kiểm tra số lượng tier variation để đảm bảo tính nhất quán
            tier_variation_count = len(current_tier_variations)

            # Kiểm tra và điều chỉnh tier_index trong models để phù hợp với tier variation hiện tại
            for model in model_list:
                if 'tier_index' in model:
                    # Đảm bảo độ dài của tier_index phù hợp với cấu trúc tier variation hiện tại
                    if len(model['tier_index']) != tier_variation_count:
                        _logger.warning(
                            f"Adjusting tier_index length from {len(model['tier_index'])} to {tier_variation_count} for model_sku: {model.get('model_sku', 'unknown')}")

                        # Nếu tier_index ngắn hơn, thêm các chỉ số 0 vào cuối
                        if len(model['tier_index']) < tier_variation_count:
                            model['tier_index'] = model['tier_index'] + [0] * (
                                        tier_variation_count - len(model['tier_index']))

                        # Nếu tier_index dài hơn, cắt bớt
                        if len(model['tier_index']) > tier_variation_count:
                            model['tier_index'] = model['tier_index'][:tier_variation_count]

                    # Kiểm tra xem từng tier_index có hợp lệ không
                    for i, idx in enumerate(model['tier_index']):
                        # Nếu chỉ số vượt quá số lượng tùy chọn trong tier variation, điều chỉnh về 0
                        if i < tier_variation_count and idx >= len(current_tier_variations[i].get('option_list', [])):
                            _logger.warning(f"Invalid tier_index {idx} at position {i}, adjusting to 0")
                            model['tier_index'][i] = 0
        except Exception as e:
            _logger.warning(f"Error when trying to get current tier variations: {str(e)}")

        formatted_models = []
        for model in model_list:
            required_fields = ['tier_index', 'original_price', 'seller_stock']
            for field in required_fields:
                if field not in model:
                    raise ValueError(f"Missing required field '{field}' in model data")

            formatted_model = {
                'tier_index': model['tier_index'],
                'original_price': float(model['original_price']),
                'seller_stock': model['seller_stock']
            }

            optional_fields = [
                'model_sku', 'gtin_code', 'weight', 'dimension', 'pre_order'
            ]

            for field in optional_fields:
                if field in model:
                    formatted_model[field] = model[field]

            # Nếu có model_id, thêm vào
            if 'model_id' in model:
                formatted_model['model_id'] = model['model_id']

            formatted_models.append(formatted_model)

        body = {
            'item_id': int(item_id),
            'model': formatted_models
        }

        try:
            response = self.call('/api/v2/product/update_tier_variation', 'POST', body=body)
            if response.get('error'):
                error_message = response.get('message', '')
                _logger.error(f"Error updating tier variation models for product {item_id}: {error_message}")

                # Nếu vẫn gặp lỗi "tier-variation level not same", thử giải pháp thay thế
                if response.get('error') == 'product.error_tier_var_level_not_same':
                    _logger.warning(f"Trying alternative approach for product {item_id}")
                    # Lấy thông tin tier variation hiện tại
                    model_info = self.get_model_list(item_id)
                    tier_variations = model_info.get('tier_variation', [])

                    # Nếu có thông tin tier_variation, thử khởi tạo lại
                    if tier_variations:
                        return self.init_tier_variation(item_id, tier_variations, formatted_models)

            return response
        except Exception as e:
            _logger.error(f"Exception when updating tier variation models for product {item_id}: {str(e)}")
            raise

    def add_product_model(self, item_id, models):
        """
        Thêm biến thể (model) cho sản phẩm trên Shopee sau khi đã thiết lập tier_variation

        :param item_id: ID sản phẩm trên Shopee
        :param models: Danh sách các biến thể cần thêm
        :return: Kết quả từ API Shopee
        """
        if not item_id:
            raise ValueError("Missing item_id for add model operation")

        # Đảm bảo models có cấu trúc đúng
        formatted_models = []
        for model in models:
            # Kiểm tra các trường bắt buộc
            if 'tier_index' not in model:
                raise ValueError("Missing tier_index in model data")

            # Chuẩn bị dữ liệu model theo cấu trúc API
            model_data = {
                'tier_index': model['tier_index'],
            }

            # Thêm các trường tùy chọn
            optional_fields = [
                'original_price', 'model_sku', 'seller_stock', 'weight'
            ]

            for field in optional_fields:
                if field in model:
                    model_data[field] = model[field]

            formatted_models.append(model_data)

        # Chuẩn bị body request
        body = {
            'item_id': int(item_id),
            'model_list': formatted_models
        }

        # Log thông tin request để debug
        _logger.info(f"Calling add_model with body: {body}")

        try:
            response = self.call('/api/v2/product/add_model', 'POST', body=body)
            if response.get('error'):
                _logger.error(f"Error adding models for product {item_id}: {response.get('error')}")
            return response
        except Exception as e:
            _logger.error(f"Exception when adding models for product {item_id}: {str(e)}")
            raise

    def get_variation_tree(self, category_id):
        """
        Lấy thông tin về cây biến thể (variation tree) của danh mục

        :param category_id: ID danh mục trên Shopee
        :return: Thông tin về cây biến thể của danh mục
        """
        if not category_id:
            category_id = 100732

        # Chuẩn bị tham số
        params = {
            'category_id': int(category_id)
        }

        # Gọi API
        try:
            # Sử dụng phương thức call đã có
            response = self.call('/api/v2/product/get_variation_tree', 'GET', params=params)

            if response.get('error'):
                _logger.error(f"Error getting variation tree for category {category_id}: {response.get('error')}")

            # Trả về dữ liệu từ response
            return response.get('response', {})
        except Exception as e:
            _logger.error(f"Exception when getting variation tree for category {category_id}: {str(e)}")
            return {}

    def get_warehouse_detail(self):
        """
        Lấy thông tin chi tiết về kho hàng của người bán trên Shopee

        :return: Danh sách các kho hàng với location_id tương ứng
        """
        try:
            response = self.call('/api/v2/shop/get_warehouse_detail', 'GET')

            if response and not response.get('error'):
                warehouses = response.get('response', {}).get('warehouse_list', [])
                _logger.info(f"Retrieved {len(warehouses)} warehouses from Shopee")
                return warehouses
            else:
                error_msg = response.get('error', 'Unknown error')
                _logger.warning(f"Failed to get warehouse details: {error_msg}")
                return []

        except Exception as e:
            _logger.error(f"Exception when getting warehouse detail: {str(e)}")
            return []

    def _get_location_id(self):
        """
        Lấy location_id từ warehouse. Nếu không có warehouse, trả về None.
        Theo hướng dẫn API Shopee: "if seller don't have any warehouse, you don't need to upload this field"

        :return: location_id hoặc None nếu không có warehouse
        """
        # Kiểm tra cache
        if hasattr(self, '_location_id_cache'):
            return self._location_id_cache

        # Lấy danh sách warehouse
        warehouses = self.get_warehouse_detail()

        if not warehouses:
            _logger.info("No warehouses found, location_id field will be omitted")
            self._location_id_cache = None
            return None

        # Ưu tiên warehouse mặc định (default_warehouse là True)
        for warehouse in warehouses:
            if warehouse.get('default_warehouse', False):
                self._location_id_cache = warehouse.get('location_id')
                _logger.info(f"Using default warehouse with location_id: {self._location_id_cache}")
                return self._location_id_cache

        # Nếu không có warehouse mặc định, dùng warehouse đầu tiên
        if warehouses:
            self._location_id_cache = warehouses[0].get('location_id')
            _logger.info(f"Using first warehouse with location_id: {self._location_id_cache}")
            return self._location_id_cache

        # Không có warehouse nào
        self._location_id_cache = None
        return None

    def check_sku_exists(self, sku):
        """
        Kiểm tra xem SKU đã tồn tại trên Shopee chưa

        :param sku: SKU cần kiểm tra
        :return: True nếu SKU đã tồn tại, False nếu chưa
        """
        try:
            # Sử dụng API search_items để tìm sản phẩm với SKU cụ thể
            params = {
                'offset': 0,
                'page_size': 10,
                'item_sku': sku,
                'attribute_status': 2
            }

            response = self.call('/api/v2/product/search_item', 'GET', params=params)

            if response and not response.get('error'):
                items = response.get('response', {}).get('item', [])

                # Kiểm tra từng sản phẩm tìm được
                for item in items:
                    # Lấy thông tin chi tiết của sản phẩm
                    item_id = item.get('item_id')
                    if item_id:
                        details = self.get_product_detail(item_id)
                        if details and not details.get('error'):
                            item_details = details.get('response', {}).get('item_list', [])
                            for detail in item_details:
                                # Kiểm tra SKU của sản phẩm chính
                                if detail.get('item_sku') == sku:
                                    return True

                                # Kiểm tra SKU của các model nếu có
                                model_list = self.get_model_list(item_id)
                                if model_list and not model_list.get('error'):
                                    models = model_list.get('model', [])
                                    for model in models:
                                        if model.get('model_sku') == sku:
                                            return True

            # Nếu không tìm thấy SKU trùng
            return False

        except Exception as e:
            _logger.warning(f"Error checking SKU existence: {str(e)}")
            return False

    def generate_unique_sku(self, base_sku):
        """
        Tạo SKU duy nhất không trùng với Shopee

        :param base_sku: SKU cơ bản, nếu trống sẽ tạo SKU mới
        :return: SKU duy nhất
        """
        if not base_sku or base_sku == '-':
            # Tạo SKU mới hoàn toàn
            random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
            sku = f"SKU-GEN-{random_str}"
        else:
            # Kiểm tra xem SKU cơ bản đã tồn tại chưa
            if not self.check_sku_exists(base_sku):
                return base_sku

        # Kiểm tra lại xem SKU mới có trùng không
        counter = 1
        original_sku = sku
        while self.check_sku_exists(sku):
            sku = f"{original_sku}-{counter}"
            counter += 1

        return sku