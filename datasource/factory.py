# -*- coding: utf-8 -*-
"""
Factory chọn nguồn dữ liệu supplier theo cấu hình .env.
"""

import logging

from .base import SupplierSource
from .config import source_kind, csv_path
from .csv_source import CsvSupplierSource
from .supabase_source import SupabaseSupplierSource, SupabaseError

logger = logging.getLogger("datasource.factory")


def get_supplier_source(kind: str | None = None, fallback_to_csv: bool = True) -> SupplierSource:
    """
    Trả về nguồn dữ liệu supplier theo cấu hình.

    Args:
        kind: 'supabase' | 'csv'. Bỏ trống → đọc SUPPLIER_SOURCE trong .env
              (mặc định 'supabase' nếu đã có SUPABASE_URL + SUPABASE_KEY).
        fallback_to_csv: khi Supabase lỗi cấu hình, tự lùi về CSV thay vì raise.

    Returns:
        SupplierSource sẵn sàng gọi .load()
    """
    kind = (kind or source_kind()).lower()

    if kind == "csv":
        logger.info(f"📄 Nguồn dữ liệu supplier: CSV ({csv_path()})")
        return CsvSupplierSource()

    try:
        source = SupabaseSupplierSource()
        logger.info(f"🗄️  Nguồn dữ liệu supplier: Supabase (bảng '{source.table}')")
        return source
    except SupabaseError as e:
        if not fallback_to_csv:
            raise
        logger.error(f"❌ Không khởi tạo được Supabase source: {e}")
        logger.warning(f"⚠️ Lùi về nguồn CSV: {csv_path()}")
        logger.warning(
            "   Lưu ý: các biến SUPPLIER_COL_* trong .env đang cấu hình cho bảng Supabase "
            "sẽ được tự động bỏ qua, hệ thống dò lại tên cột theo header của file CSV."
        )
        return CsvSupplierSource()
