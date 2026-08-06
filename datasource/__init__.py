# -*- coding: utf-8 -*-
"""
Data Source Layer — Nguồn dữ liệu doanh nghiệp supplier.
==========================================================
Tách rời việc "lấy danh sách doanh nghiệp" khỏi Matching Engine, cho phép
chuyển đổi giữa dữ liệu mẫu (CSV) và dữ liệu chính thức (Supabase) mà không
phải sửa logic matching.

Cách dùng phổ biến nhất:

    from datasource import get_supplier_source
    source = get_supplier_source()        # tự chọn theo SUPPLIER_SOURCE trong .env
    companies = source.load()

Ép dùng một nguồn cụ thể:

    from datasource import SupabaseSupplierSource, CsvSupplierSource
    source = SupabaseSupplierSource()
    source = CsvSupplierSource("Business_dataset.csv")
"""

from .base import SupplierSource, CANONICAL_FIELDS
from .csv_source import CsvSupplierSource
from .supabase_source import SupabaseSupplierSource, SupabaseError
from .factory import get_supplier_source

__all__ = [
    "SupplierSource",
    "CANONICAL_FIELDS",
    "CsvSupplierSource",
    "SupabaseSupplierSource",
    "SupabaseError",
    "get_supplier_source",
]
