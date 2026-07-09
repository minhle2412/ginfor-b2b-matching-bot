# -*- coding: utf-8 -*-
"""
Sender Stubs — Mô phỏng gửi tin nhắn Outreach.
==================================================
Stub implementations cho 3 kênh gửi.
Trong giai đoạn prototype, các sender chỉ ghi log nội dung.
Sẵn sàng thay thế bằng API thực (Gmail OAuth2, Twilio, Graph API).
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from .models import OutreachAction, OutreachChannel, GmailMessage

logger = logging.getLogger(__name__)


@dataclass
class SendResult:
    """Kết quả gửi tin nhắn outreach."""
    success: bool
    channel: OutreachChannel
    message: str               # Trạng thái (hiển thị cho admin)
    error: Optional[str] = None


class BaseSender(ABC):
    """Lớp cơ sở cho tất cả sender."""

    @abstractmethod
    async def send(self, action: OutreachAction) -> SendResult:
        """
        Gửi tin nhắn outreach.

        Args:
            action: OutreachAction đã được duyệt

        Returns:
            SendResult chứa trạng thái gửi
        """
        pass


class GmailSender(BaseSender):
    """
    Stub: Log nội dung email.

    Sẵn sàng tích hợp Gmail API OAuth2.
    Để kích hoạt gửi thật, thay thế method send() bằng logic
    sử dụng google-auth + google-api-python-client.
    """

    async def send(self, action: OutreachAction) -> SendResult:
        if not action.gmail_message:
            return SendResult(
                success=False,
                channel=OutreachChannel.GMAIL,
                message="Thiếu nội dung email",
                error="OutreachAction không có gmail_message",
            )

        msg = action.gmail_message

        logger.info(f"📧 [GMAIL STUB] ═══════════════════════════════")
        logger.info(f"   Từ: {msg.from_email}")
        logger.info(f"   Đến: {msg.to_email}")
        logger.info(f"   Tiêu đề: {msg.subject}")
        logger.info(f"   Nội dung (text):")
        for line in msg.body_text.split("\n")[:15]:
            logger.info(f"   │ {line}")
        if msg.body_text.count("\n") > 15:
            logger.info(f"   │ ... (còn tiếp)")
        logger.info(f"   ═══════════════════════════════════════════")

        return SendResult(
            success=True,
            channel=OutreachChannel.GMAIL,
            message=f"Email đã gửi (stub) tới {msg.to_email}",
        )


class SMSSender(BaseSender):
    """
    Stub: Log nội dung SMS.

    Sẵn sàng tích hợp Twilio hoặc Vonage.
    Để kích hoạt gửi thật, thay thế method send() bằng logic
    sử dụng twilio.rest.Client.
    """

    async def send(self, action: OutreachAction) -> SendResult:
        if not action.message_content:
            return SendResult(
                success=False,
                channel=OutreachChannel.SMS,
                message="Thiếu nội dung SMS",
                error="OutreachAction không có message_content",
            )

        char_count = len(action.message_content)

        logger.info(f"📱 [SMS STUB] ═══════════════════════════════")
        logger.info(f"   Đến: {action.recipient}")
        logger.info(f"   Độ dài: {char_count} ký tự")
        logger.info(f"   Nội dung:")
        for line in action.message_content.split("\n"):
            logger.info(f"   │ {line}")
        logger.info(f"   ═══════════════════════════════════════════")

        return SendResult(
            success=True,
            channel=OutreachChannel.SMS,
            message=f"SMS đã gửi (stub) tới {action.recipient} ({char_count} chars)",
        )


class FacebookCommentSender(BaseSender):
    """
    Stub: Log nội dung comment Facebook.

    Sẵn sàng tích hợp Facebook Graph API.
    Cần: Page Access Token + quyền publish_to_groups.
    """

    async def send(self, action: OutreachAction) -> SendResult:
        content = action.fb_comment_content or action.message_content

        if not content:
            return SendResult(
                success=False,
                channel=OutreachChannel.FACEBOOK_COMMENT,
                message="Thiếu nội dung comment",
                error="OutreachAction không có nội dung FB comment",
            )

        logger.info(f"💬 [FB COMMENT STUB] ═══════════════════════════")
        logger.info(f"   URL bài viết: {action.post_url}")
        logger.info(f"   Nội dung comment:")
        for line in content.split("\n")[:20]:
            logger.info(f"   │ {line}")
        if content.count("\n") > 20:
            logger.info(f"   │ ... (còn tiếp)")
        logger.info(f"   ═══════════════════════════════════════════")

        return SendResult(
            success=True,
            channel=OutreachChannel.FACEBOOK_COMMENT,
            message=f"Comment đã đăng (stub) tại {action.post_url}",
        )


def get_sender(channel: OutreachChannel) -> BaseSender:
    """
    Factory: Trả về sender tương ứng với kênh.

    Args:
        channel: OutreachChannel (SMS, GMAIL, FACEBOOK_COMMENT)

    Returns:
        BaseSender instance tương ứng
    """
    senders = {
        OutreachChannel.GMAIL: GmailSender(),
        OutreachChannel.SMS: SMSSender(),
        OutreachChannel.FACEBOOK_COMMENT: FacebookCommentSender(),
    }
    return senders[channel]
