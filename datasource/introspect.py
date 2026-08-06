# -*- coding: utf-8 -*-
"""
Công cụ kiểm tra kết nối Supabase và dò schema bảng supplier.
===============================================================
Chạy:

    python -m datasource.introspect                  # bảng lấy từ .env
    python -m datasource.introspect --table my_table
    python -m datasource.introspect --list-tables    # liệt kê bảng qua OpenAPI

In ra:
  1. Trạng thái kết nối + số dòng trong bảng
  2. Danh sách cột thật của bảng
  3. Mapping canonical field → cột thật mà hệ thống đã dò được
  4. Đoạn cấu hình .env đã điền sẵn để bạn dán vào (chỉnh tay nếu dò sai)
  5. 3 dòng dữ liệu mẫu sau khi đã chuẩn hoá
"""

import argparse
import json
import sys

from .config import FIELD_CANDIDATES, REQUIRED_FIELDS, load_env, supabase_key, supabase_url
from .supabase_source import SupabaseSupplierSource, SupabaseError


def list_tables(url: str, key: str) -> list[str]:
    """Liệt kê các bảng/view mà key hiện tại đọc được, qua OpenAPI spec của PostgREST."""
    import requests

    resp = requests.get(
        f"{url}/rest/v1/",
        headers={"apikey": key, "Authorization": f"Bearer {key}", "Accept": "application/openapi+json"},
        timeout=30,
    )
    resp.raise_for_status()
    paths = resp.json().get("paths", {})
    return sorted(p.lstrip("/") for p in paths if p not in ("/",) and not p.startswith("/rpc/"))


def count_rows(source: SupabaseSupplierSource) -> str:
    """Đếm số dòng bằng header Content-Range của PostgREST."""
    import requests

    headers = source._headers()
    headers["Prefer"] = "count=exact"
    headers["Range"] = "0-0"
    resp = requests.get(source.endpoint, headers=headers, params={"select": "*"}, timeout=30)
    content_range = resp.headers.get("content-range", "")
    return content_range.split("/")[-1] if "/" in content_range else "?"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Kiểm tra kết nối & dò schema bảng supplier trên Supabase.")
    parser.add_argument("--table", help="Tên bảng cần kiểm tra (mặc định: SUPABASE_SUPPLIER_TABLE trong .env)")
    parser.add_argument("--list-tables", action="store_true", help="Liệt kê tất cả bảng key hiện tại đọc được")
    parser.add_argument("--env", help="Đường dẫn file .env cụ thể")
    parser.add_argument("--sample", type=int, default=3, help="Số dòng dữ liệu mẫu in ra (mặc định 3)")
    args = parser.parse_args(argv)

    load_env(args.env, override=True)

    url, key = supabase_url(), supabase_key()
    print("=" * 72)
    print("KIỂM TRA KẾT NỐI SUPABASE")
    print("=" * 72)
    print(f"  SUPABASE_URL : {url or '(chưa cấu hình)'}")
    print(f"  SUPABASE_KEY : {(key[:12] + '...' + key[-4:]) if key else '(chưa cấu hình)'}")

    if not url or not key:
        print("\n❌ Thiếu SUPABASE_URL hoặc SUPABASE_KEY.")
        print("   Tạo file .env ở thư mục gốc dự án — xem mẫu tại .env.example")
        return 1

    if args.list_tables:
        try:
            tables = list_tables(url, key)
            print(f"\n📋 {len(tables)} bảng/view đọc được:")
            for t in tables:
                print(f"   • {t}")
        except Exception as e:
            print(f"\n❌ Không liệt kê được bảng: {e}")
            return 1
        return 0

    try:
        source = SupabaseSupplierSource(table=args.table, allow_stale_cache=False)
    except SupabaseError as e:
        print(f"\n❌ {e}")
        return 1

    print(f"  Bảng         : {source.table}")

    try:
        columns = source.fetch_columns()
    except SupabaseError as e:
        print(f"\n❌ {e}")
        print("\n💡 Chạy `python -m datasource.introspect --list-tables` để xem các bảng khả dụng.")
        return 1

    print(f"  Số dòng      : {count_rows(source)}")
    print(f"\n✅ Kết nối OK. Bảng '{source.table}' có {len(columns)} cột:")
    for col in columns:
        print(f"   • {col}")

    try:
        column_map = source.ensure_column_map()
    except SupabaseError as e:
        column_map = source.column_map
        print(f"\n⚠️ {e}")

    print("\n" + "=" * 72)
    print("MAPPING ĐÃ DÒ ĐƯỢC (canonical field → cột thật)")
    print("=" * 72)
    for field in FIELD_CANDIDATES:
        actual = column_map.get(field)
        flag = "✅" if actual else ("❌" if field in REQUIRED_FIELDS else "➖")
        print(f"  {flag} {field:<16} → {actual or '(không dò được)'}")

    print("\n" + "=" * 72)
    print("DÁN ĐOẠN SAU VÀO FILE .env (sửa lại dòng nào dò sai)")
    print("=" * 72)
    print(f"SUPPLIER_SOURCE=supabase")
    print(f"SUPABASE_SUPPLIER_TABLE={source.table}")
    for field, (env_var, _cands) in FIELD_CANDIDATES.items():
        actual = column_map.get(field)
        prefix = "" if actual else "# "
        print(f"{prefix}{env_var}={actual or ''}")

    unmapped_required = [f for f in REQUIRED_FIELDS if not column_map.get(f)]
    if unmapped_required:
        print(f"\n❌ Còn thiếu trường bắt buộc: {', '.join(unmapped_required)} — phải điền tay.")
        return 1

    if args.sample > 0:
        print("\n" + "=" * 72)
        print(f"{args.sample} DÒNG DỮ LIỆU MẪU SAU CHUẨN HOÁ")
        print("=" * 72)
        try:
            rows = source._fetch_all(max_rows=args.sample)
            for i, row in enumerate(rows, 1):
                print(f"\n--- Doanh nghiệp #{i} ---")
                print(json.dumps(row, ensure_ascii=False, indent=2))
        except SupabaseError as e:
            print(f"⚠️ Không lấy được dữ liệu mẫu: {e}")

    print("\n✅ Cấu hình hợp lệ. Matching Engine đã có thể dùng nguồn Supabase này.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
