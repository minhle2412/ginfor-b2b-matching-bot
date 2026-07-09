# -*- coding: utf-8 -*-
"""
Message Templates — Soạn thảo tin nhắn Outreach cho Ginfor.
=============================================================
Template engine cho 3 kênh: Facebook Comment, SMS, Gmail.
Văn phong chuyên nghiệp, chuẩn mực doanh nghiệp B2B.

Thương hiệu: Ginfor
Website: thongtincty.com
Email liên hệ: lenhatminh24122004@gmail.com
"""

import re
from typing import Optional
from .models import GmailMessage

# ===================== CẤU HÌNH =====================
BRAND_NAME = "Ginfor"
WEBSITE = "thongtincty.com"
CONTACT_EMAIL = "lenhatminh24122004@gmail.com"
SIGNATURE = f"{BRAND_NAME} — Kết nối doanh nghiệp Việt"


# ===================== TÓM TẮT NHU CẦU =====================

# Các pattern nhận diện nhu cầu mua/tìm kiếm trong tiếng Việt (Thứ tự ưu tiên từ cụ thể đến chung)
_NEED_PATTERNS = [
    # "tìm nguồn/nhà cung cấp/xưởng [X]"
    re.compile(
        r"(?:tìm|kiếm)\s+(?:nguồn|nhà cung cấp|ncc|xưởng|đối tác|supplier)\s+(?:cung cấp\s+)?(.{5,80}?)(?:\.|,|;|\n|$)",
        re.IGNORECASE | re.UNICODE,
    ),
    # "cần tìm/mua/nhập [X]"
    re.compile(
        r"(?:cần|muốn|đang)\s+(?:tìm|mua|nhập|kiếm|tuyển|thuê|đặt|order)\s+(?:đối tác\s+)?(?:cung cấp\s+)?(.{5,80}?)(?:\.|,|;|\n|$)",
        re.IGNORECASE | re.UNICODE,
    ),
    # "ai bán/cung cấp [X]"
    re.compile(
        r"(?:ai|bạn nào|shop nào|cty nào|dn nào)\s+(?:bán|cung cấp|sản xuất|gia công|phân phối)\s+(.{5,80}?)(?:\?|\.|,|\n|$)",
        re.IGNORECASE | re.UNICODE,
    ),
    # "cần [X] số lượng"
    re.compile(
        r"cần\s+(.{5,60}?)\s+(?:số lượng|sll|sl|lớn|nhiều)",
        re.IGNORECASE | re.UNICODE,
    ),
    # "mình đang tìm [X]"
    re.compile(
        r"(?:mình|em|tôi|công ty)\s+(?:đang|cần)\s+(?:tìm|kiếm)\s+(.{5,80}?)(?:\.|,|;|\n|$)",
        re.IGNORECASE | re.UNICODE,
    ),
]


def summarize_buyer_need(post_text: str) -> str:
    """
    Trích xuất tóm tắt nhu cầu mua hàng từ bài viết.

    Sử dụng regex pattern matching (không dùng LLM).
    Nếu không nhận diện được pattern cụ thể, trả về 80 ký tự đầu.

    Args:
        post_text: Nội dung bài viết Facebook

    Returns:
        Chuỗi tóm tắt nhu cầu (ví dụ: "tìm nhà cung cấp bao bì nhựa")
    """
    if not post_text:
        return "sản phẩm/dịch vụ"

    cleaned = post_text.strip()

    for pattern in _NEED_PATTERNS:
        match = pattern.search(cleaned)
        if match:
            need = match.group(1).strip()
            
            # Dọn dẹp các từ phụ trợ ở đầu nhu cầu
            need = re.sub(
                r"^(?:đối tác\s+|nhà cung cấp\s+|ncc\s+|nguồn\s+|xưởng\s+|supplier\s+|cung cấp\s+|gia công\s+|sản xuất\s+|bán\s+|mua\s+|sỉ\s+|lẻ\s+)+",
                "",
                need,
                flags=re.IGNORECASE | re.UNICODE
            )
            
            # Dọn dẹp các từ thừa ở cuối nhu cầu (giữ lại ở/tại)
            need = re.sub(
                r"\s+(?:số lượng|sll|sl|lớn|nhiều|gấp|giá|cạnh tranh|uy tín|không|ko|ạ|nhỉ|nào|với).*$",
                "",
                need,
                flags=re.IGNORECASE
            )
            # Dọn dẹp: bỏ ký tự thừa ở cuối
            need = re.sub(r"[\s,;.!?]+$", "", need)
            if len(need) >= 5:
                return need

    # Fallback: lấy 80 ký tự đầu
    fallback = cleaned[:80].replace("\n", " ").strip()
    if len(cleaned) > 80:
        fallback += "..."
    return fallback


# ===================== FORMAT DOANH NGHIỆP =====================

def _safe_get(company: dict, key: str, default: str = "") -> str:
    """Lấy giá trị từ dict công ty, trả về default nếu None/rỗng."""
    val = company.get(key)
    if val is None or (isinstance(val, str) and not val.strip()):
        return default
    return str(val).strip()


def format_company_for_comment(match: dict, rank: int) -> str:
    """
    Format thông tin doanh nghiệp cho Facebook comment (compact).

    Ví dụ: "1. Công ty ABC — Bao bì nhựa — TP.HCM — SĐT: 0912345678"
    """
    comp = match["company"]
    parts = [f"{rank}. {_safe_get(comp, 'name', 'N/A')}"]

    industry = _safe_get(comp, "main_industry")
    if industry:
        parts.append(industry)

    city = _safe_get(comp, "city")
    if city:
        parts.append(city)

    phone = _safe_get(comp, "phone")
    email = _safe_get(comp, "email")
    if phone:
        parts.append(f"SĐT: {phone}")
    elif email:
        parts.append(f"Email: {email}")

    return " — ".join(parts)


def format_company_for_sms(match: dict, rank: int) -> str:
    """
    Format thông tin doanh nghiệp cho SMS (rất compact, không dấu).

    Ví dụ: "1.Cong ty ABC-0912345678"
    """
    comp = match["company"]
    name = _safe_get(comp, "name", "N/A")
    # Bỏ dấu tiếng Việt cho SMS
    name_no_accent = _remove_accents(name)

    phone = _safe_get(comp, "phone")
    email = _safe_get(comp, "email")
    contact = phone or email or "N/A"

    return f"{rank}.{name_no_accent}-{contact}"


def format_company_for_email(match: dict, rank: int) -> str:
    """
    Format thông tin doanh nghiệp cho Gmail (chi tiết đầy đủ).

    Ví dụ:
        1. Công ty TNHH ABC
           Ngành nghề: Bao bì nhựa
           Địa chỉ: 123 Nguyễn Văn A, Q.1, TP.HCM
           Email: info@abc.com | SĐT: 0912345678
           MST: 0123456789
    """
    comp = match["company"]
    lines = [f"{rank}. {_safe_get(comp, 'name', 'N/A')}"]

    industry = _safe_get(comp, "main_industry")
    if industry:
        lines.append(f"   Ngành nghề: {industry}")

    address = _safe_get(comp, "address")
    city = _safe_get(comp, "city")
    if address or city:
        addr_parts = [p for p in [address, city] if p]
        lines.append(f"   Địa chỉ: {', '.join(addr_parts)}")

    contact_parts = []
    email = _safe_get(comp, "email")
    phone = _safe_get(comp, "phone")
    if email:
        contact_parts.append(f"Email: {email}")
    if phone:
        contact_parts.append(f"SĐT: {phone}")
    if contact_parts:
        lines.append(f"   {' | '.join(contact_parts)}")

    mst = _safe_get(comp, "mst")
    if mst:
        lines.append(f"   MST: {mst}")

    return "\n".join(lines)


# ===================== COMPOSE MESSAGES =====================

def compose_facebook_comment(buyer_need_summary: str, matches: list) -> str:
    """
    Soạn nội dung Facebook comment — kênh mặc định.

    Bao gồm: Lời chào + danh sách top 5 DN + gợi ý truy cập website.
    Văn phong chuyên nghiệp, lịch sự theo chuẩn B2B.

    Args:
        buyer_need_summary: Tóm tắt nhu cầu buyer
        matches: Danh sách kết quả matching (top 5)

    Returns:
        Nội dung comment hoàn chỉnh
    """
    company_lines = []
    for i, m in enumerate(matches[:5], start=1):
        company_lines.append(format_company_for_comment(m, i))

    companies_block = "\n".join(company_lines)

    comment = (
        f"Chào Anh/Chị,\n"
        f"\n"
        f"{BRAND_NAME} nhận thấy nhu cầu {buyer_need_summary} của Anh/Chị. "
        f"Chúng tôi xin gửi đến danh sách các doanh nghiệp uy tín phù hợp với nhu cầu này:\n"
        f"\n"
        f"{companies_block}\n"
        f"\n"
        f"Để tìm kiếm thêm nhiều đối tác và cơ hội hợp tác khác, "
        f"Anh/Chị có thể truy cập: {WEBSITE}\n"
        f"\n"
        f"Trân trọng,\n"
        f"{SIGNATURE}\n"
        f"🌐 {WEBSITE}"
    )

    return comment


def compose_sms(buyer_need_summary: str, matches: list) -> str:
    """
    Soạn nội dung SMS — ngắn gọn, không dấu tiếng Việt.

    Bao gồm: Header + top 5 DN (tên + SĐT) + link website.

    Args:
        buyer_need_summary: Tóm tắt nhu cầu buyer
        matches: Danh sách kết quả matching (top 5)

    Returns:
        Nội dung SMS hoàn chỉnh (không dấu)
    """
    summary_no_accent = _remove_accents(buyer_need_summary)

    company_lines = []
    for i, m in enumerate(matches[:5], start=1):
        company_lines.append(format_company_for_sms(m, i))

    companies_block = "\n".join(company_lines)

    sms = (
        f"[{BRAND_NAME}] Gui Anh/Chi DS doi tac phu hop nhu cau {summary_no_accent}:\n"
        f"{companies_block}\n"
        f"Tim them tai {WEBSITE}\n"
        f"LH: {CONTACT_EMAIL}"
    )

    return sms


def compose_gmail(
    buyer_need_summary: str,
    matches: list,
    recipient_email: str,
) -> GmailMessage:
    """
    Soạn email Gmail — chuyên nghiệp nhất, đính kèm bảng chi tiết.

    Bao gồm:
    - Lời kính chào từ Ginfor
    - Tóm tắt nhu cầu phát hiện từ bài đăng
    - Bảng danh sách Top 5 DN (tên, ngành, địa chỉ, liên hệ, MST)
    - Gợi ý truy cập thongtincty.com
    - Chữ ký chuyên nghiệp

    Args:
        buyer_need_summary: Tóm tắt nhu cầu buyer
        matches: Danh sách kết quả matching (top 5)
        recipient_email: Địa chỉ email người nhận

    Returns:
        GmailMessage với subject, body_text, body_html
    """
    subject = (
        f"[{BRAND_NAME}] Đề xuất danh sách đối tác cung cấp "
        f"{buyer_need_summary} phù hợp nhu cầu của Quý khách"
    )

    # ---- Plain text body ----
    company_text_lines = []
    for i, m in enumerate(matches[:5], start=1):
        company_text_lines.append(format_company_for_email(m, i))

    companies_text_block = "\n\n".join(company_text_lines)

    body_text = (
        f"Kính gửi Quý Anh/Chị,\n"
        f"\n"
        f"{BRAND_NAME} xin trân trọng kính chào.\n"
        f"\n"
        f"Qua quá trình tìm kiếm và phân tích nhu cầu, chúng tôi nhận thấy Quý Anh/Chị "
        f"đang có nhu cầu: {buyer_need_summary}.\n"
        f"\n"
        f"Dưới đây là danh sách Top 5 doanh nghiệp uy tín phù hợp nhất với nhu cầu của "
        f"Quý Anh/Chị, được sắp xếp theo mức độ phù hợp giảm dần:\n"
        f"\n"
        f"{'=' * 60}\n"
        f"{companies_text_block}\n"
        f"{'=' * 60}\n"
        f"\n"
        f"Ngoài danh sách trên, Quý Anh/Chị có thể truy cập {WEBSITE} để chủ động "
        f"tìm kiếm thêm nhiều đối tác và cơ hội hợp tác khác trong cơ sở dữ liệu "
        f"hơn 9.600 doanh nghiệp của {BRAND_NAME}.\n"
        f"\n"
        f"Nếu cần hỗ trợ thêm, Quý Anh/Chị vui lòng phản hồi email này hoặc liên hệ:\n"
        f"📧 {CONTACT_EMAIL}\n"
        f"🌐 {WEBSITE}\n"
        f"\n"
        f"Trân trọng,\n"
        f"{SIGNATURE}\n"
        f"🌐 {WEBSITE}\n"
    )

    # ---- HTML body ----
    company_html_rows = []
    for i, m in enumerate(matches[:5], start=1):
        comp = m["company"]
        score_pct = int(m.get("total_score", 0) * 100)
        company_html_rows.append(
            f"<tr>"
            f"<td style='padding:8px;border:1px solid #ddd;text-align:center;'>{i}</td>"
            f"<td style='padding:8px;border:1px solid #ddd;font-weight:bold;'>{_safe_get(comp, 'name', 'N/A')}</td>"
            f"<td style='padding:8px;border:1px solid #ddd;'>{_safe_get(comp, 'main_industry', 'N/A')}</td>"
            f"<td style='padding:8px;border:1px solid #ddd;'>{_safe_get(comp, 'city', 'N/A')}</td>"
            f"<td style='padding:8px;border:1px solid #ddd;'>{_safe_get(comp, 'phone', 'N/A')}</td>"
            f"<td style='padding:8px;border:1px solid #ddd;'>{_safe_get(comp, 'email', 'N/A')}</td>"
            f"<td style='padding:8px;border:1px solid #ddd;'>{_safe_get(comp, 'mst', 'N/A')}</td>"
            f"<td style='padding:8px;border:1px solid #ddd;text-align:center;'>{score_pct}%</td>"
            f"</tr>"
        )

    table_rows = "\n".join(company_html_rows)

    body_html = f"""<!DOCTYPE html>
<html lang="vi">
<head><meta charset="UTF-8"></head>
<body style="font-family:'Segoe UI',Arial,sans-serif;color:#333;line-height:1.6;max-width:800px;margin:0 auto;">

<p>Kính gửi Quý Anh/Chị,</p>

<p><strong>{BRAND_NAME}</strong> xin trân trọng kính chào.</p>

<p>Qua quá trình tìm kiếm và phân tích nhu cầu, chúng tôi nhận thấy Quý Anh/Chị 
đang có nhu cầu: <strong>{buyer_need_summary}</strong>.</p>

<p>Dưới đây là danh sách <strong>Top 5 doanh nghiệp uy tín</strong> phù hợp nhất với 
nhu cầu của Quý Anh/Chị, được sắp xếp theo mức độ phù hợp giảm dần:</p>

<table style="width:100%;border-collapse:collapse;margin:20px 0;font-size:14px;">
<thead>
<tr style="background-color:#2c5f8a;color:white;">
    <th style="padding:10px;border:1px solid #ddd;">#</th>
    <th style="padding:10px;border:1px solid #ddd;">Tên doanh nghiệp</th>
    <th style="padding:10px;border:1px solid #ddd;">Ngành nghề</th>
    <th style="padding:10px;border:1px solid #ddd;">Khu vực</th>
    <th style="padding:10px;border:1px solid #ddd;">SĐT</th>
    <th style="padding:10px;border:1px solid #ddd;">Email</th>
    <th style="padding:10px;border:1px solid #ddd;">MST</th>
    <th style="padding:10px;border:1px solid #ddd;">Phù hợp</th>
</tr>
</thead>
<tbody>
{table_rows}
</tbody>
</table>

<p>Ngoài danh sách trên, Quý Anh/Chị có thể truy cập 
<a href="https://{WEBSITE}" style="color:#2c5f8a;font-weight:bold;">{WEBSITE}</a> 
để chủ động tìm kiếm thêm nhiều đối tác và cơ hội hợp tác khác trong cơ sở dữ liệu 
hơn <strong>9.600 doanh nghiệp</strong> của {BRAND_NAME}.</p>

<p>Nếu cần hỗ trợ thêm, Quý Anh/Chị vui lòng phản hồi email này hoặc liên hệ:</p>
<ul>
    <li>📧 Email: <a href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a></li>
    <li>🌐 Website: <a href="https://{WEBSITE}">{WEBSITE}</a></li>
</ul>

<hr style="border:none;border-top:2px solid #2c5f8a;margin:30px 0 15px 0;">
<p style="font-size:13px;color:#666;">
    Trân trọng,<br>
    <strong>{SIGNATURE}</strong><br>
    🌐 <a href="https://{WEBSITE}">{WEBSITE}</a>
</p>

<p style="font-size:11px;color:#999;margin-top:20px;">
    <em>Email này được gửi từ hệ thống {BRAND_NAME}. Nếu Quý Anh/Chị không có nhu cầu, 
    vui lòng bỏ qua email này. Chúng tôi xin lỗi vì sự bất tiện.</em>
</p>

</body>
</html>"""

    return GmailMessage(
        subject=subject,
        body_html=body_html,
        body_text=body_text,
        to_email=recipient_email,
        from_email=CONTACT_EMAIL,
    )


# ===================== TIỆN ÍCH =====================

# Bảng chuyển đổi dấu tiếng Việt → không dấu
_ACCENT_MAP = str.maketrans(
    "àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ"
    "ÀÁẠẢÃÂẦẤẬẨẪĂẰẮẶẲẴÈÉẸẺẼÊỀẾỆỂỄÌÍỊỈĨÒÓỌỎÕÔỒỐỘỔỖƠỜỚỢỞỠÙÚỤỦŨƯỪỨỰỬỮỲÝỴỶỸĐ",
    "aaaaaaaaaaaaaaaaaeeeeeeeeeeeiiiiiooooooooooooooooouuuuuuuuuuuyyyyyd"
    "AAAAAAAAAAAAAAAAAEEEEEEEEEEEIIIIIOOOOOOOOOOOOOOOOOUUUUUUUUUUUYYYYYD",
)


def _remove_accents(text: str) -> str:
    """Loại bỏ dấu tiếng Việt (dùng cho SMS)."""
    return text.translate(_ACCENT_MAP)
