"""
Script to audit Facebook groups for buyer intent posts.
It uses existing cookies from .env and SBERT model to verify if groups contain actual buyer posts.
"""
import asyncio
import os
import sys
import logging
from dotenv import load_dotenv

# Set logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from fb_matching_bot import (
    get_facebook_cookies, 
    scrape_group_posts, 
    check_partner_intent_embedding,
    load_embedding_model
)

# Load env
env_path = "../DiscordBot/.env.bot.facebook"
load_dotenv(env_path)

# List of groups to check
FB_GROUP_IDS_RAW = os.getenv("FB_GROUP_IDS", "")
all_groups = [g.strip() for g in FB_GROUP_IDS_RAW.split(",") if g.strip()]

# Remove specified groups
to_remove = {"TimdailyNPP", "hiephoinhacungcap"}
groups_to_audit = [g for g in all_groups if g not in to_remove]

async def audit_groups():
    cookies = get_facebook_cookies()
    if not cookies:
        logger.error("❌ Cookies not found in .env file!")
        return

    logger.info("🧠 Loading SBERT model...")
    load_embedding_model()

    logger.info(f"🔍 Auditing {len(groups_to_audit)} Facebook Groups...")
    print(f"\nAUDIT PLAN: Checking {len(groups_to_audit)} groups (Removed: {to_remove})\n")

    results = {}

    for group_id in groups_to_audit:
        logger.info(f"Checking group: {group_id}...")
        try:
            # Scrape 1 page (fast audit)
            posts = await scrape_group_posts(group_id, cookies, pages=1)
            
            buyer_posts_count = 0
            matched_posts = []

            for post in posts:
                is_buyer, score = check_partner_intent_embedding(post["text"])
                if is_buyer:
                    buyer_posts_count += 1
                    matched_posts.append((post["text"][:120].replace('\n', ' '), score))

            results[group_id] = {
                "total_scraped": len(posts),
                "buyer_count": buyer_posts_count,
                "matches": matched_posts,
                "status": "KEEP" if buyer_posts_count > 0 else "REMOVE"
            }
            logger.info(f"Group {group_id}: Found {buyer_posts_count} buyer posts out of {len(posts)} scraped.")
        except Exception as e:
            logger.error(f"❌ Error auditing group {group_id}: {e}")
            results[group_id] = {
                "total_scraped": 0,
                "buyer_count": 0,
                "matches": [],
                "status": "ERROR"
            }

    # Print Report
    print("\n" + "="*80)
    print("📋 FACEBOOK GROUPS AUDIT REPORT")
    print("="*80)
    for g_id, res in results.items():
        print(f"\n👥 Group: {g_id}")
        print(f"   📊 Total Scraped: {res['total_scraped']} posts")
        print(f"   🎯 Buyer Posts: {res['buyer_count']} found")
        print(f"   ⚙️ Action Recommendation: **{res['status']}**")
        if res["matches"]:
            print("   📝 Sample Matches:")
            for text, score in res["matches"][:3]:
                print(f"      - [{int(score*100)}%] {text}...")
    print("="*80 + "\n")

    # Generate new list of group IDs
    kept_groups = [g for g, res in results.items() if res["status"] == "KEEP"]
    print(f"RECOMMENDED FB_GROUP_IDS list:\n{','.join(kept_groups)}")

if __name__ == "__main__":
    asyncio.run(audit_groups())
