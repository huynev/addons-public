# -*- coding: utf-8 -*-
from odoo.addons.component.core import Component
from odoo.addons.queue_job.exception import RetryableJobError
from odoo import fields
import datetime
import logging

_logger = logging.getLogger(__name__)


class ShopeeImporter(Component):
    _name = 'shopee.importer'
    _inherit = ['base.importer']
    _usage = 'record.importer'

    def _get_shopee_data(self):
        """Return the shopee data for the current external ID"""
        raise NotImplementedError

    def _map_data(self, shopee_data):
        """Map the shopee data to Odoo data"""
        return self.mapper.map_record(shopee_data).values()

    def _create(self, data):
        """Create the Odoo record"""
        model = self.model.with_context(connector_no_export=True)
        binding = model.create(data)
        _logger.info(
            'Created %s binding for %s', self.model._name, self.external_id)
        return binding

    def _update(self, binding, data):
        """Update the Odoo record"""
        binding.with_context(connector_no_export=True).write(data)
        _logger.info(
            'Updated %s binding for %s', self.model._name, self.external_id)
        return binding

    def run(self, external_id, force=False):
        """Run the import"""
        self.external_id = external_id
        lock_name = 'import({}, {}, {})'.format(
            self.backend_record._name,
            self.backend_record.id,
            self.external_id,
        )
        binding = self.binder.to_internal(self.external_id)
        if binding and not force:
            _logger.info(
                'Binding %s already exists for %s',
                binding._name, self.external_id)
            return binding

        try:
            shopee_data = self._get_shopee_data()
            data = self._map_data(shopee_data)
            if binding:
                binding = self._update(binding, data)
            else:
                binding = self._create(data)
            self.binder.bind(self.external_id, binding)
            return binding
        except RetryableJobError:
            raise
        except Exception as e:
            _logger.error(str(e))
            raise

    def _import_dependency(self, external_id, binding_model):
        """Import a dependency."""
        self.backend_record.env[binding_model].with_delay(channel='root.shopee').import_record(
            self.backend_record, external_id)


class ShopeeProductImporter(Component):
    _name = 'shopee.product.importer'
    _inherit = 'shopee.importer'
    _apply_on = 'shopee.product.template'

    def _get_shopee_data(self):
        """Return the shopee data for the current external ID"""
        result = self.backend_adapter.get_product_detail(self.external_id)
        if result and not result.get('error') and result.get('item_list'):
            return result.get('item_list')[0]
        return {}

    def _import_dependencies(self):
        """Import dependencies for the record"""
        return


class ShopeeBatchImporter(Component):
    _name = 'shopee.batch.importer'
    _inherit = ['base.importer']
    _usage = 'batch.importer'

    def run(self, since_date=None, **kwargs):
        """Run the batch import"""
        if since_date is None and hasattr(self.backend_record, 'import_orders_from_date'):
            since_date = self.backend_record.import_orders_from_date

        result = self._run(since_date=since_date, **kwargs)

        # Update last import date if importing orders
        if self.model._name == 'shopee.sale.order' and hasattr(self.backend_record, 'import_orders_from_date'):
            self.backend_record.write({'import_orders_from_date': fields.Datetime.now()})

        return result

    def _run(self, since_date=None, **kwargs):
        """Implement in specific batch importers"""
        raise NotImplementedError


class ShopeeProductBatchImporter(Component):
    _name = 'shopee.product.batch.importer'
    _inherit = 'shopee.batch.importer'
    _apply_on = 'shopee.product.template'

    def _run(self, since_date=None, **kwargs):
        """Run the synchronization"""
        result = self.backend_adapter.get_products(since_date)
        if not result or result.get('error'):
            return False

        for item in result.get('items', []):
            self._import_record(item.get('item_id'))

        return True

    def _import_record(self, external_id):
        """Launch the import of a record"""
        self.model.with_delay(channel='root.shopee').import_record(self.backend_record, external_id)


class ShopeeOrderImporter(Component):
    _name = 'shopee.order.importer'
    _inherit = 'shopee.importer'
    _usage = 'sale.importer'
    _apply_on = 'shopee.sale.order'

    def _get_shopee_data(self):
        """Return the shopee data for the current external ID"""
        result = self.backend_adapter.get_order_detail([self.external_id])
        if result and not result.get('error') and result.get('response', {}).get('order_list'):
            order_data = result.get('response', {}).get('order_list')[0]
            self._convert_timestamps_to_datetime(order_data)
            return order_data
        return {}

    def _convert_timestamps_to_datetime(self, data):
        """Convert Unix timestamps to datetime objects"""
        timestamp_fields = ['create_time', 'update_time', 'pay_time', 'ship_by_date']

        for field in timestamp_fields:
            if field in data and data[field]:
                try:
                    # Convert Unix timestamp to datetime
                    timestamp = int(data[field])
                    if timestamp > 0:
                        # Some APIs return milliseconds, check if we need to divide
                        if timestamp > 100000000000:  # Likely milliseconds
                            timestamp = timestamp / 1000

                        # Create datetime object
                        dt = datetime.datetime.fromtimestamp(timestamp)
                        data[field] = dt
                    else:
                        data[field] = False
                except Exception as e:
                    _logger.warning(f"Error converting {field} timestamp: {e}")
                    data[field] = False

    def _import_dependencies(self):
        """Import dependencies for the record"""
        shopee_data = self._get_shopee_data()

        # Import buyer
        buyer = shopee_data.get('buyer_user_id')
        if buyer:
            self._import_dependency(buyer, 'shopee.res.partner')

        # Import products in order
        for item in shopee_data.get('item_list', []):
            item_id = item.get('item_id')
            if item_id:
                self._import_dependency(item_id, 'shopee.product.template')

    def run(self, external_id, force=False):
        """Extended run method to create order lines"""
        binding = super().run(external_id, force)

        # Lấy lại dữ liệu Shopee
        shopee_data = self._get_shopee_data()

        # Tạo các dòng đơn hàng
        for item in shopee_data.get('item_list', []):
            item['shopee_order_id'] = binding.id
            # self.env['shopee.sale.order.line'].with_delay(channel='root.shopee').import_record(self.backend_record, item)
            self.env['shopee.sale.order.line'].import_record(self.backend_record, item)

        return binding

class ShopeeOrderLineImporter(Component):
    _name = 'shopee.order.line.importer'
    _inherit = 'shopee.importer'
    _usage = 'sale.line.importer'
    _apply_on = 'shopee.sale.order.line'

    def _get_shopee_data(self):
        """Return the shopee line data"""
        # Dữ liệu đã được truyền vào trong quá trình import
        return self.external_id

    def _import_dependencies(self):
        """Import product for the order line"""
        item_id = self.external_id.get('item_id')
        if item_id:
            self._import_dependency(item_id, 'shopee.product.template')

class ShopeeOrderBatchImporter(Component):
    _name = 'shopee.order.batch.importer'
    _inherit = 'shopee.batch.importer'
    _usage = 'sale.batch.importer'
    _apply_on = 'shopee.sale.order'

    def _run(self, since_date=None, **kwargs):
        """Run the synchronization"""
        result = self.backend_adapter.get_orders(since_date)
        if not result or result.get('error'):
            return False

        for order in result.get('response', {}).get('order_list', []):
            self._import_record(order.get('order_sn'))

        return True

    def _import_record(self, external_id):
        """Launch the import of a record"""
        self.model.with_delay(channel='root.shopee').import_record(self.backend_record, external_id)

class ShopeePartnerImporter(Component):
    _name = 'shopee.partner.importer'
    _inherit = 'shopee.importer'
    _apply_on = 'shopee.res.partner'

    def _get_shopee_data(self):
        """Return the shopee data for the current external ID"""
        # Shopee API doesn't have a direct method to get buyer info
        # So we'll need to extract from an order
        return {
            'buyer_user_id': self.external_id,
            'username': f'Shopee Customer {self.external_id}',
        }


class ShopeeCategoryBatchImporter(Component):
    _name = 'shopee.category.batch.importer'
    _inherit = 'shopee.batch.importer'
    _usage = 'category.batch.importer'
    _apply_on = 'shopee.category'

    def _run(self, force=False, **kwargs):
        """Run the synchronization"""
        # Sử dụng adapter chung
        result = self.backend_adapter.get_categories()
        if not result or result.get('error'):
            return False

        # Lấy danh sách danh mục từ response
        categories = result.get('response', {}).get('category_list', [])
        self._import_categories(categories)
        return True

    def _import_categories(self, categories):
        """Recursively import categories with full hierarchy and details"""
        # Tạo từ điển để tra cứu nhanh các category
        category_dict = {cat['category_id']: cat for cat in categories}

        # Sắp xếp categories theo cấp độ và parent_id
        sorted_categories = sorted(
            categories,
            key=lambda x: (x.get('parent_category_id', 0), x['category_id'])
        )

        # Theo dõi các category đã import để tránh import trùng
        imported_category_ids = set()

        for category_data in sorted_categories:
            current_category_id = category_data['category_id']

            # Bỏ qua nếu đã import
            if current_category_id in imported_category_ids:
                continue

            # Xác định parent_id thực tế
            actual_parent_id = False
            if category_data.get('parent_category_id', 0) != 0:
                # Tìm parent đã được import
                parent_category = self.env['shopee.category'].search([
                    ('backend_id', '=', self.backend_record.id),
                    ('shopee_category_id', '=', str(category_data['parent_category_id']))
                ], limit=1)
                actual_parent_id = parent_category.id if parent_category else False

            # Chuẩn bị giá trị import
            display_name = category_data.get('display_category_name') or \
                           category_data.get('original_category_name', '')

            values = {
                'name': display_name,
                'shopee_category_id': str(current_category_id),
                'backend_id': self.backend_record.id,
                'parent_id': actual_parent_id,
                'is_leaf': not category_data.get('has_children', False),
            }

            # Tìm category đã tồn tại
            record = self.env['shopee.category'].search([
                ('backend_id', '=', self.backend_record.id),
                ('shopee_category_id', '=', str(current_category_id))
            ], limit=1)

            # Tạo hoặc cập nhật category
            if record:
                record.write(values)
            else:
                record = self.env['shopee.category'].create(values)

            # Đánh dấu đã import
            imported_category_ids.add(current_category_id)

        return True