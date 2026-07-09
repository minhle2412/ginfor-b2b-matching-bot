# -*- coding: utf-8 -*-
"""
Contact Extractor — Trích xuất SĐT và Email từ bài viết Facebook.
====================================================================
Nhận diện các dạng số điện thoại Việt Nam (di động, cố định) và
địa chỉ email từ nội dung bài viết trên các group Facebook.
"""

import re
from .models import ContactInfo


# ===================== PHONE PATTERNS =====================

# Regex tìm ứng viên số điện thoại (bắt đầu bằng +84 hoặc 0, theo sau bởi 9-10 chữ số có dấu phân cách tùy chọn)
_PHONE_CANDIDATE_REGEX = re.compile(
    r"(?:\+84|0)(?:[\s.\-]?\d){9,10}",
    re.UNICODE
)

# Các đầu số di động hợp lệ sau khi chuẩn hóa về dạng 0xxx...
_MOBILE_PREFIXES = ("03", "05", "07", "08", "09")
_LANDLINE_PREFIXES = ("02",)

# ===================== EMAIL PATTERN =====================
_EMAIL_REGEX = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
    re.UNICODE
)


def extract_phone_numbers(text: str) -> list[str]:
    """
    Trích xuất số điện thoại Việt Nam từ text.

    Hỗ trợ các dạng:
    - Di động: 0912345678, 0912.345.678, 0912-345-678, 0912 345 678
    - Có prefix +84: +84912345678
    - Cố định: 02812345678, 028.1234.5678

    Loại bỏ:
    - Chuỗi số không khớp đầu số di động/cố định Việt Nam (như MST bắt đầu bằng 01)
    - Các số trùng lặp

    Args:
        text: Nội dung bài viết Facebook

    Returns:
        Danh sách SĐT đã chuẩn hóa (dạng 0xxxxxxxxx)
    """
    if not text:
        return []

    cleaned = text.replace("\n", " ")
    phones = []

    for match in _PHONE_CANDIDATE_REGEX.finditer(cleaned):
        full = match.group(0)
        # Loại bỏ các ký tự phân tách để kiểm tra
        digits = re.sub(r"[\s.\-+]", "", full)
        
        # Chuẩn hóa đầu số quốc tế +84 hoặc 84 về 0
        if digits.startswith("84"):
            digits = "0" + digits[2:]
            
        # Kiểm tra tính hợp lệ của số di động (10 số)
        if len(digits) == 10 and digits.startswith(_MOBILE_PREFIXES):
            phones.append(digits)
        # Kiểm tra tính hợp lệ của số cố định (10 hoặc 11 số)
        elif len(digits) in (10, 11) and digits.startswith(_LANDLINE_PREFIXES):
            phones.append(digits)

    # Loại bỏ trùng lặp, giữ nguyên thứ tự
    seen: set[str] = set()
    unique: list[str] = []
    for p in phones:
        if p not in seen:
            seen.add(p)
            unique.append(p)

    return unique


def extract_emails(text: str) -> list[str]:
    """
    Trích xuất địa chỉ email từ text.

    Args:
        text: Nội dung bài viết Facebook

    Returns:
        Danh sách email (lowercase, không trùng lặp)
    """
    if not text:
        return []

    raw_emails = _EMAIL_REGEX.findall(text)

    seen: set[str] = set()
    unique: list[str] = []
    for e in raw_emails:
        lower = e.lower()
        if lower not in seen:
            seen.add(lower)
            unique.append(lower)

    return unique


def extract_contact_info(text: str) -> ContactInfo:
    """
    Trích xuất toàn bộ thông tin liên hệ từ bài viết Facebook.

    Args:
        text: Nội dung bài viết

    Returns:
        ContactInfo chứa danh sách phones và emails tìm được
    """
    return ContactInfo(
        phones=extract_phone_numbers(text),
        emails=extract_emails(text),
    )
