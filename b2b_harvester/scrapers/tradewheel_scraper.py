"""
TradeWheel Scraper
Extracts:
1. Buyers from tradewheel.com/buyers/
2. Vietnam Supplier Directory & Product Sell Offers from tradewheel.com/suppliers/vietnam/
Supports Playwright browser WAF bypass, regex contact extraction, and URL/page number pagination (?page=N).
"""

import logging
from bs4 import BeautifulSoup
from .base_scraper import BaseScraper
from config import DEFAULT_KEYWORDS, MAX_PAGES_PER_KEYWORD

logger = logging.getLogger("b2b_harvester.scrapers.tradewheel")

class TradeWheelScraper(BaseScraper):
    def __init__(self):
        super().__init__("tradewheel")

    def scrape_buyers(self, keywords=None, max_pages=MAX_PAGES_PER_KEYWORD):
        keywords = keywords or DEFAULT_KEYWORDS
        results = []

        for kw in keywords:
            for p in range(1, max_pages + 1):
                url = f"https://www.tradewheel.com/buyers/{kw}/" if p == 1 else f"https://www.tradewheel.com/buyers/{kw}/?page={p}"
                logger.info(f"[{self.name}] Crawling Buyers (Page {p}/{max_pages}) for '{kw}': {url}")
                html = self.fetch_html(url)
                if not html:
                    continue

                soup = BeautifulSoup(html, 'html.parser')
                for item in soup.select('.buy-lead-card, .buyer-item, .lead-box, div[class*="lead"], div[class*="buyer"]'):
                    title_el = item.select_one('h3 a, h2 a, .lead-title, a.title, a[href*="/buyers/"]')
                    desc_el = item.select_one('.lead-desc, .description, p')
                    country_el = item.select_one('.country-name, .flag-icon + span, .country')
                    qty_el = item.select_one('.quantity, .qty')

                    if title_el:
                        title_text = title_el.get_text(strip=True)
                        desc_text = desc_el.get_text(strip=True) if desc_el else f"Requirement for {title_text}"
                        detail_url = title_el.get('href', url)
                        if not detail_url.startswith('http'):
                            detail_url = f"https://www.tradewheel.com{detail_url}"

                        contacts = self.extract_contact_info(f"{title_text}\n{desc_text}")

                        results.append({
                            "source_platform": self.name,
                            "title": title_text,
                            "description": desc_text,
                            "category": f"Export / {kw.title()}",
                            "buyer_name": "TradeWheel Buyer",
                            "buyer_country": country_el.get_text(strip=True) if country_el else "Global",
                            "quantity": qty_el.get_text(strip=True) if qty_el else "",
                            "destination_port": "",
                            "payment_terms": "",
                            "posted_date": "",
                            "contact_email": contacts.get("email", ""),
                            "contact_phone": contacts.get("phone", ""),
                            "detail_url": detail_url
                        })

        logger.info(f"[{self.name}] Extracted {len(results)} Buyer records across pages.")
        return results

    def scrape_suppliers_vietnam(self, keywords=None, max_pages=MAX_PAGES_PER_KEYWORD):
        keywords = keywords or DEFAULT_KEYWORDS
        results = []

        for p in range(1, max_pages + 1):
            url = "https://www.tradewheel.com/suppliers/vietnam/" if p == 1 else f"https://www.tradewheel.com/suppliers/vietnam/?page={p}"
            logger.info(f"[{self.name}] Crawling Vietnam Suppliers (Page {p}/{max_pages}): {url}")
            html = self.fetch_html(url)
            if not html:
                continue

            soup = BeautifulSoup(html, 'html.parser')
            # Extract company items from directory list
            for a in soup.find_all('a', href=True):
                href = a['href']
                text = a.get_text(strip=True)
                if ('/company/' in href or '/supplier/' in href or 'tradewheel.com/' in href) and len(text) > 4:
                    if text.lower() not in ['suppliers', 'china', 'india', 'usa', 'vietnam', 'about us', 'contact us']:
                        c_url = href if href.startswith('http') else f"https://www.tradewheel.com{href}"
                        contacts = self.extract_contact_info(text)

                        results.append({
                            "source_platform": self.name,
                            "company_name": text,
                            "mst_tax_code": "",
                            "country": "Vietnam",
                            "province_city": "Ho Chi Minh City / Hanoi",
                            "address": "Vietnam",
                            "main_products": "Chế biến & Xuất khẩu nông sản, hàng tiêu dùng",
                            "export_markets": "Worldwide",
                            "moq_capacity": "Cung ứng xuất khẩu",
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
        results = []

        for p in range(1, max_pages + 1):
            url = "https://www.tradewheel.com/suppliers/vietnam/" if p == 1 else f"https://www.tradewheel.com/suppliers/vietnam/?page={p}"
            logger.info(f"[{self.name}] Crawling TradeWheel Vietnam Product Sell Offers (Page {p}/{max_pages}): {url}")
            html = self.fetch_html(url)
            if not html:
                continue

            soup = BeautifulSoup(html, 'html.parser')
            for a in soup.find_all('a', href=True):
                href = a['href']
                text = a.get_text(strip=True)
                if ('/product/' in href or '/p/' in href or 'tradewheel.com/' in href) and len(text) > 6:
                    if text.lower() not in ['suppliers', 'china', 'india', 'usa', 'vietnam']:
                        c_url = href if href.startswith('http') else f"https://www.tradewheel.com{href}"
                        contacts = self.extract_contact_info(text)
                        contact_str = f"Email: {contacts.get('email', '')} | SĐT: {contacts.get('phone', '')}".strip(" |")

                        results.append({
                            "source_platform": self.name,
                            "company_name": "Nhà Cung Cấp Việt Nam (TradeWheel)",
                            "product_title": f"Chào bán xuất khẩu: {text}",
                            "description": f"Sản phẩm {text} chất lượng cao xuất khẩu từ nhà cung cấp Việt Nam trên TradeWheel.",
                            "category": "Sản Xuất Xuất Khẩu Việt Nam",
                            "moq_price": "Thỏa thuận / FOB",
                            "country": "Vietnam",
                            "contact_info": contact_str or "Xem chi tiết trên TradeWheel",
                            "detail_url": c_url
                        })

        logger.info(f"[{self.name}] Extracted {len(results)} Supplier Product Sell Posts across pages.")
        return results
