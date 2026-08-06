# -*- coding: utf-8 -*-
"""
Translation Layer — Dịch bài đăng buyer sang tiếng Việt trước khi matching.
============================================================================
Lý do tồn tại: Matching Engine dùng `keepitreal/vietnamese-sbert` — model đơn ngữ
tiếng Việt. Bài đăng buyer trên các trang B2B e-commerce (Go4WorldBusiness, EC21,
GlobalSources, TradeWheel) viết bằng tiếng Anh, còn mô tả doanh nghiệp trong
Supabase là tiếng Việt. Hai đầu khác ngôn ngữ nên điểm ngữ nghĩa gần như vô nghĩa
("Rice Buyers" từng khớp cao nhất với một công ty mã vạch).

Dịch bài đăng sang tiếng Việt trước khi đưa vào matching sẽ đưa cả hai đầu về
cùng không gian ngữ nghĩa.

Cách dùng:

    from translation import get_translator
    tr = get_translator()
    vi = tr.translate("Buyer is looking for long grain white rice, 5% broken")
    # → "Người mua đang tìm gạo trắng hạt dài, tấm 5%"

Bài đã là tiếng Việt sẽ được trả về nguyên vẹn, không dịch lại.
"""

from .detect import detect_language, is_vietnamese
from .glossary import B2B_GLOSSARY, augment_with_glossary, glossary_translate
from .service import Translator, get_translator

__all__ = [
    "detect_language",
    "is_vietnamese",
    "B2B_GLOSSARY",
    "augment_with_glossary",
    "glossary_translate",
    "Translator",
    "get_translator",
]
