# -*- coding: utf-8 -*-
"""
Nguồn dữ liệu Supabase (dữ liệu doanh nghiệp supplier chính thức).
====================================================================
Gọi thẳng PostgREST API của Supabase bằng `requests` — không cần cài thêm
SDK `supabase-py`.

Điểm chính:
  * Tự phân trang (limit/offset) để lấy hết bảng, kể cả > 1000 dòng.
  * Mapping cột động: đọc schema thật rồi dò tên cột (xem datasource/config.py).
  * Cache offline: mỗi lần fetch thành công ghi ra .cache/suppliers_supabase.json;
    khi mất mạng / Supabase lỗi sẽ tự dùng lại cache thay vì sập cả bot.
"""

import hashlib
import json
import logging
import os
import time

from .base import SupplierSource, flatten_columns, normalize_company, pick_value
from .config import (
    REQUIRED_FIELDS,
    cache_dir,
    page_size as default_page_size,
    resolve_column_map,
    supabase_key,
    supabase_url,
    supplier_filter,
    supplier_table,
)

logger = logging.getLogger("datasource.supabase")


class SupabaseError(RuntimeError):
    """Lỗi khi giao tiếp với Supabase REST API."""


def _quote_ident(column: str) -> str:
    """
    Bọc nháy kép cho tên cột chứa ký tự đặc biệt (khoảng trắng, dấu tiếng Việt,
    dấu chấm, gạch chéo...). Cột tên bình thường giữ nguyên để URL gọn hơn.
    """
    if column and all(ch.isascii() and (ch.isalnum() or ch == "_") for ch in column):
        return column
    return f'"{column}"'


class SupabaseSupplierSource(SupplierSource):
    """Tải danh sách doanh nghiệp supplier từ một bảng trên Supabase."""

    source_id = "supabase"

    def __init__(
        self,
        url: str | None = None,
        key: str | None = None,
        table: str | None = None,
        column_map: dict | None = None,
        page_size: int | None = None,
        rest_filter: str | None = None,
        allow_stale_cache: bool = True,
        timeout: int = 30,
    ):
        self.url = (url or supabase_url()).rstrip("/")
        self.key = key or supabase_key()
        self.table = table or supplier_table()
        self.page_size = page_size or default_page_size()
        self.rest_filter = rest_filter if rest_filter is not None else supplier_filter()
        self.allow_stale_cache = allow_stale_cache
        self.timeout = timeout

        self.column_map: dict[str, str | None] = column_map or {}
        self.available_columns: list[str] = []
        self._companies: list[dict] | None = None
        self._content_hash: str | None = None

        if not self.url or not self.key:
            raise SupabaseError(
                "Thiếu SUPABASE_URL hoặc SUPABASE_KEY. "
                "Khai báo trong file .env ở thư mục gốc dự án (xem .env.example)."
            )

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------
    @property
    def endpoint(self) -> str:
        return f"{self.url}/rest/v1/{self.table}"

    def _headers(self) -> dict:
        return {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Accept": "application/json",
            "Accept-Profile": os.getenv("SUPABASE_SCHEMA", "public"),
        }

    def _get(self, params: dict, retries: int = 3) -> list[dict]:
        """GET tới PostgREST, có retry với backoff cho lỗi tạm thời."""
        import requests

        last_error = None
        for attempt in range(retries):
            try:
                resp = requests.get(
                    self.endpoint,
                    headers=self._headers(),
                    params=params,
                    timeout=self.timeout,
                )
                if resp.status_code == 200:
                    return resp.json()

                # 4xx là lỗi cấu hình — retry vô nghĩa
                if 400 <= resp.status_code < 500:
                    raise SupabaseError(
                        f"Supabase trả về {resp.status_code} cho bảng '{self.table}': "
                        f"{resp.text[:300]}"
                    )
                last_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
            except SupabaseError:
                raise
            except Exception as e:                       # lỗi mạng / timeout
                last_error = f"{type(e).__name__}: {e}"

            if attempt < retries - 1:
                wait = 2 ** attempt
                logger.warning(f"Gọi Supabase thất bại ({last_error}). Thử lại sau {wait}s...")
                time.sleep(wait)

        raise SupabaseError(f"Không gọi được Supabase sau {retries} lần: {last_error}")

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------
    def fetch_columns(self) -> list[str]:
        """Lấy danh sách tên cột thật của bảng (đọc 1 dòng mẫu)."""
        if self.available_columns:
            return self.available_columns

        rows = self._get({"select": "*", "limit": 1})
        if not rows:
            raise SupabaseError(
                f"Bảng '{self.table}' rỗng hoặc RLS đang chặn — không đọc được schema. "
                f"Kiểm tra tên bảng và quyền của key đang dùng."
            )
        self.available_columns = list(rows[0].keys())
        return self.available_columns

    def ensure_column_map(self) -> dict[str, str | None]:
        """Dò (hoặc kiểm tra) mapping cột, raise nếu thiếu trường bắt buộc."""
        if not self.column_map:
            columns = self.fetch_columns()
            self.column_map = resolve_column_map(columns)

        missing = [f for f in REQUIRED_FIELDS if not self.column_map.get(f)]
        if missing:
            raise SupabaseError(
                f"Không dò được cột cho trường bắt buộc: {', '.join(missing)}.\n"
                f"Các cột hiện có trong bảng '{self.table}': {', '.join(self.available_columns)}\n"
                f"Hãy chỉ định thủ công trong .env, ví dụ: SUPPLIER_COL_NAME=ten_cong_ty\n"
                f"Gợi ý: chạy `python -m datasource.introspect` để xem mapping đề xuất."
            )

        mapped = {k: v for k, v in self.column_map.items() if v}
        logger.info(f"Mapping cột Supabase ({len(mapped)}/{len(self.column_map)} trường): {mapped}")
        return self.column_map

    # ------------------------------------------------------------------
    # Load
    # ------------------------------------------------------------------
    def load(self, force_refresh: bool = False) -> list[dict]:
        """
        Tải toàn bộ doanh nghiệp từ Supabase (có phân trang).
        Nếu gọi API thất bại và có cache offline thì dùng cache.
        """
        if self._companies is not None and not force_refresh:
            return self._companies

        try:
            companies = self._fetch_all()
            self._write_cache(companies)
        except SupabaseError as e:
            cached = self._read_cache() if self.allow_stale_cache else None
            if cached is None:
                raise
            logger.error(f"❌ Không tải được dữ liệu từ Supabase: {e}")
            logger.warning(f"⚠️ Dùng tạm cache offline: {len(cached)} doanh nghiệp từ {self._cache_file()}")
            companies = cached

        self._companies = companies
        self._content_hash = None
        return companies

    def _fetch_all(self, max_rows: int | None = None) -> list[dict]:
        """
        Tải dữ liệu từ Supabase.

        Args:
            max_rows: dừng sớm sau khi đã lấy đủ chừng này dòng (dùng để xem mẫu).
                      None = tải toàn bộ bảng.
        """
        column_map = self.ensure_column_map()

        # Chỉ select đúng những cột cần dùng cho matching → giảm băng thông
        select_cols = sorted({c for spec in column_map.values() for c in flatten_columns(spec)})
        select = ",".join(_quote_ident(c) for c in select_cols)

        # Cột dùng để sắp xếp ổn định khi phân trang (phải là một cột đơn)
        order_candidates = flatten_columns(column_map.get("supplier_id")) or flatten_columns(column_map.get("name"))
        order_col = order_candidates[0] if order_candidates else None

        companies: list[dict] = []
        offset = 0
        page = 0
        t0 = time.time()

        while True:
            batch_size = self.page_size
            if max_rows is not None:
                batch_size = min(batch_size, max_rows - len(companies))
                if batch_size <= 0:
                    break

            params = {"select": select, "limit": batch_size, "offset": offset}
            if order_col:
                params["order"] = f"{_quote_ident(order_col)}.asc"
            if self.rest_filter:
                for clause in self.rest_filter.split("&"):
                    if "=" in clause:
                        k, v = clause.split("=", 1)
                        params[k.strip()] = v.strip()

            rows = self._get(params)
            if not rows:
                break

            for row in rows:
                raw = {field: pick_value(row, spec) for field, spec in column_map.items()}
                company = normalize_company(raw)
                if not company["supplier_id"]:
                    company["supplier_id"] = company["mst"] or f"supabase:{offset + len(companies)}"
                if company["name"]:
                    companies.append(company)

            page += 1
            offset += len(rows)
            logger.info(f"   ↳ Trang {page}: +{len(rows)} dòng (tổng {len(companies)} DN hợp lệ)")

            if len(rows) < batch_size:
                break

        logger.info(
            f"✅ Đã tải {len(companies)} doanh nghiệp từ Supabase "
            f"(bảng '{self.table}', {page} trang, {time.time() - t0:.1f}s)"
        )
        return companies

    # ------------------------------------------------------------------
    # Cache offline
    # ------------------------------------------------------------------
    def _cache_file(self) -> str:
        safe_table = "".join(ch if ch.isalnum() else "_" for ch in self.table)
        return str(cache_dir() / f"suppliers_supabase_{safe_table}.json")

    def _write_cache(self, companies: list[dict]):
        try:
            with open(self._cache_file(), "w", encoding="utf-8") as f:
                json.dump(
                    {"table": self.table, "fetched_at": time.time(), "companies": companies},
                    f, ensure_ascii=False,
                )
        except Exception as e:
            logger.warning(f"⚠️ Không ghi được cache offline: {e}")

    def _read_cache(self) -> list[dict] | None:
        path = self._cache_file()
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f).get("companies")
        except Exception as e:
            logger.warning(f"⚠️ Không đọc được cache offline: {e}")
            return None

    # ------------------------------------------------------------------
    # SupplierSource interface
    # ------------------------------------------------------------------
    def content_hash(self) -> str:
        """
        SHA-256 của toàn bộ nội dung dữ liệu đã tải.
        Dữ liệu Supabase đổi (thêm/sửa/xoá DN) → hash đổi → embeddings tự build lại.
        """
        if self._content_hash:
            return self._content_hash

        companies = self.load()
        hasher = hashlib.sha256()
        for c in companies:
            hasher.update(
                f"{c['supplier_id']}|{c['name']}|{c['main_industry']}|{c['description']}".encode("utf-8")
            )
        self._content_hash = hasher.hexdigest()
        return self._content_hash

    def cache_path(self) -> str:
        safe_table = "".join(ch if ch.isalnum() else "_" for ch in self.table)
        return str(cache_dir() / f"embeddings_supabase_{safe_table}.pkl")

    def describe(self) -> str:
        return f"Supabase: {self.table}"
