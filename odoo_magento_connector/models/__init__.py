# -*- coding: utf-8 -*-
# File: models/__init__.py

from . import magento_backend
from . import magento_binding
from . import magento_website
from . import magento_store
from . import magento_storeview

# Import các module trong thư mục con product
from . import product

# Kiểm tra và tạo thư mục partner trước khi import
try:
    from . import partner
except ImportError:
    import logging
    logging.getLogger(__name__).warning("Could not import 'partner' module - directory may not exist")

# Kiểm tra và tạo thư mục sale trước khi import
try:
    from . import sale
except ImportError:
    import logging
    logging.getLogger(__name__).warning("Could not import 'sale' module - directory may not exist")

# Kiểm tra và tạo thư mục stock trước khi import
try:
    from . import stock
except ImportError:
    import logging
    logging.getLogger(__name__).warning("Could not import 'stock' module - directory may not exist")