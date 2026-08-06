"""
Config settings for B2B Harvester System
Isolated standalone module for thongtincty.com B2B integration.
Includes WAF stealth bypass, proxy support, and user-agent rotation.
"""

import os
from pathlib import Path

# Base directory
BASE_DIR = Path(__file__).resolve().parent

# Database Configuration
DB_PATH = os.getenv("B2B_HARVESTER_DB", str(BASE_DIR / "b2b_harvester.db"))

# Schedule Configuration
# Phase 1: Daily scraping (1 time per day)
PHASE1_SCHEDULE_HOUR = 7    # 07:00 AM ICT
PHASE1_SCHEDULE_MINUTE = 0

# Phase 2: Weekly scraping (1 time per week)
PHASE2_SCHEDULE_DAY = "monday"
PHASE2_SCHEDULE_HOUR = 8

# Pagination limit per keyword
MAX_PAGES_PER_KEYWORD = int(os.getenv("B2B_MAX_PAGES", "3"))

# Optional Proxy Server (e.g. "http://user:pass@ip:port")
PROXY_SERVER = os.getenv("B2B_PROXY_SERVER", None)

# User Agent Pool for Rotation
USER_AGENT_POOL = [
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2.1 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0',
]

# Default User Agent Headers
HEADERS = {
    'User-Agent': USER_AGENT_POOL[0],
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9,vi;q=0.8',
    'Sec-Ch-Ua': '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
    'Sec-Ch-Ua-Mobile': '?0',
    'Sec-Ch-Ua-Platform': '"macOS"',
}

# Target Keywords for Scrapers (Agricultural & High-Demand Export Categories)
DEFAULT_KEYWORDS = [
    "rice", "coffee", "cashew", "pepper", "seafood", 
    "garment", "handicraft", "wood", "spices", "fruit"
]

# Embedding Model
EMBEDDING_MODEL_NAME = 'keepitreal/vietnamese-sbert'
