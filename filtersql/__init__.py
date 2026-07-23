# -*- coding: utf-8 -*-
"""
SQL Backend Library for AI, Datatables and Frontend Apps
"""

from .sql import (
    Datasource,
    filtersql,
    FilterSQLError,
    ValidationError,
    ConfigurationError,
    InvalidIdentifierError,
)
from .__version__ import __version__

__all__ = [
    "Datasource",
    "filtersql",
    "FilterSQLError",
    "ValidationError",
    "ConfigurationError",
    "InvalidIdentifierError",
    "__version__",
]

__title__ = "filtersql"
__description__ = "SQL Backend Library for AI, Datatables and Frontend Apps"
__url__ = "https://github.com/fthiella/filtersql"
__uri__ = __url__
__doc__ = __description__ + " <" + __uri__ + ">"
__author__ = "Federico Thiella"
__email__ = "fthiella@gmail.com"
__license__ = "MIT"
__copyright__ = "Copyright (c) 2026 Federico Thiella"
