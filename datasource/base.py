# -*- coding: utf-8 -*-
"""
Giao diện chung cho mọi nguồn dữ liệu doanh nghiệp supplier.

Mọi nguồn (CSV, Supabase, ...) đều phải trả về danh sách dict với cùng bộ
"canonical fields" bên dưới, để Matching Engine không cần biết dữ liệu đến
từ đâu.
"""

from abc import ABC, abstractmethod

# Bộ trường chuẩn hoá mà Matching Engine sử dụng.
# Mọi nguồn dữ liệu đều phải sinh ra đủ các key này (giá trị rỗng nếu thiếu).
CANONICAL_FIELDS = [
    "supplier_id",     # ID định danh trong nguồn (Supabase PK / MST / STT dòng CSV)
    "name",            # Tên công ty
    "mst",             # Mã số thuế
    "email",           # Email liên hệ
    "phone",           # Số điện thoại
    "main_industry",   # Ngành chính
    "sub_industry",    # Ngành phụ
    "address",         # Địa chỉ
    "city",            # Tỉnh/Thành
    "type",            # Loại hình doanh nghiệp
    "description",     # Mô tả / sản phẩm chính
    "industry_group",  # Nhóm ngành
    "classification",  # Nhóm phân loại
    "website",         # Website
]


def blank_company() -> dict:
    """Trả về một record rỗng đủ toàn bộ canonical fields."""
    return {field: "" for field in CANONICAL_FIELDS}


def pick_value(row: dict, col_spec):
    """
    Lấy giá trị của một canonical field từ một dòng dữ liệu thô.

    `col_spec` có thể là:
      - None            → trả về ""
      - "ten_cot"       → lấy đúng cột đó
      - ["a", "b", "c"] → lấy cột đầu tiên có giá trị khác rỗng (ưu tiên trái sang phải)

    Dạng list dùng khi không cột nào phủ đủ dữ liệu, ví dụ tỉnh/thành nằm rải
    ở `location`, `province_slug` hoặc `address` tuỳ từng dòng.
    """
    if not col_spec:
        return ""
    if isinstance(col_spec, str):
        return row.get(col_spec) or ""
    for col in col_spec:
        value = row.get(col)
        if value not in (None, ""):
            return value
    return ""


def flatten_columns(col_spec) -> list[str]:
    """Trả về danh sách tên cột thật của một col_spec (str hoặc list)."""
    if not col_spec:
        return []
    return [col_spec] if isinstance(col_spec, str) else list(col_spec)


def normalize_company(raw: dict) -> dict:
    """
    Chuẩn hoá một record về đúng bộ canonical fields.
    Ép mọi giá trị về str đã strip, None → "".
    """
    company = blank_company()
    for field in CANONICAL_FIELDS:
        value = raw.get(field)
        if value is None:
            company[field] = ""
        elif isinstance(value, str):
            company[field] = value.strip()
        else:
            company[field] = str(value).strip()
    return company


class SupplierSource(ABC):
    """
    Nguồn dữ liệu doanh nghiệp supplier.

    Ngoài `load()`, mỗi nguồn còn cung cấp:
      - `source_id`     : định danh ngắn, dùng đặt tên file cache embeddings
      - `content_hash()`: vân tay dữ liệu, dùng để phát hiện cache embeddings đã cũ
      - `cache_path()`  : nơi lưu cache embeddings của nguồn này
    """

    #: Định danh ngắn gọn của nguồn (dùng trong log và tên file cache)
    source_id = "unknown"

    @abstractmethod
    def load(self, force_refresh: bool = False) -> list[dict]:
        """
        Tải toàn bộ doanh nghiệp, trả về list dict theo CANONICAL_FIELDS.

        Args:
            force_refresh: bỏ qua dữ liệu đã cache trong bộ nhớ, tải lại từ nguồn.
        """

    @abstractmethod
    def content_hash(self) -> str:
        """
        Vân tay của dữ liệu hiện tại. Khi giá trị này đổi, cache embeddings
        sẽ được coi là cũ và tự động build lại.
        """

    @abstractmethod
    def cache_path(self) -> str:
        """Đường dẫn file cache embeddings cho nguồn này."""

    def describe(self) -> str:
        """Mô tả ngắn để hiển thị trong log/Discord."""
        return self.source_id
