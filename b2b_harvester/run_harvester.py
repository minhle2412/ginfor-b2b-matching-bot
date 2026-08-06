"""
B2B Harvester Pipeline Runner
Standalone CLI script to trigger scraping from 4 B2B platforms + Local Business Dataset:
- Go4WorldBusiness (URL Pagination & JSON-LD)
- EC21 (URL Pagination & JSON-LD)
- GlobalSources (URL Pagination & Playwright WAF Bypass)
- TradeWheel (URL Pagination & Playwright WAF Bypass)
- Local Vietnamese Business Dataset (Business_dataset.csv)

Harvests 2 Core Datasets:
1. buyers (Global Buyer Lead Posts / Bài đăng nhu cầu người mua)
2. suppliers_vietnam (Vietnamese Enterprise Directory / Thông tin doanh nghiệp supplier)
(Note: Supplier product sell posts harvesting disabled as per requirement)
"""

import sys
import argparse
import logging
from config import DEFAULT_KEYWORDS, MAX_PAGES_PER_KEYWORD
from database import DatabaseManager
from embeddings import VectorEmbedder
from scrapers import (
    Go4WorldBusinessScraper,
    EC21Scraper,
    GlobalSourcesScraper,
    TradeWheelScraper,
    LocalBusinessDatasetImporter
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(levelname)s] %(name)s - %(message)s'
)
logger = logging.getLogger("b2b_harvester.main")

def run_phase1_buyers(db, embedder, scrapers, keywords, max_pages):
    """Executes Phase 1: Global Buyers Scraping Pipeline across multiple URL pages."""
    logger.info(f"=== STARTING PHASE 1: GLOBAL BUYERS HARVESTING (Max Pages: {max_pages}) ===")
    total_saved = 0

    for scraper in scrapers:
        try:
            logger.info(f"--> Running {scraper.name.upper()} Buyer Scraper...")
            buyers = scraper.scrape_buyers(keywords, max_pages=max_pages)
            
            for item in buyers:
                # Generate SBERT embedding vector
                text_for_embed = f"{item['title']} - {item['description']} - Quốc gia: {item['buyer_country']}"
                item["vector_embedding"] = embedder.embed_text(text_for_embed)
                
                saved = db.save_buyer(item)
                if saved:
                    total_saved += 1
        except Exception as e:
            logger.error(f"Error executing {scraper.name} buyer scraper: {e}")

    logger.info(f"=== COMPLETED PHASE 1: Saved {total_saved} new buyer records. ===")
    return total_saved

def run_phase2_suppliers(db, embedder, scrapers, keywords, max_pages):
    """Executes Phase 2: Vietnam Exporting Suppliers Directory Pipeline."""
    logger.info(f"=== STARTING PHASE 2: VIETNAM SUPPLIERS DIRECTORY HARVESTING (Max Pages: {max_pages}) ===")
    total_suppliers_saved = 0

    for scraper in scrapers:
        # Harvest Supplier Companies Only (do NOT scrape supplier sell posts)
        try:
            logger.info(f"--> Running {scraper.name.upper()} Vietnam Supplier Directory Scraper...")
            suppliers = scraper.scrape_suppliers_vietnam(keywords, max_pages=max_pages)
            
            for item in suppliers:
                text_for_embed = f"{item['company_name']} - Sản phẩm: {item['main_products']} - Địa chỉ: {item['address']}"
                item["vector_embedding"] = embedder.embed_text(text_for_embed)
                
                saved = db.save_supplier(item)
                if saved:
                    total_suppliers_saved += 1
        except Exception as e:
            logger.error(f"Error executing {scraper.name} supplier scraper: {e}")

    logger.info(f"=== COMPLETED PHASE 2: Saved {total_suppliers_saved} suppliers. ===")
    return total_suppliers_saved

def main():
    parser = argparse.ArgumentParser(description="B2B Harvester Pipeline Runner for thongtincty.com")
    parser.add_argument("--phase", choices=["1", "2", "all"], default="all", help="1=Buyers only, 2=Suppliers Info only, all=Both")
    parser.add_argument("--keywords", nargs="+", default=None, help="Custom search keywords (e.g. --keywords rice coffee)")
    parser.add_argument("--max-pages", type=int, default=MAX_PAGES_PER_KEYWORD, help="Number of pages to scrape per keyword (default: 3)")
    args = parser.parse_args()

    keywords = args.keywords or DEFAULT_KEYWORDS
    logger.info(f"Target Keywords: {keywords} | Max Pages per Keyword: {args.max_pages}")

    # Initialize components
    db = DatabaseManager()
    embedder = VectorEmbedder()
    scrapers = [
        Go4WorldBusinessScraper(),
        EC21Scraper(),
        GlobalSourcesScraper(),
        TradeWheelScraper(),
        LocalBusinessDatasetImporter()
    ]

    if args.phase in ["1", "all"]:
        run_phase1_buyers(db, embedder, scrapers, keywords, max_pages=args.max_pages)

    if args.phase in ["2", "all"]:
        run_phase2_suppliers(db, embedder, scrapers, keywords, max_pages=args.max_pages)

    stats = db.get_stats()
    logger.info(f"Database Current Stats: {stats}")

if __name__ == "__main__":
    main()

