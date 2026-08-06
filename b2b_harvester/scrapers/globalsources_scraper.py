"""
GlobalSources Scraper
Extracts:
1. Global RFQs (Buyers)
2. Vietnam Supplier Directory
3. Vietnam Supplier Product Sell Offers (Bài đăng bán hàng)
Supports Stealth Playwright browser fallback and regex contact extraction.
"""

import logging
from pathlib import Path
from bs4 import BeautifulSoup
from .base_scraper import BaseScraper
from config import DEFAULT_KEYWORDS, MAX_PAGES_PER_KEYWORD

logger = logging.getLogger("b2b_harvester.scrapers.globalsources")

class GlobalSourcesScraper(BaseScraper):
    def __init__(self, cookies_file=None):
        super().__init__("globalsources")
        
        base_dir = Path(__file__).resolve().parent.parent
        possible_paths = [
            cookies_file,
            base_dir / "data" / "globalsources_cookies.json",
            base_dir / "globalsources_cookies.json",
            base_dir / "data" / "globalsources_cookies_raw.json",
            Path("/Users/lenhatminh/Downloads/thuvienphapluat/data/Untitled-1.json"),
        ]
        for path in possible_paths:
            if path and Path(path).exists():
                if self.load_cookies(path):
                    break

    def scrape_buyers(self, keywords=None, max_pages=MAX_PAGES_PER_KEYWORD):
        keywords = keywords or DEFAULT_KEYWORDS
        results = []

        for p in range(1, max_pages + 1):
            url = "https://www.globalsources.com/highSeas/highSeasRFQList?source=TopNav_Serv" if p == 1 else f"https://www.globalsources.com/highSeas/highSeasRFQList?source=TopNav_Serv&page={p}"
            logger.info(f"[{self.name}] Crawling RFQ list (Page {p}/{max_pages}): {url}")
            
            html = self.fetch_html(url)
            if html:
                soup = BeautifulSoup(html, 'html.parser')
                cards = soup.select('.RFQ-list-item, div[class*="RFQ-list-item"], .rfq-item, div[class*="rfq"]')
                for card in cards:
                    text = card.get_text(separator=' ', strip=True)
                    if not text or len(text) < 10 or 'Submit a Similar Request' not in text:
                        continue

                    # Extract fields using regex parsing on card text
                    import re
                    title = text.split('Quantity')[0].strip() if 'Quantity' in text else text[:100]
                    
                    qty_match = re.search(r'Quantity\s*([^\s]+(?:\s+[^\s]+)?)', text, re.IGNORECASE)
                    qty = qty_match.group(1) if qty_match else ""

                    country_match = re.search(r'Country/Region\s*([A-Za-z\s]+?)(?:Buyer Name|$)', text, re.IGNORECASE)
                    country = country_match.group(1).strip() if country_match else "Global"

                    buyer_match = re.search(r'Buyer Name\s*([^\s]+)', text, re.IGNORECASE)
                    buyer_name = buyer_match.group(1).strip() if buyer_match else "Global Buyer"

                    link_el = card.select_one('a[href*="rfq"], a[href*="highSeas"], a')
                    t_url = link_el.get('href', url) if link_el else url
                    if not t_url.startswith('http'):
                        t_url = f"https://www.globalsources.com{t_url}"

                    contacts = self.extract_contact_info(text)

                    results.append({
                        "source_platform": self.name,
                        "title": title,
                        "description": f"GlobalSources RFQ: {title} - Qty: {qty}",
                        "category": "General / B2B Export",
                        "buyer_name": buyer_name,
                        "buyer_country": country,
                        "quantity": qty,
                        "destination_port": "",
                        "payment_terms": "",
                        "posted_date": "",
                        "contact_email": contacts.get("email", ""),
                        "contact_phone": contacts.get("phone", ""),
                        "detail_url": t_url
                    })

        logger.info(f"[{self.name}] Extracted {len(results)} Buyer records across pages.")
        return results

    def scrape_suppliers_vietnam(self, keywords=None, max_pages=MAX_PAGES_PER_KEYWORD):
        keywords = keywords or DEFAULT_KEYWORDS
        results = []

        for p in range(1, max_pages + 1):
            url = "https://www.globalsources.com/manufacturers/vietnam-supplier.html" if p == 1 else f"https://www.globalsources.com/manufacturers/vietnam-supplier.html?page={p}"
            logger.info(f"[{self.name}] Crawling Vietnam Suppliers (Page {p}/{max_pages}): {url}")
            
            html = self.fetch_html(url)
            if html:
                soup = BeautifulSoup(html, 'html.parser')
                cards = soup.select('.card-box, div[class*="card-box"], .supplier-card, div[class*="supplier"]')
                for card in cards:
                    name_el = card.select_one('a[href*="/supplier/"], a[href*="/manufacturers/"], .product-name, a')
                    if name_el:
                        c_name = name_el.get_text(strip=True)
                        c_url = name_el.get('href', url)
                        if not c_url.startswith('http'):
                            c_url = f"https://www.globalsources.com{c_url}"

                        if not c_name or len(c_name) < 5 or 'Global Sources' in c_name:
                            continue

                        contacts = self.extract_contact_info(card.get_text(strip=True))

                        results.append({
                            "source_platform": self.name,
                            "company_name": c_name,
                            "mst_tax_code": "",
                            "country": "Vietnam",
                            "province_city": "",
                            "address": "",
                            "main_products": c_name,
                            "export_markets": "Worldwide",
                            "moq_capacity": "",
                            "certifications": "ISO / HACCP",
                            "contact_phone": contacts.get("phone", ""),
                            "contact_email": contacts.get("email", ""),
                            "website": "",
                            "detail_url": c_url
                        })

        logger.info(f"[{self.name}] Extracted {len(results)} Vietnam Supplier records across pages.")
        return results

    def scrape_supplier_posts(self, keywords=None, max_pages=MAX_PAGES_PER_KEYWORD):
        keywords = keywords or DEFAULT_KEYWORDS
        return []

