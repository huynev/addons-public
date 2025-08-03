import logging
from odoo import fields

try:
    from odoo.addons.hr_payroll.models.base_browsable import BrowsableObject
except ImportError:
    try:
        from odoo.addons.payroll.models.base_browsable import BrowsableObject
    except ImportError:
        # Sao chép lớp BrowsableObject từ base_browsable.py
        class BaseBrowsableObject:
            def __init__(self, vals_dict):
                self.__dict__["base_fields"] = ["base_fields", "dict"]
                self.dict = vals_dict

            def __getattr__(self, attr):
                return attr in self.dict and self.dict.__getitem__(attr) or 0.0

            def __setattr__(self, attr, value):
                _fields = self.__dict__["base_fields"]
                if attr in _fields:
                    return super().__setattr__(attr, value)
                self.__dict__["dict"][attr] = value

            def __str__(self):
                return str(self.__dict__)

        class BrowsableObject(BaseBrowsableObject):
            def __init__(self, employee_id, vals_dict, env):
                super().__init__(vals_dict)
                self.base_fields += ["employee_id", "env"]
                self.employee_id = employee_id
                self.env = env

_logger = logging.getLogger(__name__)


class AllowanceBrowsableObject(BrowsableObject):
    """Đối tượng Browsable để truy cập dữ liệu phụ cấp lương"""

    def __getattr__(self, attr):
        # Nếu attr tồn tại trong dict, trả về AllowanceData
        if attr in self.dict:
            return AllowanceData(self.employee_id, attr, self.dict[attr], self.env)
        return super().__getattr__(attr)

    def __contains__(self, key):
        return key in self.dict


class AllowanceData(BrowsableObject):
    """Đối tượng lưu trữ dữ liệu cho một loại phụ cấp cụ thể"""

    def __init__(self, employee_id, code, data_dict, env):
        super().__init__(employee_id, data_dict, env)
        self.base_fields += ["code", "amount"]
        self.code = code

        # Xác định các thuộc tính từ data_dict
        if isinstance(data_dict, dict):
            self.amount = data_dict.get('amount', 0.0)
        else:
            # Trường hợp data_dict không phải dict
            self.amount = 0.0