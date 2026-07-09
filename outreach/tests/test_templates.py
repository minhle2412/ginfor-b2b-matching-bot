# -*- coding: utf-8 -*-
import unittest
import sys
import os

# Thêm thư mục cha vào sys.path để import được package outreach
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from outreach.templates import (
    summarize_buyer_need,
    format_company_for_comment,
    format_company_for_sms,
    format_company_for_email,
    compose_facebook_comment,
    compose_sms,
    compose_gmail,
    _remove_accents
)


class TestTemplates(unittest.TestCase):
    def setUp(self):
        # Thiết lập các mẫu dữ liệu matching giả lập
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
            },
            {
                "company": {
                    "name": "Hợp tác xã May mặc Đông Dương",
                    "mst": "0304050607",
                    "email": "info@dongduonggarment.vn",
                    "phone": "0987654321",
                    "main_industry": "Gia công quần áo đồng phục",
                    "address": "123 Lê Lợi, Quận Hải Châu",
                    "city": "Đà Nẵng"
                },
                "total_score": 0.88
            },
            {
                "company": {
                    "name": "Công ty Cổ phần Thép Việt Ý",
                    "mst": "0908070605",
                    "email": "sales@viety.com.vn",
                    "phone": "0243123456",
                    "main_industry": "Cung cấp thép xây dựng",
                    "address": "KCN Châu Sơn",
                    "city": "Hà Nam"
                },
                "total_score": 0.82
            },
            {
                "company": {
                    "name": "Xưởng cơ khí Hoàng Gia",
                    "mst": "",
                    "email": "",
                    "phone": "0911223344",
                    "main_industry": "Gia công cơ khí chính xác",
                    "address": "Đường 3/2",
                    "city": "Bình Dương"
                },
                "total_score": 0.75
            },
            {
                "company": {
                    "name": "Công ty Logistics Toàn Cầu",
                    "mst": "1122334455",
                    "email": "logistic@global.com",
                    "phone": "",
                    "main_industry": "Dịch vụ vận tải kho bãi",
                    "address": "Cảng Cát Lái",
                    "city": "TP. Hồ Chí Minh"
                },
                "total_score": 0.69
            }
        ]

    def test_summarize_buyer_need(self):
        self.assertEqual(summarize_buyer_need("Cty cần mua bao bì nhựa PE số lượng lớn"), "bao bì nhựa PE")
        self.assertEqual(summarize_buyer_need("Mình đang tìm đối tác cung cấp thép xây dựng tại HCM"), "thép xây dựng tại HCM")
        self.assertEqual(summarize_buyer_need("Ai bán gạo xuất khẩu không ạ?"), "gạo xuất khẩu")
        self.assertEqual(summarize_buyer_need("Cần tìm nguồn sỉ quần áo nam nữ"), "quần áo nam nữ")
        # Fallback test
        self.assertEqual(summarize_buyer_need("Bài viết không chứa các từ khóa mua bán phổ biến"), "Bài viết không chứa các từ khóa mua bán phổ biến")

    def test_format_company_for_comment(self):
        formatted = format_company_for_comment(self.mock_matches[0], 1)
        self.assertEqual(formatted, "1. Công ty TNHH Nhựa ABC — Sản xuất bao bì nhựa — TP. Hồ Chí Minh — SĐT: 0901234567")

    def test_format_company_for_sms(self):
        formatted = format_company_for_sms(self.mock_matches[0], 1)
        # Tên không dấu, SĐT đi kèm
        self.assertEqual(formatted, "1.Cong ty TNHH Nhua ABC-0901234567")

    def test_format_company_for_email(self):
        formatted = format_company_for_email(self.mock_matches[0], 1)
        self.assertIn("1. Công ty TNHH Nhựa ABC", formatted)
        self.assertIn("Ngành nghề: Sản xuất bao bì nhựa", formatted)
        self.assertIn("Địa chỉ: Số 1 Đường số 2, P. Thảo Điền, Quận 2, TP. Hồ Chí Minh", formatted)
        self.assertIn("Email: contact@nhuaabc.com | SĐT: 0901234567", formatted)
        self.assertIn("MST: 0102030405", formatted)

    def test_compose_facebook_comment(self):
        comment = compose_facebook_comment("bao bì nhựa PE", self.mock_matches)
        self.assertIn("Ginfor nhận thấy nhu cầu bao bì nhựa PE của Anh/Chị", comment)
        self.assertIn("Công ty TNHH Nhựa ABC", comment)
        self.assertIn("Công ty Logistics Toàn Cầu", comment)
        self.assertIn("thongtincty.com", comment)

    def test_compose_sms(self):
        sms = compose_sms("bao bì nhựa PE", self.mock_matches)
        self.assertIn("[Ginfor] Gui Anh/Chi DS doi tac phu hop nhu cau bao bi nhua PE:", sms)
        self.assertIn("Cong ty TNHH Nhua ABC-0901234567", sms)
        self.assertIn("Cong ty Logistics Toan Cau-logistic@global.com", sms)
        self.assertIn("thongtincty.com", sms)

    def test_compose_gmail(self):
        gmail = compose_gmail("bao bì nhựa PE", self.mock_matches, "test@buyer.com")
        self.assertEqual(gmail.to_email, "test@buyer.com")
        self.assertIn("[Ginfor] Đề xuất danh sách đối tác cung cấp bao bì nhựa PE", gmail.subject)
        
        # Test text body
        self.assertIn("Kính gửi Quý Anh/Chị", gmail.body_text)
        self.assertIn("Công ty TNHH Nhựa ABC", gmail.body_text)
        
        # Test HTML body
        self.assertIn("<table", gmail.body_html)
        self.assertIn("Công ty TNHH Nhựa ABC", gmail.body_html)
        self.assertIn("contact@nhuaabc.com", gmail.body_html)
        self.assertIn("95%", gmail.body_html) # score_pct


if __name__ == "__main__":
    unittest.main()
