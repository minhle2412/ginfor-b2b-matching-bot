# -*- coding: utf-8 -*-
"""
Cấu hình nguồn dữ liệu + mapping cột động.
============================================
Toàn bộ cấu hình đọc từ biến môi trường (hoặc file .env ở thư mục gốc dự án),
nên đổi bảng / đổi tên cột trên Supabase KHÔNG cần sửa code.

Các biến môi trường chính
-------------------------
SUPPLIER_SOURCE          supabase | csv   (mặc định: supabase nếu có SUPABASE_URL)
SUPABASE_URL             https://<project-ref>.supabase.co
SUPABASE_KEY             service_role key (hoặc anon key nếu bảng cho phép đọc)
SUPABASE_SUPPLIER_TABLE  tên bảng chứa doanh nghiệp supplier
SUPABASE_SUPPLIER_FILTER filter PostgREST tuỳ chọn, vd: "country=eq.Vietnam"
SUPABASE_PAGE_SIZE       số dòng mỗi lần gọi API (mặc định 1000)

Mapping cột (tuỳ chọn — bỏ trống thì hệ thống tự dò):
SUPPLIER_COL_ID, SUPPLIER_COL_NAME, SUPPLIER_COL_MST, SUPPLIER_COL_EMAIL,
SUPPLIER_COL_PHONE, SUPPLIER_COL_MAIN_INDUSTRY, SUPPLIER_COL_SUB_INDUSTRY,
SUPPLIER_COL_ADDRESS, SUPPLIER_COL_CITY, SUPPLIER_COL_TYPE,
SUPPLIER_COL_DESCRIPTION, SUPPLIER_COL_INDUSTRY_GROUP,
SUPPLIER_COL_CLASSIFICATION, SUPPLIER_COL_WEBSITE

Chạy `python -m datasource.introspect` để in ra schema thật của bảng và
đoạn .env đã điền sẵn mapping đã dò được.
"""

import logging
import os
import unicodedata
from pathlib import Path

logger = logging.getLogger("datasource.config")

BASE_DIR = Path(__file__).resolve().parent.parent

_ENV_LOADED = False


def load_env(env_file: str | None = None, override: bool = False):
    """
    Nạp biến môi trường từ file .env (nếu có python-dotenv).
    Chỉ nạp một lần trừ khi truyền env_file cụ thể.
    """
    global _ENV_LOADED
    if _ENV_LOADED and not env_file:
        return

    candidates = [env_file] if env_file else [
        str(BASE_DIR / ".env"),
        str(BASE_DIR / ".env.bot.facebook"),
    ]

    try:
        from dotenv import load_dotenv
    except ImportError:
        _ENV_LOADED = True
        return

    for path in candidates:
        if path and os.path.exists(path):
            load_dotenv(path, override=override)
    _ENV_LOADED = True


# ============================================================
# MAPPING CỘT: canonical field → (biến môi trường, các tên cột thường gặp)
# ============================================================
# Danh sách candidate được so khớp KHÔNG phân biệt hoa/thường, dấu tiếng Việt,
# khoảng trắng, gạch dưới và gạch ngang (xem normalize_key()).
FIELD_CANDIDATES: dict[str, tuple[str, list[str]]] = {
    "supplier_id": ("SUPPLIER_COL_ID", [
        "id", "supplier_id", "uuid", "company_id", "ma_doanh_nghiep",
    ]),
    "name": ("SUPPLIER_COL_NAME", [
        "Ten cong ty", "ten_cong_ty", "tencongty", "company_name", "ten_doanh_nghiep",
        "ten_cty", "name", "company", "supplier_name",
    ]),
    "mst": ("SUPPLIER_COL_MST", [
        "MST", "mst", "ma_so_thue", "masothue", "tax_code", "mst_tax_code", "tax_id",
    ]),
    "email": ("SUPPLIER_COL_EMAIL", [
        "Email", "email", "contact_email", "email_lien_he", "mail",
    ]),
    "phone": ("SUPPLIER_COL_PHONE", [
        "SDT", "sdt", "so_dien_thoai", "sodienthoai", "dien_thoai", "phone",
        "contact_phone", "phone_number", "tel", "hotline",
    ]),
    "main_industry": ("SUPPLIER_COL_MAIN_INDUSTRY", [
        "Nganh chinh", "nganh_chinh", "nganhchinh", "main_industry", "industry",
        "nganh_nghe_chinh", "nganh_nghe", "linh_vuc",
    ]),
    "sub_industry": ("SUPPLIER_COL_SUB_INDUSTRY", [
        "Nganh phu", "nganh_phu", "nganhphu", "sub_industry", "secondary_industry",
    ]),
    "address": ("SUPPLIER_COL_ADDRESS", [
        "Dia chi", "dia_chi", "diachi", "address", "dia_chi_tru_so",
    ]),
    "city": ("SUPPLIER_COL_CITY", [
        "Tinh/Thanh", "tinh_thanh", "tinhthanh", "province_city", "province",
        "city", "tinh", "thanh_pho", "khu_vuc",
    ]),
    "type": ("SUPPLIER_COL_TYPE", [
        "Loai hinh", "loai_hinh", "loaihinh", "company_type", "business_type", "type",
    ]),
    "description": ("SUPPLIER_COL_DESCRIPTION", [
        "Mo ta", "mo_ta", "mota", "description", "mo_ta_doanh_nghiep",
        "main_products", "san_pham_chinh", "products", "gioi_thieu",
    ]),
    "industry_group": ("SUPPLIER_COL_INDUSTRY_GROUP", [
        "Nhom nganh", "nhom_nganh", "nhomnganh", "industry_group", "nganh_cap_1",
    ]),
    "classification": ("SUPPLIER_COL_CLASSIFICATION", [
        "Nhóm phân loại", "Nhom phan loai", "nhom_phan_loai", "classification",
        "phan_loai", "category",
    ]),
    "website": ("SUPPLIER_COL_WEBSITE", [
        "Website", "website", "web", "url", "trang_web", "homepage",
    ]),
}

#: Những trường bắt buộc phải map được, thiếu là coi như cấu hình sai.
REQUIRED_FIELDS = ["name"]


def normalize_key(text: str) -> str:
    """
    Chuẩn hoá tên cột để so khớp: bỏ dấu tiếng Việt, hạ về chữ thường,
    loại bỏ khoảng trắng / gạch dưới / gạch ngang / dấu chấm / gạch chéo.

        "Nhóm phân loại" → "nhomphanloai"
        "Tinh/Thanh"     → "tinhthanh"
        "company_name"   → "companyname"
    """
    if not text:
        return ""
    decomposed = unicodedata.normalize("NFD", str(text))
    stripped = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    stripped = stripped.replace("đ", "d").replace("Đ", "D")
    return "".join(ch for ch in stripped.lower() if ch.isalnum())


def resolve_column_map(available_columns: list[str]) -> dict[str, str | None]:
    """
    Dò mapping canonical field → tên cột thật trong bảng.

    Thứ tự ưu tiên:
      1. Biến môi trường SUPPLIER_COL_* (nếu được đặt và cột đó tồn tại)
      2. Khớp chính xác (sau chuẩn hoá) với danh sách candidate
      3. Khớp chứa (substring) với candidate — chỉ khi chưa có cột nào được chọn

    Args:
        available_columns: danh sách tên cột thật lấy từ Supabase

    Returns:
        dict canonical_field → tên cột thật, hoặc None nếu không dò được
    """
    load_env()
    normalized = {normalize_key(col): col for col in available_columns}
    column_map: dict[str, str | None] = {}
    taken: set[str] = set()

    # Vòng 1: biến môi trường (ưu tiên tuyệt đối)
    # Cho phép khai báo nhiều cột dự phòng, ngăn cách bằng "|":
    #     SUPPLIER_COL_CITY=location|province_slug|address
    # → lấy cột đầu tiên có giá trị khác rỗng ở từng dòng.
    for field, (env_var, _candidates) in FIELD_CANDIDATES.items():
        override = os.getenv(env_var, "").strip()
        if not override:
            continue

        names = [part.strip() for part in override.split("|") if part.strip()]
        # Chỉ nhận những cột THỰC SỰ có trong nguồn dữ liệu. Nhờ vậy một file .env
        # cấu hình cho bảng Supabase không làm hỏng nguồn CSV fallback (tên cột khác
        # hẳn nhau) — những cột không tồn tại bị bỏ qua và trường đó quay về tự dò.
        actuals = [normalized[normalize_key(n)] for n in names if normalize_key(n) in normalized]
        ignored = [n for n in names if normalize_key(n) not in normalized]
        if ignored:
            logger.warning(
                f"{env_var}: bỏ qua cột không tồn tại trong nguồn dữ liệu: {', '.join(ignored)}"
            )
        if not actuals:
            continue

        column_map[field] = actuals[0] if len(actuals) == 1 else actuals
        taken.update(actuals)

    # Vòng 2: khớp chính xác theo candidate
    for field, (_env_var, candidates) in FIELD_CANDIDATES.items():
        if column_map.get(field):
            continue
        for candidate in candidates:
            actual = normalized.get(normalize_key(candidate))
            if actual and actual not in taken:
                column_map[field] = actual
                taken.add(actual)
                break

    # Vòng 3: khớp chứa (bắt các tên như "ten_cong_ty_day_du")
    for field, (_env_var, candidates) in FIELD_CANDIDATES.items():
        if column_map.get(field):
            continue
        for candidate in candidates:
            key = normalize_key(candidate)
            if len(key) < 4:          # tránh khớp bừa với candidate quá ngắn ("id", "mst")
                continue
            for norm_col, actual in normalized.items():
                if actual in taken:
                    continue
                if key in norm_col or norm_col in key:
                    column_map[field] = actual
                    taken.add(actual)
                    break
            if column_map.get(field):
                break

    # Đảm bảo đủ key, thiếu thì None
    for field in FIELD_CANDIDATES:
        column_map.setdefault(field, None)

    return column_map


# ============================================================
# Getters cấu hình Supabase
# ============================================================
def supabase_url() -> str:
    load_env()
    return os.getenv("SUPABASE_URL", "").strip().rstrip("/")


def supabase_key() -> str:
    load_env()
    # Chấp nhận nhiều tên biến để tương thích với các quy ước đặt tên khác nhau
    for var in ("SUPABASE_KEY", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_SERVICE_KEY", "SUPABASE_ANON_KEY"):
        value = os.getenv(var, "").strip()
        if value:
            return value
    return ""


def supplier_table() -> str:
    load_env()
    return os.getenv("SUPABASE_SUPPLIER_TABLE", "suppliers").strip()


def supplier_filter() -> str:
    load_env()
    return os.getenv("SUPABASE_SUPPLIER_FILTER", "").strip()


def page_size() -> int:
    load_env()
    try:
        return max(1, min(10000, int(os.getenv("SUPABASE_PAGE_SIZE", "1000"))))
    except ValueError:
        return 1000


def source_kind() -> str:
    """Trả về 'supabase' hoặc 'csv'."""
    load_env()
    explicit = os.getenv("SUPPLIER_SOURCE", "").strip().lower()
    if explicit in ("supabase", "csv"):
        return explicit
    return "supabase" if supabase_url() and supabase_key() else "csv"


def csv_path() -> str:
    load_env()
    return os.getenv("SUPPLIER_CSV_PATH", str(BASE_DIR / "Business_dataset.csv"))


def cache_dir() -> Path:
    d = BASE_DIR / ".cache"
    d.mkdir(exist_ok=True)
    return d
