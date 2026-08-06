# -*- coding: utf-8 -*-
"""
Làm sạch bài đăng buyer trước khi dịch.
=========================================
Bài đăng trên các trang xúc tiến thương mại được sinh từ template, nên phần lớn
nội dung là câu khuôn mẫu lặp đi lặp lại không mang thông tin về nhu cầu:

    "WANTED : Rice Like Steam Basmati Rice"
    "Buyer is interested to receive quotations for the following RFQ - ..."
    "Please quote for the following wholesale product requirement - ..."

Bỏ những câu này mang lại ba lợi ích:
  1. Query đưa vào matching sạch hơn, điểm ngữ nghĩa phản ánh đúng nhu cầu thật
  2. Ít văn bản phải dịch hơn → nhanh hơn
  3. Model dịch không bị nhiễu bởi cụm không phải câu hoàn chỉnh
"""

import re

#: Các câu khuôn mẫu của trang web, xoá sạch trước khi dịch.
_BOILERPLATE_PATTERNS = [
    r"^\s*WANTED\s*:\s*",
    r"^\s*RFQ\s*:\s*",
    r"buyer is interested to receive quotations for the following rfq\s*[-–:]?",
    r"the buyer would like to receive quotations for\s*[-–:]?",
    r"buyer would like to receive quotations for\s*[-–:]?",
    r"please quote for the following wholesale product requirement\s*[-–:]?",
    r"we would like to receive quotations for\s*[-–:]?",
    r"requirement for\s+",
    r"i am interested in your product\s*[.,]?",
    r"please send me? (?:your )?(?:best )?(?:price|quotation|offer)s?\s*[.,]?",
    r"looking forward to (?:your reply|hearing from you)\s*[.,]?",
    r"thank you( very much)?\s*[.,]?$",
    r"best regards\s*[.,]?.*$",
]

_COMPILED = [re.compile(p, re.IGNORECASE | re.MULTILINE) for p in _BOILERPLATE_PATTERNS]

#: Nhãn trường trong template — giữ lại giá trị, bỏ nhãn tiếng Anh vô nghĩa
#: khi đã có nhãn tương đương ở query cuối.
_FIELD_LABELS = re.compile(
    r"\b(product name|specifications?|quantity required|packing|price term|"
    r"payment terms?|destination port|shipment terms?)\s*:\s*",
    re.IGNORECASE,
)


def clean_boilerplate(text: str, strip_labels: bool = False) -> str:
    """
    Xoá câu khuôn mẫu của trang B2B khỏi bài đăng.

    Args:
        text: nội dung gốc
        strip_labels: xoá luôn nhãn trường ("Product Name:", "Packing:"...).
                      Mặc định giữ lại vì nhãn giúp model dịch hiểu ngữ cảnh.

    Returns:
        Nội dung đã làm sạch. Nếu sau khi xoá không còn gì, trả về nguyên bản
        để không bao giờ làm mất toàn bộ thông tin.
    """
    if not text or not text.strip():
        return text or ""

    cleaned = text
    for pattern in _COMPILED:
        cleaned = pattern.sub(" ", cleaned)

    if strip_labels:
        cleaned = _FIELD_LABELS.sub(" ", cleaned)

    # Gom khoảng trắng, bỏ dấu câu thừa còn sót lại sau khi xoá
    cleaned = re.sub(r"\s*[-–]\s*(?=[-–]|$)", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -–:,;")

    return cleaned if cleaned.strip() else text.strip()
