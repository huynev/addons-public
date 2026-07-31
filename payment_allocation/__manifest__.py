# -*- coding: utf-8 -*-
{
    'name': 'Phân Bổ Thanh Toán Hoá Đơn (Payment Allocation)',
    'version': '17.0.1.0.0',
    'category': 'Accounting/Accounting',
    'summary': 'Phân bổ 1 khoản thanh toán cho nhiều hoá đơn theo số tiền tuỳ chỉnh + báo cáo thanh toán theo khách hàng',
    'description': """
Payment Allocation
===================
- Cho phép phân bổ (allocate) 1 khoản thanh toán (account.payment) cho nhiều
  hoá đơn của cùng khách hàng, với số tiền phân bổ cho từng hoá đơn do người
  dùng tự nhập (không bắt buộc theo thứ tự trả đủ từng hoá đơn như mặc định
  của Odoo).
- Báo cáo: xem theo từng khách hàng, trong khoảng thời gian đã chọn, khách
  đã thanh toán bao nhiêu và hiện còn nợ lại bao nhiêu.

Lưu ý: module tương tác trực tiếp với cơ chế đối soát (reconciliation) kế
toán cốt lõi của Odoo (account.partial.reconcile). Vui lòng kiểm thử kỹ
trên môi trường test/staging trước khi dùng cho dữ liệu thật.
    """,
    'author': 'Custom Development',
    'license': 'LGPL-3',
    'depends': ['account'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/payment_allocation_wizard_views.xml',
        'wizard/customer_payment_report_wizard_views.xml',
        'wizard/customer_payment_detail_report_wizard_views.xml',
        'views/account_payment_views.xml',
        'views/payment_allocation_report_views.xml',
        'views/menu_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
