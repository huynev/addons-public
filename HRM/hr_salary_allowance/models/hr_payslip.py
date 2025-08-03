from odoo import models, api, fields
from .allowance_browsable import AllowanceBrowsableObject


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    def _get_baselocaldict(self, contracts):
        """Mở rộng dict cơ bản để thêm đối tượng allowances"""
        # Gọi phương thức gốc để lấy localdict
        res = super()._get_baselocaldict(contracts)

        # Tạo đối tượng allowances
        allowance_dict = self._get_allowance_dict()

        # Tạo đối tượng AllowanceBrowsableObject
        allowances = AllowanceBrowsableObject(self.employee_id.id, allowance_dict, self.env)

        # Thêm vào dict
        res.update({
            'allowances': allowances,
        })

        return res

    def _get_allowance_dict(self):
        """Lấy từ điển chứa thông tin phụ cấp lương"""
        self.ensure_one()
        result = {}

        # Tìm các phụ cấp lương trong kỳ lương
        domain = [
            ('employee_id', '=', self.employee_id.id),
            ('state', '=', 'confirmed'),
            ('start_date', '<=', self.date_to),
            '|',
            ('end_date', '>=', self.date_from),
            ('end_date', '=', False)
        ]

        allowances = self.env['salary.allowance'].search(domain)

        for allowance in allowances:
            code = allowance.allowance_type_id.code

            # Khởi tạo nếu chưa có
            if code not in result:
                result[code] = {
                    'amount': 0.0
                }

            # Cộng dồn vào kết quả
            result[code]['amount'] += allowance.amount

        return result