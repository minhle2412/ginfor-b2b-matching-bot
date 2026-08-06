"""
Daily Automation Scheduler for B2B Harvester
Executes Phase 1 (Buyers) daily (1 time per day at 07:00 AM ICT).
Executes Phase 2 (Vietnam Suppliers) weekly (Mondays at 08:00 AM ICT).
"""

import time
import logging
from datetime import datetime, timezone, timedelta
from config import (
    PHASE1_SCHEDULE_HOUR,
    PHASE1_SCHEDULE_MINUTE,
    DEFAULT_KEYWORDS
)
from database import DatabaseManager
from embeddings import VectorEmbedder
from scrapers import (
    Go4WorldBusinessScraper,
    EC21Scraper,
    GlobalSourcesScraper,
    TradeWheelScraper
)
from run_harvester import run_phase1_buyers, run_phase2_suppliers

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(levelname)s] %(name)s - %(message)s'
)
logger = logging.getLogger("b2b_harvester.scheduler")

ICT_TZ = timezone(timedelta(hours=7))

def start_daily_scheduler():
    logger.info("==================================================")
    logger.info("🚀 STARTING B2B HARVESTER DAILY AUTOMATION SERVICE")
    logger.info(f"📅 Phase 1 (Buyers): Scheduled Daily at {PHASE1_SCHEDULE_HOUR:02d}:{PHASE1_SCHEDULE_MINUTE:02d} ICT")
    logger.info("📅 Phase 2 (Suppliers): Scheduled Weekly on Monday at 08:00 ICT")
    logger.info("==================================================")

    db = DatabaseManager()
    embedder = VectorEmbedder()
    scrapers = [
        Go4WorldBusinessScraper(),
        EC21Scraper(),
        GlobalSourcesScraper(),
        TradeWheelScraper()
    ]

    last_run_day = None

    while True:
        now_ict = datetime.now(ICT_TZ)
        current_day_str = now_ict.strftime("%Y-%m-%d")

        # Check if it's 07:00 AM ICT and hasn't run today yet
        if now_ict.hour == PHASE1_SCHEDULE_HOUR and now_ict.minute >= PHASE1_SCHEDULE_MINUTE:
            if last_run_day != current_day_str:
                logger.info(f"⏰ Daily Scheduled Trigger Fired for {current_day_str}")
                
                # Execute Phase 1 (Buyers)
                run_phase1_buyers(db, embedder, scrapers, DEFAULT_KEYWORDS)
                
                # Execute Phase 2 (Suppliers) if today is Monday
                if now_ict.weekday() == 0:
                    logger.info("🗓️ Monday Weekly Trigger Fired for Phase 2 Suppliers.")
                    run_phase2_suppliers(db, embedder, scrapers, DEFAULT_KEYWORDS)

                last_run_day = current_day_str
                logger.info(f"✅ Completed daily run for {current_day_str}. Waiting for tomorrow...")

        # Sleep for 60 seconds before next check
        time.sleep(60)

if __name__ == "__main__":
    start_daily_scheduler()
