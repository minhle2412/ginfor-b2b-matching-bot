# -*- coding: utf-8 -*-
"""
Outreach Package — Ginfor B2B Outreach Engine
===============================================
Hệ thống tự động soạn thảo và gửi thông báo đối tác phù hợp
tới bên có nhu cầu (buyer) qua Gmail, SMS, hoặc Facebook Comment.

Thương hiệu: Ginfor
Website: thongtincty.com
"""

from .models import ContactInfo, OutreachChannel, OutreachAction, GmailMessage
from .contact_extractor import extract_contact_info
from .outreach_engine import OutreachEngine

__all__ = [
    "ContactInfo",
    "OutreachChannel",
    "OutreachAction",
    "GmailMessage",
    "extract_contact_info",
    "OutreachEngine",
]
