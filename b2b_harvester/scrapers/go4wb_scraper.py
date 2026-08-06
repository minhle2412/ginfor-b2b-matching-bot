"""
Go4WorldBusiness Scraper
Parses Schema.org JSON-LD structured objects for:
1. Buyers (@type: Demand)
2. Vietnam Supplier Directory (@type: Product / Brand)
3. Vietnam Supplier Product Sell Offers (@type: Product / Offer)
Supports URL/page number pagination (?page=N) and automatic regex contact info extraction.
"""

import json
import logging
from bs4 import BeautifulSoup
from .base_scraper import BaseScraper
from config import DEFAULT_KEYWORDS, MAX_PAGES_PER_KEYWORD

logger = logging.getLogger("b2b_harvester.scrapers.go4wb")

class Go4WorldBusinessScraper(BaseScraper):
    def __init__(self):
        super().__init__("go4worldbusiness")

    def scrape_buyers(self, keywords=None, max_pages=MAX_PAGES_PER_KEYWORD):
        keywords = keywords or DEFAULT_KEYWORDS
        results = []

        for kw in keywords:
            for p in range(1, max_pages + 1):
                url = f"https://www.go4worldbusiness.com/buyers/{kw}.html" if p == 1 else f"https://www.go4worldbusiness.com/buyers/{kw}.html?page={p}"
                logger.info(f"[{self.name}] Crawling Buyer Leads (Page {p}/{max_pages}) for '{kw}': {url}")
                html = self.fetch_html(url)
                if not html:
                    continue

                soup = BeautifulSoup(html, 'html.parser')
                json_lds = soup.find_all('script', type='application/ld+json')

                for script in json_lds:
                    try:
                        data = json.loads(script.string)
                        if isinstance(data, dict) and data.get('@type') == 'ItemList':
                            items = data.get('itemListElement', [])
                            for el in items:
                                item = el.get('item', {})
                                if item.get('@type') == 'Demand':
                                    desc_text = item.get("description", "").strip()
                                    title_text = item.get("name", "").strip()
                                    contacts = self.extract_contact_info(f"{title_text}\n{desc_text}")

                                    buyer_dict = {
                                        "source_platform": self.name,
                                        "title": title_text,
                                        "description": desc_text,
                                        "category": f"Agriculture / {kw.title()}",
                                        "buyer_name": item.get("contact", "B2B Importer"),
                                        "buyer_country": item.get("availableAtOrFrom", {}).get("address", {}).get("addressCountry", ""),
                                        "quantity": f"{item.get('eligibleQuantity', {}).get('minValue', '')} {item.get('eligibleQuantity', {}).get('unitText', '')}".strip(),
                                        "destination_port": item.get("destinationPort", ""),
                                        "payment_terms": item.get("acceptedPaymentMethod", ""),
                                        "posted_date": "",
                                        "contact_email": contacts.get("email", ""),
                                        "contact_phone": contacts.get("phone", ""),
                                        "detail_url": item.get("url") or item.get("@id") or url
                                    }
                                    results.append(buyer_dict)
                    except Exception as e:
                        logger.debug(f"[{self.name}] Error parsing JSON-LD script: {e}")

        logger.info(f"[{self.name}] Extracted {len(results)} Buyer records across pages.")
        return results

    def scrape_suppliers_vietnam(self, keywords=None, max_pages=MAX_PAGES_PER_KEYWORD):
        keywords = keywords or DEFAULT_KEYWORDS
        results = []

        for kw in keywords:
            for p in range(1, max_pages + 1):
                url = f"https://www.go4worldbusiness.com/suppliers/vietnam/{kw}.html" if p == 1 else f"https://www.go4worldbusiness.com/suppliers/vietnam/{kw}.html?page={p}"
                logger.info(f"[{self.name}] Crawling Vietnam Suppliers (Page {p}/{max_pages}) for '{kw}': {url}")
                html = self.fetch_html(url)
                if not html:
                    continue

                soup = BeautifulSoup(html, 'html.parser')
                for script in soup.find_all('script', type='application/ld+json'):
                    try:
                        data = json.loads(script.string)
                        if isinstance(data, dict) and data.get('@type') == 'ItemList':
                            items = data.get('itemListElement', [])
                            for el in items:
                                item = el.get('item', {})
                                if item.get('@type') == 'Product':
                                    brand = item.get("brand", {})
                                    address = brand.get("address", {})
                                    country = address.get("addressCountry", "Vietnam")
                                    
                                    if "vietnam" in country.lower():
                                        contacts = self.extract_contact_info(item.get("description", ""))
                                        results.append({
                                            "source_platform": self.name,
                                            "company_name": brand.get("name", "Vietnamese Supplier").strip(),
                                            "mst_tax_code": "",
                                            "country": "Vietnam",
                                            "province_city": address.get("addressLocality", "Ho Chi Minh City"),
                                            "address": address.get("addressLocality", "Vietnam"),
                                            "main_products": item.get("name", f"Export {kw.title()}").strip(),
                                            "export_markets": "Worldwide",
                                            "moq_capacity": "Bulk Export",
                                            "certifications": "ISO / HACCP",
                                            "contact_phone": contacts.get("phone", ""),
                                            "contact_email": contacts.get("email", ""),
                                            "website": "",
                                            "detail_url": item.get("url") or item.get("@id") or url
                                        })
                    except Exception as e:
                        logger.debug(f"[{self.name}] Error parsing supplier JSON-LD: {e}")

        logger.info(f"[{self.name}] Extracted {len(results)} Vietnam Supplier records across pages.")
        return results

    def scrape_supplier_posts(self, keywords=None, max_pages=MAX_PAGES_PER_KEYWORD):
        keywords = keywords or DEFAULT_KEYWORDS
        results = []

        for kw in keywords:
            for p in range(1, max_pages + 1):
                url = f"https://www.go4worldbusiness.com/suppliers/vietnam/{kw}.html" if p == 1 else f"https://www.go4worldbusiness.com/suppliers/vietnam/{kw}.html?page={p}"
                logger.info(f"[{self.name}] Crawling Vietnam Supplier Sell Posts (Page {p}/{max_pages}) for '{kw}': {url}")
                html = self.fetch_html(url)
                if not html:
                    continue

                soup = BeautifulSoup(html, 'html.parser')
                # 1. Parse JSON-LD structured product sell offers
                for script in soup.find_all('script', type='application/ld+json'):
                    try:
                        data = json.loads(script.string)
                        if isinstance(data, dict) and data.get('@type') == 'ItemList':
                            items = data.get('itemListElement', [])
                            for el in items:
                                item = el.get('item', {})
                                if item.get('@type') == 'Product':
                                    prod_name = item.get("name", "").strip()
                                    brand = item.get("brand", {})
                                    comp_name = brand.get("name", "Vietnamese Supplier").strip()
                                    desc_text = item.get("description", "").strip()
                                    offers = item.get("offers", {})
                                    price_str = f"{offers.get('price', '')} {offers.get('priceCurrency', '')}".strip() or "FOB / Thỏa thuận"
                                    contacts = self.extract_contact_info(f"{prod_name}\n{desc_text}")
                                    contact_str = f"Email: {contacts.get('email', '')} | SĐT: {contacts.get('phone', '')}".strip(" |")

                                    detail_url = item.get("url") or item.get("@id") or url

                                    if prod_name:
                                        results.append({
                                            "source_platform": self.name,
                                            "company_name": comp_name,
                                            "product_title": f"Chào bán xuất khẩu: {prod_name}",
                                            "description": desc_text or f"Doanh nghiệp Việt Nam chào bán {prod_name} số lượng lớn phục vụ xuất khẩu.",
                                            "category": f"Xuất Khẩu / {kw.title()}",
                                            "moq_price": price_str,
                                            "country": "Vietnam",
                                            "contact_info": contact_str or "Xem thông tin chi tiết bài đăng",
                                            "detail_url": detail_url
                                        })
                    except Exception as e:
                        logger.debug(f"[{self.name}] Error parsing JSON-LD product sell offer: {e}")

                # 2. DOM Fallback for product cards if JSON-LD parsed items < 5
                if len(results) == 0:
                    for card in soup.select('.supplier-product-card, .product-card, .gold-supplier-box, div[class*="product"]'):
                        title_el = card.select_one('h3 a, h2 a, .product-title, a[href*="/product/"]')
                        comp_el = card.select_one('.company-name, .supplier-name')
                        desc_el = card.select_one('.description, p')

                        if title_el:
                            t_text = title_el.get_text(strip=True)
                            c_text = comp_el.get_text(strip=True) if comp_el else "Doanh Nghiệp Việt Nam"
                            d_text = desc_el.get_text(strip=True) if desc_el else f"Sản phẩm {t_text} chất lượng cao xuất khẩu"
                            p_url = title_el.get('href', url)
                            if not p_url.startswith('http'):
                                p_url = f"https://www.go4worldbusiness.com{p_url}"

                            contacts = self.extract_contact_info(f"{t_text}\n{d_text}")
                            contact_str = f"Email: {contacts.get('email', '')} | SĐT: {contacts.get('phone', '')}".strip(" |")

                            results.append({
                                "source_platform": self.name,
                                "company_name": c_text,
                                "product_title": t_text,
                                "description": d_text,
                                "category": f"Xuất Khẩu / {kw.title()}",
                                "moq_price": "FOB / Thỏa thuận",
                                "country": "Vietnam",
                                "contact_info": contact_str or "Xem bài đăng gốc",
                                "detail_url": p_url
                            })

        logger.info(f"[{self.name}] Extracted {len(results)} Supplier Product Sell Posts across pages.")
        return results
