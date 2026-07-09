# -*- coding: utf-8 -*-
"""
Data Models cho Ginfor Outreach Engine.
========================================
Định nghĩa các dataclass và enum dùng trong toàn bộ hệ thống outreach.
"""

from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from typing import Optional


class OutreachChannel(Enum):
    """Kênh gửi thông báo outreach."""
    SMS = "sms"
    GMAIL = "gmail"
    FACEBOOK_COMMENT = "facebook_comment"


@dataclass
class ContactInfo:
    """Thông tin liên hệ trích xuất từ bài viết Facebook."""
    phones: list[str] = field(default_factory=list)
    emails: list[str] = field(default_factory=list)

    @property
    def has_phone(self) -> bool:
        """Kiểm tra có số điện thoại hay không."""
        return len(self.phones) > 0

    @property
    def has_email(self) -> bool:
        """Kiểm tra có email hay không."""
        return len(self.emails) > 0

    @property
    def primary_phone(self) -> Optional[str]:
        """Trả về số điện thoại đầu tiên (ưu tiên cao nhất)."""
        return self.phones[0] if self.phones else None

    @property
    def primary_email(self) -> Optional[str]:
        """Trả về email đầu tiên (ưu tiên cao nhất)."""
        return self.emails[0] if self.emails else None


@dataclass
class GmailMessage:
    """Cấu trúc email Gmail đã soạn sẵn."""
    subject: str
    body_html: str
    body_text: str
    to_email: str
    from_email: str = "lenhatminh24122004@gmail.com"


@dataclass
class OutreachAction:
    """
    Hành động outreach đã soạn thảo, chờ duyệt trước khi gửi.

    Mỗi OutreachAction đại diện cho 1 lần tiếp cận buyer,
    bao gồm kênh gửi ưu tiên + nội dung Facebook comment mặc định.
    """
    post_id: str
    post_url: str
    post_text: str
    buyer_need_summary: str
    channel: OutreachChannel
    recipient: str                    # SĐT, email, hoặc URL bài viết
    message_content: str              # Nội dung tin nhắn đã soạn
    matches_used: list = field(default_factory=list)  # Top N match dicts
    status: str = "pending_review"    # pending_review | approved | sent | rejected
    created_at: datetime = field(default_factory=datetime.now)
    # Email chi tiết (chỉ khi channel=GMAIL)
    gmail_message: Optional[GmailMessage] = None
    # Luôn tạo Facebook comment làm kênh mặc định
    fb_comment_content: Optional[str] = None
