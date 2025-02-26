{
    'name': 'Magento Connector (Multi-Store)',
    'version': '1.0.0',
    'category': 'Connector',
    'summary': 'Connect Odoo with Multiple Magento Stores',
    'author': '(Wokwy) quochuy.software@gmail.com + claude.ai',
    'website': 'https://www.yourcompany.com',
    'license': 'AGPL-3',
    'description': """
Magento Connector with Multi-Store Support
=========================================
Connect Odoo with multiple Magento websites and stores.
    """,
    'depends': [
        'connector',
        'component',
        'queue_job',
        'product',
        'sale',
    ],
    'data': [
        'security/ir.model.access.csv',
        # 'security/security.xml',
        # 'data/magento_data.xml',
        # 'data/queue_job_data.xml',
        'views/magento_backend_view.xml',
        'views/magento_website_view.xml',
        'views/magento_store_view.xml',
        'views/magento_storeview_view.xml',
        'views/product_view.xml',
        # 'views/partner_view.xml',
        # 'views/sale_view.xml',
        # 'views/stock_view.xml',
        'wizards/views/import_products_wizard_view.xml',
        'wizards/views/import_orders_wizard_view.xml',
    ],
    'demo': [],
    'installable': True,
    'application': False,
    'auto_install': False,
}