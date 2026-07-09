# -*- coding: utf-8 -*-
"""
Outreach Engine — Điều phối chính hệ thống Ginfor Outreach.
=============================================================
Nhận bài viết buyer + kết quả matching →
Trích xuất thông tin liên hệ →
Chọn kênh gửi (SMS > Gmail > Facebook Comment) →
Soạn tin nhắn chuyên nghiệp.
"""

import logging
from .models import ContactInfo, OutreachChannel, OutreachAction
from .contact_extractor import extract_contact_info
from .templates import (
    summarize_buyer_need,
    compose_facebook_comment,
    compose_sms,
    compose_gmail,
)

logger = logging.getLogger(__name__)


class OutreachEngine:
    """
    Điều phối chính của hệ thống outreach.

    Luồng xử lý:
    1. Nhận bài viết buyer + danh sách DN matching
    2. Trích xuất SĐT/email từ nội dung bài viết
    3. Chọn kênh ưu tiên: SĐT → SMS, Email → Gmail, Mặc định → FB Comment
    4. Soạn tin nhắn theo template chuyên nghiệp
    5. Trả về OutreachAction để admin duyệt trên Discord
    """

    def __init__(self):
        self.pending_actions: list[OutreachAction] = []
        self._stats = {
            "total_processed": 0,
            "sms_count": 0,
            "gmail_count": 0,
            "fb_comment_count": 0,
            "approved": 0,
            "rejected": 0,
        }

    def determine_channel(self, contact_info: ContactInfo) -> OutreachChannel:
        """
        Xác định kênh gửi ưu tiên dựa trên thông tin liên hệ.

        Thứ tự ưu tiên:
        1. Có SĐT → SMS
        2. Có email → Gmail
        3. Không có cả hai → Facebook Comment (mặc định)

        Args:
            contact_info: Thông tin liên hệ đã trích xuất

        Returns:
            OutreachChannel tương ứng
        """
        if contact_info.has_phone:
            return OutreachChannel.SMS
        elif contact_info.has_email:
            return OutreachChannel.GMAIL
        else:
            return OutreachChannel.FACEBOOK_COMMENT

    def process_match_result(self, post: dict, matches: list) -> OutreachAction:
        """
        Xử lý kết quả matching và tạo OutreachAction.

        Luồng:
        1. Trích xuất thông tin liên hệ từ bài viết
        2. Tóm tắt nhu cầu buyer
        3. Xác định kênh ưu tiên
        4. Lấy top 5 matches
        5. Soạn tin nhắn theo kênh ưu tiên
        6. Luôn soạn thêm Facebook comment (mặc định)
        7. Trả về OutreachAction sẵn sàng review

        Args:
            post: dict với keys 'post_id', 'text', 'url', 'group_id'
            matches: list of match dicts từ matching engine
                     mỗi item có 'company', 'score_breakdown', 'total_score'

        Returns:
            OutreachAction sẵn sàng để preview trên Discord
        """
        post_text = post.get("text", "")
        post_id = post.get("post_id", "unknown")
        post_url = post.get("url", "")

        # 1. Trích xuất thông tin liên hệ
        contact_info = extract_contact_info(post_text)

        # 2. Tóm tắt nhu cầu
        buyer_need_summary = summarize_buyer_need(post_text)

        # 3. Xác định kênh ưu tiên
        channel = self.determine_channel(contact_info)

        # 4. Lấy top 5 matches
        top_matches = matches[:5]

        # 5. Soạn tin nhắn theo kênh ưu tiên
        gmail_message = None  # Khởi tạo để tránh UnboundLocalError

        if channel == OutreachChannel.SMS:
            message_content = compose_sms(buyer_need_summary, top_matches)
            recipient = contact_info.primary_phone
        elif channel == OutreachChannel.GMAIL:
            gmail_message = compose_gmail(
                buyer_need_summary, top_matches, contact_info.primary_email
            )
            message_content = gmail_message.body_text
            recipient = contact_info.primary_email
        else:
            message_content = compose_facebook_comment(
                buyer_need_summary, top_matches
            )
            recipient = post_url

        # 6. Luôn soạn Facebook comment mặc định
        fb_comment = compose_facebook_comment(buyer_need_summary, top_matches)

        # 7. Tạo OutreachAction
        action = OutreachAction(
            post_id=post_id,
            post_url=post_url,
            post_text=post_text,
            buyer_need_summary=buyer_need_summary,
            channel=channel,
            recipient=recipient,
            message_content=message_content,
            matches_used=top_matches,
            fb_comment_content=fb_comment,
            gmail_message=gmail_message,
        )

        # Cập nhật thống kê
        self.pending_actions.append(action)
        self._stats["total_processed"] += 1
        if channel == OutreachChannel.SMS:
            self._stats["sms_count"] += 1
        elif channel == OutreachChannel.GMAIL:
            self._stats["gmail_count"] += 1
        else:
            self._stats["fb_comment_count"] += 1

        logger.info(
            f"📨 Outreach: post [{post_id}] → kênh={channel.value}, "
            f"recipient={recipient}, {len(top_matches)} DN"
        )

        return action

    def get_stats(self) -> dict:
        """Trả về thống kê outreach hiện tại."""
        return self._stats.copy()

    def get_pending_count(self) -> int:
        """Số lượng action đang chờ duyệt."""
        return sum(1 for a in self.pending_actions if a.status == "pending_review")

    def mark_approved(self, post_id: str) -> bool:
        """
        Đánh dấu action là đã duyệt.

        Args:
            post_id: ID bài viết Facebook

        Returns:
            True nếu tìm thấy và cập nhật thành công
        """
        for action in self.pending_actions:
            if action.post_id == post_id and action.status == "pending_review":
                action.status = "approved"
                self._stats["approved"] += 1
                logger.info(f"✅ Outreach approved: post [{post_id}]")
                return True
        return False

    def mark_rejected(self, post_id: str) -> bool:
        """
        Đánh dấu action là bị từ chối.

        Args:
            post_id: ID bài viết Facebook

        Returns:
            True nếu tìm thấy và cập nhật thành công
        """
        for action in self.pending_actions:
            if action.post_id == post_id and action.status == "pending_review":
                action.status = "rejected"
                self._stats["rejected"] += 1
                logger.info(f"❌ Outreach rejected: post [{post_id}]")
                return True
        return False
