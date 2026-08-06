"""
Base Abstract Scraper Class for B2B Harvester
Includes Stealth Playwright Fallback, Lazy-Loading Auto-Scroll, Contact Info Extraction (Regex), and Proxy Support.
"""

from abc import ABC, abstractmethod
import urllib.request
import ssl
import time
import random
import re
import logging
from config import HEADERS, USER_AGENT_POOL, PROXY_SERVER

logger = logging.getLogger("b2b_harvester.scrapers.base")

# JavaScript Evasion Script for Playwright Stealth (Overrides webdriver and bot flags)
STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en', 'vi']});
Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
window.chrome = { runtime: {} };
"""

# JavaScript Auto-Scroll Script for AJAX / Lazy Loading
AUTO_SCROLL_JS = """
async () => {
    await new Promise((resolve) => {
        var totalHeight = 0;
        var distance = 400;
        var timer = setInterval(() => {
            var scrollHeight = document.body.scrollHeight;
            window.scrollBy(0, distance);
            totalHeight += distance;
            if(totalHeight >= scrollHeight || totalHeight > 3000){
                clearInterval(timer);
                resolve();
            }
        }, 120);
    });
}
"""

class BaseScraper(ABC):
    def __init__(self, name):
        self.name = name
        self.headers = HEADERS.copy()
        self.ssl_context = ssl.create_default_context()
        self.ssl_context.check_hostname = False
        self.ssl_context.verify_mode = ssl.CERT_NONE
        self.cookie_header = None
        self.playwright_cookies = []

    def load_cookies(self, cookie_path):
        """Loads and formats cookies from exported JSON file for urllib and Playwright."""
        import json
        from pathlib import Path
        p = Path(cookie_path)
        if not p.exists():
            logger.warning(f"[{self.name}] Cookie file not found at: {cookie_path}")
            return False

        try:
            with open(p, 'r', encoding='utf-8') as f:
                raw_cookies = json.load(f)

            cookie_strs = []
            pw_cookies = []
            for c in raw_cookies:
                name = c.get("name")
                val = c.get("value")
                if name and val:
                    cookie_strs.append(f"{name}={val}")

                    item = {
                        "name": name,
                        "value": val,
                        "domain": c.get("domain", f".{self.name}.com"),
                        "path": c.get("path", "/"),
                    }
                    if "secure" in c:
                        item["secure"] = bool(c["secure"])
                    if "httpOnly" in c:
                        item["httpOnly"] = bool(c["httpOnly"])
                    if "expirationDate" in c:
                        item["expires"] = float(c["expirationDate"])

                    ss = c.get("sameSite")
                    if ss == "no_restriction":
                        item["sameSite"] = "None"
                    elif ss in ["lax", "Lax"]:
                        item["sameSite"] = "Lax"
                    elif ss in ["strict", "Strict"]:
                        item["sameSite"] = "Strict"

                    pw_cookies.append(item)

            self.cookie_header = "; ".join(cookie_strs)
            self.playwright_cookies = pw_cookies
            logger.info(f"[{self.name}] Loaded {len(pw_cookies)} cookies from {p}")
            return True
        except Exception as e:
            logger.error(f"[{self.name}] Failed to load cookies from {cookie_path}: {e}")
            return False

    def get_random_headers(self):
        """Returns headers with a random User-Agent from pool and session cookies if available."""
        h = self.headers.copy()
        h['User-Agent'] = random.choice(USER_AGENT_POOL)
        if self.cookie_header:
            h['Cookie'] = self.cookie_header
        return h

    def fetch_html(self, url, timeout=14):
        """
        Fetches raw HTML string.
        First attempts fast HTTP request with curl_cffi Chrome impersonation & cookies;
        if blocked by WAF (403/Incapsula/CF), falls back to Playwright Stealth Headless Browser.
        """
        # Random rate-limiting delay between page requests (Chống ban IP)
        time.sleep(random.uniform(1.5, 3.5))
        req_headers = self.get_random_headers()

        html = None
        # 1. Try curl_cffi Chrome TLS impersonation
        try:
            from curl_cffi import requests as cffi_requests
            cookie_dict = {c['name']: c['value'] for c in self.playwright_cookies if 'name' in c and 'value' in c} if self.playwright_cookies else None
            res = cffi_requests.get(url, headers=req_headers, cookies=cookie_dict, impersonate="chrome120", timeout=timeout)
            html = res.text

            if "Incapsula" in html or "Pardon Our Interruption" in html or "Just a moment..." in html or len(html) < 2500:
                logger.info(f"[{self.name}] ⚠️ WAF Challenge detected via curl_cffi for {url}. Switching to Stealth Playwright Browser...")
                html = self.fetch_html_browser(url)
        except Exception as cffi_err:
            # 2. Fallback to urllib
            try:
                req = urllib.request.Request(url, headers=req_headers)
                with urllib.request.urlopen(req, context=self.ssl_context, timeout=timeout) as res:
                    html = res.read().decode('utf-8', errors='ignore')
                    
                    if "Incapsula" in html or "Pardon Our Interruption" in html or "Just a moment..." in html or len(html) < 2500:
                        logger.info(f"[{self.name}] ⚠️ WAF Challenge detected via urllib for {url}. Switching to Stealth Playwright Browser...")
                        html = self.fetch_html_browser(url)
            except Exception as e:
                logger.info(f"[{self.name}] HTTP fetch failed ({e}) for {url}. Switching to Stealth Playwright Browser...")
                html = self.fetch_html_browser(url)

        return html


    def fetch_html_browser(self, url, timeout=30000, cdp_url="http://localhost:9222"):
        """
        Fetches rendered HTML page using Playwright.
        Attempts Chrome CDP connection first (bypasses Imperva Reese84 100%),
        falling back to Playwright Stealth Headless Browser if CDP is unavailable.
        """
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = None
                is_cdp = False
                
                # 1. Try CDP Connection to real Chrome instance
                try:
                    browser = p.chromium.connect_over_cdp(cdp_url)
                    is_cdp = True
                    logger.info(f"[{self.name}] 🚀 Connected to real Chrome via CDP ({cdp_url}) for WAF bypass!")
                    context = browser.contexts[0]
                except Exception as cdp_err:
                    logger.info(f"[{self.name}] CDP not available on {cdp_url}. Launching Playwright Chromium...")
                    launch_options = {"headless": True}
                    if PROXY_SERVER:
                        launch_options["proxy"] = {"server": PROXY_SERVER}
                    browser = p.chromium.launch(**launch_options)
                    user_agent = random.choice(USER_AGENT_POOL)
                    context = browser.new_context(
                        user_agent=user_agent,
                        viewport={'width': 1366, 'height': 768},
                        locale='en-US'
                    )

                if not is_cdp and self.playwright_cookies:
                    try:
                        context.add_cookies(self.playwright_cookies)
                        logger.info(f"[{self.name}] Injected {len(self.playwright_cookies)} cookies into Playwright Context.")
                    except Exception as cookie_err:
                        logger.warning(f"[{self.name}] Playwright add_cookies warning: {cookie_err}")
                
                page = context.new_page()
                
                # Inject stealth events if not CDP
                if not is_cdp:
                    page.add_init_script(STEALTH_JS)
                
                # Navigate to URL
                page.goto(url, wait_until="domcontentloaded", timeout=timeout)
                page.wait_for_timeout(2500)

                # Auto-scroll to trigger AJAX lazy loading
                try:
                    page.evaluate(AUTO_SCROLL_JS)
                    page.wait_for_timeout(1500)
                except Exception as scroll_err:
                    logger.debug(f"[{self.name}] Auto-scroll notice: {scroll_err}")

                html = page.content()
                
                if is_cdp:
                    page.close()
                else:
                    browser.close()

                logger.info(f"[{self.name}] ✅ Browser successfully fetched {len(html)} bytes for {url}")
                return html
        except Exception as e:
            logger.warning(f"[{self.name}] ❌ Browser fetch failed for {url}: {e}")
            return None


    @staticmethod
    def extract_contact_info(text):
        """
        Bóc tách Email và Phone/WhatsApp/WeChat từ văn bản mô tả (Description/Title).
        Khắc phục hạn chế giấu thông tin liên hệ của các sàn B2B.
        """
        if not text:
            return {"email": "", "phone": ""}

        # Regex email
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        emails = re.findall(email_pattern, text)
        extracted_email = emails[0] if emails else ""

        # Regex phone / whatsapp (Dạng +84..., +1..., 090..., WhatsApp: +...)
        phone_pattern = r'(?:WhatsApp|Phone|Tel|Mobile|SĐT|Call|Contact)?[\s:]*(\+?\d{1,4}[\s.-]?\(?\d{1,4}\)?[\s.-]?\d{3,4}[\s.-]?\d{3,4})'
        phones = re.findall(phone_pattern, text, re.IGNORECASE)
        
        valid_phones = []
        for p in phones:
            digits = re.sub(r'\D', '', p)
            if len(digits) >= 8:
                valid_phones.append(p.strip())
                
        extracted_phone = valid_phones[0] if valid_phones else ""

        return {"email": extracted_email, "phone": extracted_phone}

    @abstractmethod
    def scrape_buyers(self, keywords=None, max_pages=3):
        """Scrapes Buyer Leads for given keywords across multiple pages."""
        pass

    @abstractmethod
    def scrape_suppliers_vietnam(self, keywords=None, max_pages=3):
        """Scrapes Vietnamese Suppliers for given keywords across multiple pages."""
        pass

    @abstractmethod
    def scrape_supplier_posts(self, keywords=None, max_pages=3):
        """Scrapes Product Sell Offers / Bài đăng bán hàng of Vietnamese Suppliers for given keywords across multiple pages."""
        pass
