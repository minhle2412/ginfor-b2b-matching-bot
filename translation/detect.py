# -*- coding: utf-8 -*-
"""
Phát hiện ngôn ngữ bằng heuristic — không cần thư viện ngoài.

Chỉ cần phân biệt "tiếng Việt" với "không phải tiếng Việt", nên hai tín hiệu sau
là đủ và rất đáng tin:
  1. Ký tự có dấu riêng của tiếng Việt (ă â đ ê ô ơ ư + thanh điệu)
  2. Từ chức năng tiếng Việt không dấu (cua, va, cho, tim, can...)

Tránh phụ thuộc langdetect/langid vì chúng nặng và hay đoán sai với văn bản ngắn
kiểu tiêu đề RFQ.
"""

import re
import unicodedata

# Ký tự chỉ xuất hiện trong tiếng Việt (sau khi loại bỏ các ký tự Latin cơ bản)
_VN_CHARS = set("ăâđêôơưĂÂĐÊÔƠƯáàảãạấầẩẫậắằẳẵặéèẻẽẹếềểễệíìỉĩị"
                "óòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ")

# Từ chức năng tiếng Việt hay gặp (viết không dấu để bắt cả văn bản mất dấu)
_VN_STOPWORDS = {
    "cua", "va", "cho", "voi", "cac", "mot", "duoc", "nay", "den", "ben",
    "tim", "can", "muon", "dang", "cong", "ty", "hang", "gia", "san", "pham",
    "nha", "cung", "cap", "khach", "mua", "ban", "so", "luong", "chat", "luong",
}

# Từ chức năng tiếng Anh — dùng để tăng độ tin cậy khi kết luận "không phải tiếng Việt"
_EN_STOPWORDS = {
    "the", "and", "for", "with", "from", "please", "quote", "buyer", "product",
    "quantity", "supplier", "looking", "would", "like", "receive", "following",
    "requirement", "specification", "price", "delivery", "payment", "shipment",
}


def _strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def detect_language(text: str) -> str:
    """
    Trả về 'vi' nếu văn bản là tiếng Việt, 'en' nếu không phải.

    Văn bản rỗng coi như 'vi' để pipeline bỏ qua, không tốn công dịch.
    """
    if not text or not text.strip():
        return "vi"

    # Tín hiệu 1: ký tự có dấu tiếng Việt
    accent_count = sum(1 for ch in text if ch in _VN_CHARS)
    if accent_count >= 3 or (accent_count / max(len(text), 1)) > 0.02:
        return "vi"

    # Tín hiệu 2: từ chức năng (áp dụng cho văn bản tiếng Việt mất dấu)
    words = set(re.findall(r"[a-z]+", _strip_accents(text).lower()))
    vn_hits = len(words & _VN_STOPWORDS)
    en_hits = len(words & _EN_STOPWORDS)

    if vn_hits >= 3 and vn_hits > en_hits:
        return "vi"
    return "en"


def is_vietnamese(text: str) -> bool:
    """Kiểm tra nhanh văn bản có phải tiếng Việt không."""
    return detect_language(text) == "vi"
