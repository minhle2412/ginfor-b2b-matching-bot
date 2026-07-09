# -*- coding: utf-8 -*-
import unittest
import sys
import os

# Thêm thư mục cha vào sys.path để import được package outreach
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from outreach.models import OutreachChannel, OutreachAction
from outreach.outreach_engine import OutreachEngine


class TestOutreachEngine(unittest.TestCase):
    def setUp(self):
        self.engine = OutreachEngine()
        self.mock_matches = [
            {
                "company": {
                    "name": "Công ty TNHH Nhựa ABC",
                    "mst": "0102030405",
                    "email": "contact@nhuaabc.com",
                    "phone": "0901234567",
                    "main_industry": "Sản xuất bao bì nhựa",
                    "address": "Số 1 Đường số 2, P. Thảo Điền, Quận 2",
                    "city": "TP. Hồ Chí Minh"
                },
                "total_score": 0.95
            }
        ]

    def test_determine_channel_phone(self):
        # Có SĐT ưu tiên hàng đầu -> SMS
        post = {
            "post_id": "123",
            "text": "Cần tìm nguồn sỉ bao bì nhựa. LH SĐT 0901234567, email: test@buyer.com",
            "url": "https://facebook.com/groups/123/posts/456"
        }
        action = self.engine.process_match_result(post, self.mock_matches)
        self.assertEqual(action.channel, OutreachChannel.SMS)
        self.assertEqual(action.recipient, "0901234567")
        self.assertIn("0901234567", action.message_content)

    def test_determine_channel_email(self):
        # Không có SĐT, có email -> Gmail
        post = {
            "post_id": "124",
            "text": "Cần tìm đối tác bao bì nhựa. Email: test@buyer.com",
            "url": "https://facebook.com/groups/123/posts/457"
        }
        action = self.engine.process_match_result(post, self.mock_matches)
        self.assertEqual(action.channel, OutreachChannel.GMAIL)
        self.assertEqual(action.recipient, "test@buyer.com")
        self.assertIsNotNone(action.gmail_message)
        self.assertEqual(action.gmail_message.to_email, "test@buyer.com")

    def test_determine_channel_default(self):
        # Không có SĐT hay email -> Facebook Comment
        post = {
            "post_id": "125",
            "text": "Cần tìm xưởng bao bì nhựa gấp tại HCM",
            "url": "https://facebook.com/groups/123/posts/458"
        }
        action = self.engine.process_match_result(post, self.mock_matches)
        self.assertEqual(action.channel, OutreachChannel.FACEBOOK_COMMENT)
        self.assertEqual(action.recipient, post["url"])

    def test_stats_and_actions_review(self):
        post = {
            "post_id": "126",
            "text": "Cần xưởng cơ khí, LH: 0912345678",
            "url": "https://facebook.com/groups/123/posts/459"
        }
        action = self.engine.process_match_result(post, self.mock_matches)
        self.assertEqual(action.status, "pending_review")
        self.assertEqual(self.engine.get_pending_count(), 1)
        
        # Approve
        success = self.engine.mark_approved(action.post_id)
        self.assertTrue(success)
        self.assertEqual(action.status, "approved")
        self.assertEqual(self.engine.get_pending_count(), 0)
        self.assertEqual(self.engine.get_stats()["approved"], 1)


if __name__ == "__main__":
    unittest.main()
