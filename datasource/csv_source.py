# -*- coding: utf-8 -*-
"""
Nguồn dữ liệu CSV (dữ liệu mẫu Business_dataset.csv).
Giữ lại để chạy offline / fallback khi Supabase không truy cập được.
"""

import csv
import hashlib
import logging
import os

from .base import SupplierSource, normalize_company, pick_value
from .config import resolve_column_map, csv_path as default_csv_path

logger = logging.getLogger("datasource.csv")


class CsvSupplierSource(SupplierSource):
    """Đọc danh sách doanh nghiệp từ file CSV, mapping cột tự động."""

    source_id = "csv"

    def __init__(self, path: str | None = None):
        self.path = path or default_csv_path()
        self.column_map: dict[str, str | None] = {}

    def describe(self) -> str:
        return f"CSV: {os.path.basename(self.path)}"

    def load(self, force_refresh: bool = False) -> list[dict]:
        # CSV luôn đọc lại từ đĩa nên force_refresh không làm thay đổi hành vi.
        if not os.path.exists(self.path):
            raise FileNotFoundError(f"Không tìm thấy file CSV: {self.path}")

        with open(self.path, mode="r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames or []
            self.column_map = resolve_column_map(headers)

            companies = []
            for idx, row in enumerate(reader):
                raw = {
                    field: pick_value(row, spec)
                    for field, spec in self.column_map.items()
                }
                company = normalize_company(raw)
                if not company["supplier_id"]:
                    company["supplier_id"] = company["mst"] or f"csv:{idx}"
                if company["name"]:
                    companies.append(company)

        if not companies:
            logger.error(
                f"❌ Đọc {self.path} nhưng không có doanh nghiệp nào hợp lệ. "
                f"Cột tên công ty đang map tới: {self.column_map.get('name')!r}. "
                f"Các cột có trong file: {', '.join(headers)}"
            )
        else:
            logger.info(f"Đã đọc {len(companies)} doanh nghiệp từ {self.path}")
        return companies

    def content_hash(self) -> str:
        """MD5 của file CSV (giữ nguyên cách tính cũ để cache embeddings vẫn dùng lại được)."""
        if not os.path.exists(self.path):
            return ""
        hasher = hashlib.md5()
        with open(self.path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def cache_path(self) -> str:
        return self.path + ".embeddings.pkl"
