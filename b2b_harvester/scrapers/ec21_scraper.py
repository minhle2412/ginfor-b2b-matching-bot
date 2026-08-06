"""
EC21 Scraper
Extracts:
1. Buyer Leads from importer.ec21.com (JSON-LD)
2. Vietnam Supplier Directory & Sell Offers from www.ec21.com
Supports URL/page number pagination (/page-N.html and ?page=N) and regex contact extraction.
"""

import json
import logging
from bs4 import BeautifulSoup
from .base_scraper import BaseScraper
from config import DEFAULT_KEYWORDS, MAX_PAGES_PER_KEYWORD

logger = logging.getLogger("b2b_harvester.scrapers.ec21")

class EC21Scraper(BaseScraper):
    def __init__(self):
        super().__init__("ec21")

    def scrape_buyers(self, keywords=None, max_pages=MAX_PAGES_PER_KEYWORD):
        keywords = keywords or DEFAULT_KEYWORDS
        results = []

        for kw in keywords:
            for p in range(1, max_pages + 1):
                url = f"https://importer.ec21.com/Agriculture--01/1/{kw}.html" if p == 1 else f"https://importer.ec21.com/Agriculture--01/1/{kw}/page-{p}.html"
                logger.info(f"[{self.name}] Crawling Importers (Page {p}/{max_pages}) for '{kw}': {url}")
                html = self.fetch_html(url)
                if not html:
                    continue

                soup = BeautifulSoup(html, 'html.parser')
                script = soup.find('script', type='application/ld+json')

                if script:
                    try:
                        data = json.loads(script.string)
                        items = data.get('itemListElement', [])
                        for el in items:
                            lead_url = el.get('url', '')
                            lead_title = el.get('name', '').strip()
                            if lead_url:
                                contacts = self.extract_contact_info(lead_title)
                                buyer_dict = {
                                    "source_platform": self.name,
                                    "title": lead_title,
                                    "description": f"Buy Lead Requirement: {lead_title}",
                                    "category": f"Agriculture / {kw.title()}",
                                    "buyer_name": "EC21 Importer",
                                    "buyer_country": "Global",
                                    "quantity": "",
                                    "destination_port": "",
                                    "payment_terms": "",
                                    "posted_date": "",
                                    "contact_email": contacts.get("email", ""),
                                    "contact_phone": contacts.get("phone", ""),
                                    "detail_url": lead_url
                                }
                                results.append(buyer_dict)
                    except Exception as e:
                        logger.debug(f"[{self.name}] Error parsing EC21 JSON-LD: {e}")

        logger.info(f"[{self.name}] Extracted {len(results)} Buyer records across pages.")
        return results

    def scrape_suppliers_vietnam(self, keywords=None, max_pages=MAX_PAGES_PER_KEYWORD):
        keywords = keywords or DEFAULT_KEYWORDS
        results = []

        for kw in keywords:
            for p in range(1, max_pages + 1):
                url = f"https://www.ec21.com/search/product_list.jsp?kw={kw}&country=VN" if p == 1 else f"https://www.ec21.com/search/product_list.jsp?kw={kw}&country=VN&page={p}"
                logger.info(f"[{self.name}] Crawling Vietnam Suppliers (Page {p}/{max_pages}) for '{kw}': {url}")
                html = self.fetch_html(url)
                if not html:
                    continue

                soup = BeautifulSoup(html, 'html.parser')
                # Parse all product / company cards from DOM
                for card in soup.select('.pro_list li, .search_list_box, .list_item, tr, div[class*="item"]'):
                    title_tag = card.select_one('a.title, h3 a, .prod_name a, a[href*="/product/"], a[href*="/company/"]')
                    company_tag = card.select_one('.comp_name, .company_name, a.company')

                    if title_tag:
                        p_name = title_tag.get_text(strip=True)
                        c_name = company_tag.get_text(strip=True) if company_tag else "Vietnamese Exporting Supplier"
                        p_url = title_tag.get('href', url)
                        if not p_url.startswith('http'):
                            p_url = f"https://www.ec21.com{p_url}"

                        contacts = self.extract_contact_info(card.get_text(strip=True))

                        if p_name and len(p_name) > 3:
                            results.append({
                                "source_platform": self.name,
                                "company_name": c_name,
                                "mst_tax_code": "",
                                "country": "Vietnam",
                                "province_city": "Ho Chi Minh City / Hanoi",
                                "address": "Vietnam",
                                "main_products": p_name,
                                "export_markets": "Worldwide",
                                "moq_capacity": "Bulk Export",
                                "certifications": "ISO / HACCP",
                                "contact_phone": contacts.get("phone", ""),
                                "contact_email": contacts.get("email", ""),
                                "website": "",
                                "detail_url": p_url
                            })

        logger.info(f"[{self.name}] Extracted {len(results)} Vietnam Supplier records across pages.")
        return results

    def scrape_supplier_posts(self, keywords=None, max_pages=MAX_PAGES_PER_KEYWORD):
        keywords = keywords or DEFAULT_KEYWORDS
        results = []

        for kw in keywords:
            for p in range(1, max_pages + 1):
                url = f"https://www.ec21.com/search/product_list.jsp?kw={kw}&country=VN" if p == 1 else f"https://www.ec21.com/search/product_list.jsp?kw={kw}&country=VN&page={p}"
                logger.info(f"[{self.name}] Crawling EC21 Vietnam Product Sell Offers (Page {p}/{max_pages}) for '{kw}': {url}")
                html = self.fetch_html(url)
                if not html:
                    continue

                soup = BeautifulSoup(html, 'html.parser')
                for item in soup.select('.pro_list li, .search_list_box, .list_item, div[class*="product"], div[class*="item"]'):
                    title_tag = item.select_one('a.title, h3 a, .prod_name a, a[href*="/product/"]')
                    company_tag = item.select_one('.comp_name, .company_name, a.company')
                    desc_tag = item.select_one('.desc, .summary, p')

                    if title_tag:
                        prod_title = title_tag.get_text(strip=True)
                        comp_name = company_tag.get_text(strip=True) if company_tag else "Doanh Nghiệp VN (EC21)"
                        desc_text = desc_tag.get_text(strip=True) if desc_tag else f"Chào bán xuất khẩu sản phẩm {prod_title} từ Việt Nam"

                        p_url = title_tag.get('href', url)
                        if not p_url.startswith('http'):
                            p_url = f"https://www.ec21.com{p_url}"

                        contacts = self.extract_contact_info(f"{prod_title}\n{desc_text}")
                        contact_str = f"Email: {contacts.get('email', '')} | SĐT: {contacts.get('phone', '')}".strip(" |")

                        if prod_title and len(prod_title) > 3:
                            results.append({
                                "source_platform": self.name,
                                "company_name": comp_name,
                                "product_title": f"Chào bán xuất khẩu: {prod_title}",
                                "description": desc_text,
                                "category": f"Nông Sản / {kw.title()}",
                                "moq_price": "Thỏa thuận / FOB",
                                "country": "Vietnam",
                                "contact_info": contact_str or "Chi tiết trên sàn EC21",
                                "detail_url": p_url
                            })

        logger.info(f"[{self.name}] Extracted {len(results)} Supplier Product Sell Posts across pages.")
        return results
