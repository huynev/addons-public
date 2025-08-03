from odoo import models, api, fields
from .contribution_browsable import ContributionBrowsableObject


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    def _get_baselocaldict(self, contracts):
        """Mở rộng dict cơ bản để thêm đối tượng contributions"""
        # Gọi phương thức gốc để lấy localdict
        res = super()._get_baselocaldict(contracts)

        # Tạo đối tượng contributions
        contrib_dict = self._get_contribution_dict()

        # Tạo đối tượng ContributionBrowsableObject
        contributions = ContributionBrowsableObject(self.employee_id.id, contrib_dict, self.env)

        # Thêm vào dict
        res.update({
            'contributions': contributions,
        })

        return res

    def _get_contribution_dict(self):
        """Lấy từ điển chứa thông tin đóng góp lương"""
        self.ensure_one()
        result = {}

        # Tìm các đóng góp lương trong kỳ lương
        domain = [
            ('employee_id', '=', self.employee_id.id),
            ('state', '=', 'confirmed'),
            ('start_date', '<=', self.date_to),
            '|',
            ('end_date', '>=', self.date_from),
            ('end_date', '=', False)
        ]

        contributions = self.env['salary.contribution'].search(domain)

        for contribution in contributions:
            code = contribution.contribution_type_id.code

            # Khởi tạo nếu chưa có
            if code not in result:
                result[code] = {
                    'employee_contribution': 0.0,
                    'company_contribution': 0.0
                }

            # Tính toán số tiền đóng góp
            base = contribution.calculation_base or self.contract_id.wage

            # Cộng dồn vào kết quả
            result[code]['employee_contribution'] += base * (contribution.employee_contribution_rate / 100)
            result[code]['company_contribution'] += base * (contribution.company_contribution_rate / 100)

        return result