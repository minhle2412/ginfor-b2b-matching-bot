# -*- coding: utf-8 -*-
import unittest
import sys
import os

# Thêm thư mục cha vào sys.path để import được package outreach
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from outreach.contact_extractor import extract_phone_numbers, extract_emails, extract_contact_info


class TestPhoneExtraction(unittest.TestCase):
    def test_basic_mobile(self):
        self.assertIn("0912345678", extract_phone_numbers("Liên hệ 0912345678"))

    def test_dotted_format(self):
        self.assertIn("0912345678", extract_phone_numbers("SĐT: 0912.345.678"))

    def test_dashed_format(self):
        self.assertIn("0912345678", extract_phone_numbers("Gọi 0912-345-678"))

    def test_spaced_format(self):
        self.assertIn("0912345678", extract_phone_numbers("Tel: 0912 345 678"))

    def test_plus84_prefix(self):
        self.assertIn("0912345678", extract_phone_numbers("+84912345678"))

    def test_multiple_phones(self):
        text = "LH: 0912345678 hoặc 0987654321"
        phones = extract_phone_numbers(text)
        self.assertEqual(len(phones), 2)
        self.assertIn("0912345678", phones)
        self.assertIn("0987654321", phones)

    def test_no_phone(self):
        self.assertEqual([], extract_phone_numbers("Cần mua 100 tấn thép"))

    def test_various_prefixes(self):
        for prefix in ["032", "056", "070", "081", "098"]:
            phone = prefix + "1234567"
            result = extract_phone_numbers(f"Gọi {phone}")
            self.assertTrue(len(result) > 0, f"Failed for prefix {prefix}")


class TestEmailExtraction(unittest.TestCase):
    def test_basic_email(self):
        self.assertIn("test@example.com", extract_emails("Email: test@example.com"))

    def test_company_email(self):
        self.assertIn("mua@company.com.vn", extract_emails("Gửi báo giá: mua@company.com.vn"))

    def test_no_email(self):
        self.assertEqual([], extract_emails("Cần mua 100 tấn thép tại HCM"))


class TestContactInfo(unittest.TestCase):
    def test_both_phone_and_email(self):
        text = "LH: 0912345678, email: buyer@company.com"
        info = extract_contact_info(text)
        self.assertTrue(info.has_phone)
        self.assertTrue(info.has_email)
        self.assertEqual(info.primary_phone, "0912345678")
        self.assertEqual(info.primary_email, "buyer@company.com")

    def test_phone_only(self):
        info = extract_contact_info("LH: 0912345678")
        self.assertTrue(info.has_phone)
        self.assertFalse(info.has_email)

    def test_no_contact(self):
        info = extract_contact_info("Cần mua gạo xuất khẩu")
        self.assertFalse(info.has_phone)
        self.assertFalse(info.has_email)


if __name__ == "__main__":
    unittest.main()
