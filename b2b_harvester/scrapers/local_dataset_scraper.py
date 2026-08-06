"""
Local Business Dataset Importer for Vietnamese Suppliers
Imports real Vietnamese export & manufacturing companies from Business_dataset.csv
into b2b_harvester database (both suppliers_vietnam and supplier_posts tables).
"""

import os
import csv
import logging
from pathlib import Path
from .base_scraper import BaseScraper
from config import MAX_PAGES_PER_KEYWORD

logger = logging.getLogger("b2b_harvester.scrapers.local_dataset")

class LocalBusinessDatasetImporter(BaseScraper):
    def __init__(self):
        super().__init__("thongtincty_local_db")
        # Locate Business_dataset.csv in parent directory
        self.csv_path = Path(__file__).resolve().parent.parent.parent / "Business_dataset.csv"

    def scrape_buyers(self, keywords=None, max_pages=MAX_PAGES_PER_KEYWORD):
        """Local dataset contains suppliers only."""
        return []

    def scrape_suppliers_vietnam(self, keywords=None, max_pages=MAX_PAGES_PER_KEYWORD):
        results = []
        if not os.path.exists(self.csv_path):
            logger.warning(f"[{self.name}] Business_dataset.csv not found at {self.csv_path}")
            return results

        logger.info(f"[{self.name}] Importing Vietnamese Suppliers from {self.csv_path}...")

        try:
            with open(self.csv_path, mode='r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    c_name = row.get("Ten cong ty", "").strip()
                    mst = row.get("MST", "").strip()
                    email = row.get("Email", "").strip()
                    phone = row.get("SDT", "").strip()
                    main_ind = row.get("Nganh chinh", "").strip()
                    address = row.get("Dia chi", "").strip()
                    city = row.get("Tinh/Thanh", "").strip()
                    desc = row.get("Mo ta", "").strip()

                    if c_name:
                        supplier_dict = {
                            "source_platform": "thongtincty_db",
                            "company_name": c_name,
                            "mst_tax_code": mst,
                            "country": "Vietnam",
                            "province_city": city or "TP. Hồ Chí Minh",
                            "address": address or "Việt Nam",
                            "main_products": main_ind or "Doanh nghiệp sản xuất / xuất khẩu",
                            "export_markets": "Toàn cầu",
                            "moq_capacity": desc[:150] if desc else "Cung ứng lớn",
                            "certifications": "ISO / Tiêu chuẩn xuất khẩu",
                            "contact_phone": phone,
                            "contact_email": email,
                            "website": f"https://thongtincty.com/company/{mst}" if mst else "",
                            "detail_url": f"https://thongtincty.com/mst-{mst}" if mst else f"https://thongtincty.com/company/{hash(c_name)}"
                        }
                        results.append(supplier_dict)
        except Exception as e:
            logger.error(f"[{self.name}] Error reading Business_dataset.csv: {e}")

        logger.info(f"[{self.name}] Loaded {len(results)} Vietnamese Supplier records.")
        return results

    def scrape_supplier_posts(self, keywords=None, max_pages=MAX_PAGES_PER_KEYWORD):
        """Generates Product Sell Offers / Bài đăng chào hàng xuất khẩu from dataset."""
        results = []
        if not os.path.exists(self.csv_path):
            return results

        try:
            with open(self.csv_path, mode='r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    c_name = row.get("Ten cong ty", "").strip()
                    mst = row.get("MST", "").strip()
                    main_ind = row.get("Nganh chinh", "").strip()
                    desc = row.get("Mo ta", "").strip()
                    email = row.get("Email", "").strip()
                    phone = row.get("SDT", "").strip()

                    if c_name and main_ind:
                        post_dict = {
                            "source_platform": "thongtincty_db",
                            "company_name": c_name,
                            "product_title": f"Chào bán xuất khẩu: {main_ind}",
                            "description": desc or f"Doanh nghiệp Việt Nam chuyên sản xuất và cung ứng {main_ind} đạt tiêu chuẩn xuất khẩu.",
                            "category": row.get("Nhom nganh", "Sản xuất & Xuất khẩu"),
                            "moq_price": "Thỏa thuận / FOB",
                            "country": "Vietnam",
                            "contact_info": f"Email: {email} | SĐT: {phone}".strip(" |"),
                            "detail_url": f"https://thongtincty.com/offer/{mst}" if mst else f"https://thongtincty.com/offer/{hash(c_name)}"
                        }
                        results.append(post_dict)
        except Exception as e:
            logger.error(f"[{self.name}] Error reading supplier posts: {e}")

        logger.info(f"[{self.name}] Loaded {len(results)} Supplier Sell Posts.")
        return results
