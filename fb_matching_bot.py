"""
Facebook Group Buyer Tracker + B2B Matching — Discord Bot
==========================================================
Clone của facebook_scraper_bot.py tối ưu cho project B2B Matching.

Thay vì chỉ gửi bài viết buyer đơn giản về Discord:
  1. Scrape bài viết từ Facebook groups (giữ nguyên logic gốc)
  2. Lọc bài viết có buyer intent bằng Vietnamese SBERT
  3. Chạy bài viết qua B2B Matching Engine (9.600+ doanh nghiệp)
  4. Gửi kết quả matching (top 5 DN phù hợp + thông tin liên hệ) về Discord

Cách chạy:
    python fb_matching_bot.py -e .env.bot.facebook
"""

import asyncio
import os
import sys
import json
import logging
import argparse
import re
import hashlib
from datetime import datetime, time, timedelta, timezone

import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv

# ===================== OUTREACH ENGINE INTEGRATION =====================
from outreach import OutreachEngine
from outreach.discord_outreach import send_outreach_preview

# ===================== ARGPARSE & ENV LOADING =====================
parser = argparse.ArgumentParser(description="Chạy Facebook B2B Matching Bot.")
parser.add_argument("-e", "--env", help="Đường dẫn tới file .env cấu hình", default=None)
args, unknown = parser.parse_known_args()

if args.env and os.path.exists(args.env):
    load_dotenv(args.env, override=True)
    print(f"ℹ️ Đang tải cấu hình từ file: {args.env}")
else:
    # Tìm file .env trong thư mục hiện tại hoặc thư mục DiscordBot
    default_envs = ['.env.bot.facebook', '.env', '../DiscordBot/.env.bot.facebook']
    loaded = False
    for path in default_envs:
        if os.path.exists(path):
            load_dotenv(path, override=True)
            print(f"ℹ️ Đang tải cấu hình từ: {path}")
            loaded = True
            break
    if not loaded:
        load_dotenv()
        print("ℹ️ Đang tải cấu hình từ hệ thống")

# ===================== LOGGING =====================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ===================== CẤU HÌNH =====================
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "YOUR_DISCORD_BOT_TOKEN")

_channel_id_raw = os.getenv("DISCORD_CHANNEL_ID", "0")
try:
    DISCORD_CHANNEL_ID = int(_channel_id_raw)
except ValueError:
    DISCORD_CHANNEL_ID = 0
    logger.warning(f"⚠️ DISCORD_CHANNEL_ID không hợp lệ: '{_channel_id_raw}'.")

FB_COOKIE_C_USER = os.getenv("FB_COOKIE_C_USER", "")
FB_COOKIE_XS = os.getenv("FB_COOKIE_XS", "")

FB_GROUP_IDS_RAW = os.getenv("FB_GROUP_IDS", "")
FB_GROUP_IDS = [g.strip() for g in FB_GROUP_IDS_RAW.split(",") if g.strip()]

SCRAPE_HOUR = int(os.getenv("SCRAPE_HOUR", "8"))
SCRAPE_MINUTE = int(os.getenv("SCRAPE_MINUTE", "0"))
ICT_TZ = timezone(timedelta(hours=7))
scrape_time = time(hour=SCRAPE_HOUR, minute=SCRAPE_MINUTE, tzinfo=ICT_TZ)

SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.55"))
SCRAPE_DAYS_LIMIT = int(os.getenv("SCRAPE_DAYS_LIMIT", "7"))
SCRAPE_PAGES_LIMIT = int(os.getenv("SCRAPE_PAGES_LIMIT", "3"))

# ===================== B2B MATCHING CONFIG =====================
# Trọng số scoring
MATCH_W_SEMANTIC = float(os.getenv("MATCH_W_SEMANTIC", "0.50"))
MATCH_W_LEXICAL  = float(os.getenv("MATCH_W_LEXICAL",  "0.30"))
MATCH_W_LOCATION = float(os.getenv("MATCH_W_LOCATION",  "0.20"))
MATCH_MIN_SCORE  = float(os.getenv("MATCH_MIN_SCORE",  "0.30"))
MATCH_TOP_N      = int(os.getenv("MATCH_TOP_N", "5"))

# Kênh Discord để duyệt outreach review (mặc định trùng với kênh kết quả matching)
_outreach_channel_id_raw = os.getenv("OUTREACH_REVIEW_CHANNEL_ID", "")
try:
    OUTREACH_REVIEW_CHANNEL_ID = int(_outreach_channel_id_raw) if _outreach_channel_id_raw else DISCORD_CHANNEL_ID
except ValueError:
    OUTREACH_REVIEW_CHANNEL_ID = DISCORD_CHANNEL_ID

# Nguồn dữ liệu doanh nghiệp supplier (Supabase / CSV — cấu hình trong .env)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE_DIR, "Business_dataset.csv")   # chỉ dùng khi SUPPLIER_SOURCE=csv

# Kênh outreach cho nhánh này: kết quả matching bài Facebook → comment vào bài viết
OUTREACH_CHANNEL_FACEBOOK = "facebook_comment"

# ===================== FILE PATHS =====================
POSTS_DB_FILE = os.path.join(BASE_DIR, "fb_matching_posts.json")

# ===================== REFERENCE QUERIES CHO EMBEDDING =====================
PARTNER_QUERIES = [
    # --- Nhóm 1: Tìm nguồn hàng sỉ chung ---
    "cần tìm nguồn hàng sỉ chiết khấu cao",
    "mình đang tìm nguồn sỉ tận gốc giá tốt",
    "ai biết nguồn hàng sỉ nào uy tín không",
    "cần tìm nhà cung cấp sản phẩm sỉ lẻ",
    "tìm đối tác cung ứng hàng hoá lâu dài",
    "muốn tìm nguồn nhập hàng sỉ số lượng lớn",
    "đang tìm supplier phân phối sỉ",
    "cần nhập hàng sỉ số lượng lớn giá cạnh tranh",
    "cần tìm ncc uy tín giá sỉ tốt",
    "mình đang tìm ncc nguồn hàng sỉ sll",
    "muốn hợp tác với các ncc trực tiếp",
    
    # --- Nhóm 2: Tìm xưởng gia công & sản xuất ---
    "cần tìm xưởng gia công theo yêu cầu",
    "tìm xưởng sản xuất OEM ODM",
    "mình cần tìm xưởng sản xuất trực tiếp không qua trung gian",
    "tìm xưởng may gia công quần áo thời trang",
    "cần tìm xưởng may đồng phục công ty số lượng lớn",
    "tìm xưởng mộc gia công nội thất gỗ",
    "cần tìm xưởng in bao bì túi giấy hộp giấy",
    "tìm xưởng gia công cơ khí chính xác",

    # --- Nhóm 3: F&B ---
    "cần tìm nguồn cung cấp nguyên liệu thực phẩm sỉ",
    "tìm nhà cung cấp hải sản tươi sống giá sỉ",
    "cần tìm nguồn cung cấp rau củ quả hữu cơ sạch",
    "đang tìm nhà máy sản xuất nước uống đóng chai đóng lon",
    "cần tìm nguồn sỉ bánh kẹo gia vị đồ ăn vặt",

    # --- Nhóm 4: Mỹ phẩm & Spa ---
    "tìm nguồn mỹ phẩm chính hãng sỉ chiết khấu cao",
    "cần tìm xưởng gia công mỹ phẩm OEM trọn gói",
    "đang tìm nhà cung cấp vật tư tiêu hao cho spa thẩm mỹ viện",
    "tìm nguồn sỉ dầu gội sữa tắm sản phẩm chăm sóc tóc",

    # --- Nhóm 5: Dịch vụ B2B & Công nghệ ---
    "cần tìm đối tác làm dịch vụ kế toán thuế trọn gói",
    "tìm agency chạy quảng cáo marketing online uy tín",
    "cần tìm đơn vị thiết kế website chuẩn SEO chuyên nghiệp",
    "đang tìm đối tác vận chuyển logistics xuất nhập khẩu",
    "cần tìm công ty cung cấp dịch vụ hải quan trọn gói",
    "tìm đơn vị outsource nhân sự cho dự án",

    # --- Nhóm 6: Vật liệu & Điện tử ---
    "cần tìm nhà cung cấp vật liệu xây dựng sắt thép",
    "tìm nguồn sỉ linh kiện điện tử phụ kiện điện thoại",
    "đang tìm nhà cung cấp bao bì hộp carton giá tốt",
    "cần tìm đối tác cung cấp thiết bị y tế vật tư phòng khám",

    # --- Nhóm 7: Tiếng Anh ---
    "looking for suppliers in Vietnam",
    "looking for manufacturing factories for OEM ODM",
    "seeking reliable suppliers and business partners",
    "need to import products from Vietnamese suppliers",
    "looking for logistics and shipping partners",
]

# ===================== BIẾN TOÀN CỤC =====================
embedding_model = None
query_embeddings = None
matching_engine = None  # B2B Matching Engine instance
supplier_source = None  # Nguồn dữ liệu doanh nghiệp (Supabase / CSV)
outreach_engine = OutreachEngine()  # Ginfor Outreach Engine instance


# ===================== NEGATIVE KEYWORDS (DRY) =====================
NEGATIVE_KEYWORDS = [
    # --- Supplier: Chào hàng / Bán sỉ ---
    "chuyên sỉ lẻ", "tuyển sỉ", "tuyển đại lý", "tuyển ctv", "tuyển cộng tác viên",
    "sỉ tận gốc", "sỉ tận xưởng", "xưởng may nhận",
    "bên em chuyên", "nhà e sẵn", "bảng báo giá sỉ", "inbox nhận báo giá",
    "nhận gia công", "bên mình chuyên cung cấp", "chuyên phân phối sỉ lẻ",
    "nhân sự cty", "phiên dịch", "kiêm phiên dịch", "lm hay sẽ làm", "làm hay sẽ làm",
    "cho cty hàn", "cho công ty hàn",
    # --- Tuyển dụng / Việc làm ---
    "tuyển nhân viên", "tuyển gấp nhân viên", "tuyển ctv đăng bài",
    "tuyển nhân sự", "ca tối", "ca sáng", "lương cứng", "lương 25k",
    "tuyển gấp", "tuyển part time", "tuyển fulltime", "việc làm",
    "tuyển dụng", "mô tả công việc", "yêu cầu công việc", "tuyển vị trí",
    "sales admin", "chế độ đãi ngộ",
    # --- Quảng cáo bán lẻ B2C ---
    "freeship", "miễn phí vận chuyển", "combo ưu đãi", "mua ngay",
    "đặt hàng ngay", "đặt hàng liền", "order ngay", "inbox ngay",
    "ưu đãi hôm nay", "giảm giá cực sốc", "sale off", "flash sale",
    "vào bên mình mua", "liên hệ để mua", "liên hệ ngay để nhận",
    "có người dùng phản hồi", "khách hàng phản hồi",
    "gọi điện tư vấn miễn phí", "tư vấn miễn phí",
    "sản phẩm chính hãng 100%", "cam kết chính hãng",
    "ăn là mê", "giòn tan", "thơm bùi",
    # --- MLM / Đa cấp ---
    "phát triển lâu dài với ngành", "tìm người muốn phát triển",
    "không tuyển người chỉ muốn đi làm", "không tuyển người đi làm nhận lương",
    "thu nhập thụ động", "thu nhập khủng", "tự do tài chính",
    "upline", "downline", "hệ thống đa cấp", "kinh doanh đa cấp",
    "mô hình kinh doanh cùng mình", "chia sẻ cơ hội kiếm tiền",
    "khởi nghiệp cùng", "đội nhóm của mình", "đi cùng mình",
    "ngành fitness", "ngành làm đẹp", "ngành beauty",
    # --- Rác ---
    "xin lời khuyên", "cho em xin lời khuyên", "lương cứ lẹt đẹt",
    "em năm nay", "em đang khó khăn", "ai cho em hỏi",
    "hôm nay bạn có dự định gì", "khởi động tuần mới",
    "mô hình này đang hot", "share để mọi người biết",
    "nhượng lại cty", "nhượng lại công ty", "nhượng lại shop",
    "thanh lý tài sản",
    "cần nhượng lại", "sang nhượng",
    "cho thuê mặt bằng", "cho thuê đất", "bán đất", "thuê kho",
    "mặt bằng kinh doanh", "cho thuê kho xưởng",
    "tài khoản sàn", "nạp tiền nhận lãi", "cam kết lãi suất",
    "khóa học tỉnh thức", "chữa lành tâm hồn", "vòng quay năng lượng",
    "tập mới nhất", "xem tại link", "cập nhật link",
]


# ===================== B2B MATCHING ENGINE =====================
def load_matching_engine():
    """Tải B2B Matching Engine (chỉ chạy 1 lần khi khởi động)"""
    global matching_engine, supplier_source
    from matching_engine import B2BMatchingEngine
    from datasource import get_supplier_source

    supplier_source = get_supplier_source()

    logger.info("🏢 Đang tải B2B Matching Engine...")
    logger.info(f"   🗄️  Nguồn dữ liệu: {supplier_source.describe()}")
    logger.info(f"   ⚖️  Weights: semantic={MATCH_W_SEMANTIC}, lexical={MATCH_W_LEXICAL}, location={MATCH_W_LOCATION}")

    matching_engine = B2BMatchingEngine(source=supplier_source)
    matching_engine.load_data()
    matching_engine.build_index()

    logger.info(f"✅ B2B Matching Engine sẵn sàng! {len(matching_engine.companies)} doanh nghiệp đã được index.")


# ===================== MATCH QUEUE (lưu kết quả matching) =====================
# Kết quả matching của cả 2 nhánh được ghi vào chung bảng `buyer_supplier_matches`
# trong b2b_harvester.db, phân biệt bằng outreach_channel:
#   - nhánh này (Facebook group)     → 'facebook_comment'
#   - nhánh B2B e-commerce           → 'email'  (xem ecommerce_matching.py)
_match_db = None


def get_match_db():
    """Lazy-init DatabaseManager của B2B Harvester để ghi hàng đợi outreach."""
    global _match_db
    if _match_db is None:
        harvester_dir = os.path.join(BASE_DIR, "b2b_harvester")
        if harvester_dir not in sys.path:
            sys.path.insert(0, harvester_dir)
        from database import DatabaseManager
        _match_db = DatabaseManager()
    return _match_db


def save_fb_matches(post: dict, matches: list) -> int:
    """
    Ghi kết quả matching của một bài viết Facebook vào hàng đợi outreach.
    Lỗi ghi DB không được làm gián đoạn pipeline quét.
    """
    try:
        db = get_match_db()
    except Exception as e:
        logger.warning(f"⚠️ Không mở được match queue DB: {e}")
        return 0

    post_id = post.get("post_id", "")
    saved = 0
    for rank, result in enumerate(matches, 1):
        company = result["company"]
        breakdown = result["score_breakdown"]
        row = {
            "buyer_id": f"fb:{post_id}",
            "buyer_source": f"facebook_group:{post.get('group_id', '')}",
            "source_type": "facebook_group",
            "outreach_channel": OUTREACH_CHANNEL_FACEBOOK,
            "buyer_title": post.get("text", "")[:200],
            "buyer_query": post.get("text", ""),
            "buyer_url": post.get("url", ""),
            "buyer_email": "",
            "buyer_phone": "",
            "supplier_id": company.get("supplier_id", ""),
            "supplier_name": company.get("name", ""),
            "supplier_email": company.get("email", ""),
            "supplier_phone": company.get("phone", ""),
            "supplier_city": company.get("city", ""),
            "supplier_industry": company.get("main_industry", ""),
            "rank_position": rank,
            "score_total": result["total_score"],
            "score_semantic": round(breakdown["semantic"], 4),
            "score_lexical": round(breakdown["lexical"], 4),
            "score_location": round(breakdown["location"], 4),
        }
        try:
            if db.save_match(row):
                saved += 1
        except Exception as e:
            logger.warning(f"⚠️ Không ghi được match {post_id} × {row['supplier_name']}: {e}")

    if saved:
        logger.info(f"   💾 Đã lưu {saved} cặp match vào hàng đợi comment Facebook")
    return saved


# ===================== VECTOR EMBEDDING MODULE =====================
def load_embedding_model():
    """Tải model Vietnamese SBERT (chỉ chạy 1 lần khi khởi động)"""
    global embedding_model, query_embeddings
    try:
        from sentence_transformers import SentenceTransformer
        logger.info("🧠 Đang tải model Vietnamese SBERT (keepitreal/vietnamese-sbert)...")
        embedding_model = SentenceTransformer('keepitreal/vietnamese-sbert')

        # Pre-encode các reference queries
        query_embeddings = embedding_model.encode(PARTNER_QUERIES, convert_to_tensor=True)
        logger.info(f"✅ Model SBERT đã sẵn sàng! Đã encode {len(PARTNER_QUERIES)} reference queries.")
        return True
    except Exception as e:
        logger.error(f"❌ Không thể tải model SBERT: {e}")
        return False


def check_partner_intent_embedding(text: str) -> tuple[bool, float]:
    """
    Kiểm tra bài viết có ý định tìm nguồn hàng / sản phẩm / dịch vụ (Buyer) không
    bằng Cosine Similarity (SBERT) + Bộ lọc từ khoá phủ định.
    """
    global embedding_model, query_embeddings

    if embedding_model is None or query_embeddings is None:
        return check_partner_intent_keyword(text)

    try:
        text_lower = text.lower()
        for kw in NEGATIVE_KEYWORDS:
            if kw in text_lower:
                logger.info(f"   ❌ Bỏ qua bài viết (từ khóa phủ định): '{kw}'")
                return (False, 0.0)

        from sentence_transformers import util

        post_embedding = embedding_model.encode(text, convert_to_tensor=True)
        cos_scores = util.cos_sim(post_embedding, query_embeddings)[0]
        max_score = float(cos_scores.max())

        is_match = max_score >= SIMILARITY_THRESHOLD
        return (is_match, max_score)
    except Exception as e:
        logger.warning(f"⚠️ Lỗi embedding, fallback sang keyword: {e}")
        return check_partner_intent_keyword(text)


def check_partner_intent_keyword(text: str) -> tuple[bool, float]:
    """Fallback: kiểm tra ý định tìm nguồn hàng bằng keyword matching."""
    text_lower = text.lower()

    for kw in NEGATIVE_KEYWORDS:
        if kw in text_lower:
            return (False, 0.0)

    intent_keywords = [
        "tìm", "cần", "looking for", "need",
        "muốn tìm", "cần tìm", "đang tìm", "ai có", "bên nào",
    ]
    object_keywords = [
        "nhà cung cấp", "nguồn hàng", "đối tác", "partner", "supplier", "ncc",
        "xưởng", "gia công", "cung cấp", "cung ứng", "phân phối",
        "đại lý", "nguồn cung", "nguyên liệu", "nguyên vật liệu",
        "nhà phân phối", "hàng sỉ", "giá sỉ", "sỉ lẻ",
    ]

    has_intent = any(kw in text_lower for kw in intent_keywords)
    has_object = any(kw in text_lower for kw in object_keywords)

    if has_intent and has_object:
        return (True, 0.80)
    elif has_object:
        return (True, 0.60)
    return (False, 0.0)


# ===================== POST ID MANAGEMENT =====================
def load_scraped_posts() -> dict:
    """Tải danh sách post đã quét"""
    if os.path.exists(POSTS_DB_FILE):
        try:
            with open(POSTS_DB_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if "posts" in data:
                if len(data["posts"]) > 2000:
                    data["posts"] = data["posts"][-2000:]
                return data
        except Exception as e:
            logger.warning(f"⚠️ Lỗi đọc file {POSTS_DB_FILE}: {e}. Tạo mới.")

    new_data = {"posts": []}
    save_scraped_posts(new_data)
    return new_data


def save_scraped_posts(data: dict):
    """Lưu danh sách post đã quét"""
    with open(POSTS_DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ===================== FACEBOOK SCRAPER MODULE =====================
def get_facebook_cookies() -> dict:
    """Tạo dict cookies cho facebook-scraper"""
    if not FB_COOKIE_C_USER or not FB_COOKIE_XS:
        logger.error("❌ Thiếu cookies Facebook (FB_COOKIE_C_USER, FB_COOKIE_XS).")
        return None
    return {
        "c_user": FB_COOKIE_C_USER,
        "xs": FB_COOKIE_XS,
    }


def extract_post_id(href: str) -> str | None:
    """Trích xuất post_id từ nhiều định dạng URL của Facebook"""
    match = re.search(r'/posts/(\d+)', href)
    if match:
        return match.group(1)
        
    match2 = re.search(r'story_fbid=(\d+)', href)
    if match2:
        return match2.group(1)
        
    match3 = re.search(r'/permalink/(\d+)', href)
    if match3:
        return match3.group(1)
        
    match4 = re.search(r'/stories/[^/]+/([^/?]+)', href)
    if match4:
        token = match4.group(1)
        try:
            import base64
            padded = token + "=" * ((4 - len(token) % 4) % 4)
            decoded = base64.b64decode(padded).decode('utf-8', errors='ignore')
            num_match = re.search(r':(\d+)', decoded)
            if num_match:
                return num_match.group(1)
        except Exception:
            pass
            
    return None


async def scrape_group_posts(group_id: str, cookies: dict, pages: int = 2) -> list:
    """
    Quét bài viết từ 1 group Facebook bằng Pyppeteer.
    (Giữ nguyên logic gốc từ facebook_scraper_bot.py)
    """
    from bs4 import BeautifulSoup
    from pyppeteer import launch

    posts = []
    executable_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    if not os.path.exists(executable_path):
        executable_path = None

    logger.info(f"   📥 Đang quét group {group_id} bằng Browser Automation...")
    browser = None
    try:
        browser_args = [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--window-size=1280,1000'
        ]
        
        if executable_path:
            browser = await launch(
                executablePath=executable_path,
                headless=True,
                args=browser_args
            )
        else:
            browser = await launch(
                headless=True,
                args=browser_args
            )

        page = await browser.newPage()
        await page.setViewport({'width': 1280, 'height': 1000})
        await page.setUserAgent("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36")

        # Set cookies
        fb_cookies = [
            {'name': 'c_user', 'value': cookies.get('c_user'), 'domain': '.facebook.com'},
            {'name': 'xs', 'value': cookies.get('xs'), 'domain': '.facebook.com'}
        ]
        for cookie in fb_cookies:
            await page.setCookie(cookie)

        url = f"https://www.facebook.com/groups/{group_id}?sorting_setting=CHRONOLOGICAL"
        await page.goto(url, {'waitUntil': 'networkidle2'})
        
        await asyncio.sleep(5)

        for i in range(pages * 3):
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(3)

        content = await page.content()
        soup = BeautifulSoup(content, 'html.parser')
        
        all_links = soup.find_all('a', href=True)
        processed_post_ids = set()

        for link in all_links:
            href = link['href']
            post_id = extract_post_id(href)

            if not post_id or post_id in processed_post_ids:
                continue

            processed_post_ids.add(post_id)
            post_url = f"https://www.facebook.com/groups/{group_id}/posts/{post_id}/"

            parent = link.parent
            message_div = None
            while parent:
                message_div = parent.find(attrs={"data-ad-preview": "message"}) or parent.find(attrs={"data-ad-comet-preview": "message"})
                if message_div:
                    break
                if parent.name == 'body' or parent.get('role') == 'feed':
                    break
                parent = parent.parent

            if not parent or parent.name == 'body':
                parent = link.parent
                for _ in range(12):
                    if parent and parent.parent:
                        parent = parent.parent

            text_content = ""
            if message_div:
                text_content = message_div.get_text(separator="\n").strip()
            else:
                auto_elements = parent.find_all(attrs={"dir": "auto"}) if parent else []
                texts = []
                for elem in auto_elements:
                    parent_names = [p.name for p in elem.parents]
                    if any(h in parent_names for h in ['h2', 'h3', 'h4', 'span']):
                        continue
                    txt = elem.get_text().strip()
                    if txt and len(txt) > 20 and txt not in texts:
                        texts.append(txt)
                text_content = "\n".join(texts)

            if not text_content.strip():
                continue

            posts.append({
                "post_id": post_id,
                "text": text_content,
                "time": None,
                "url": post_url,
                "group_id": group_id,
            })

        logger.info(f"   ✅ Trích xuất thành công {len(posts)} bài viết từ group {group_id}")

    except Exception as e:
        logger.error(f"   ❌ Lỗi cào group {group_id} bằng Browser: {e}")
    finally:
        if browser:
            try:
                await browser.close()
            except Exception:
                pass

    return posts


# ===================== B2B MATCHING OUTPUT =====================
def run_matching(post_text: str, top_n: int = None) -> list:
    """
    Chạy B2B Matching Engine trên một bài viết buyer.
    Returns: list of match result dicts.
    """
    global matching_engine
    if matching_engine is None:
        logger.error("❌ Matching engine chưa được khởi tạo!")
        return []
    
    top_n = top_n or MATCH_TOP_N
    
    results = matching_engine.match(
        query=post_text,
        w_semantic=MATCH_W_SEMANTIC,
        w_lexical=MATCH_W_LEXICAL,
        w_location=MATCH_W_LOCATION,
        min_score=MATCH_MIN_SCORE
    )
    
    return results[:top_n]


async def send_matching_results_to_discord(bot, post: dict, buyer_score: float, matches: list):
    """
    Gửi bài viết buyer + kết quả matching (top DN phù hợp) về Discord.
    
    Flow: 1 embed header (buyer post) + N embed (mỗi DN phù hợp)
    """
    try:
        channel = bot.get_channel(DISCORD_CHANNEL_ID)
        if not channel:
            try:
                channel = await bot.fetch_channel(DISCORD_CHANNEL_ID)
            except Exception as e:
                logger.error(f"❌ Không tìm thấy channel {DISCORD_CHANNEL_ID}: {e}")
                return

        # === EMBED 1: BUYER POST HEADER ===
        text_preview = post["text"][:500]
        if len(post["text"]) > 500:
            text_preview += "..."

        post_url = post.get("url", "")
        group_id = post.get("group_id", "N/A")
        post_time = post.get("time", "N/A")

        # Format thời gian
        time_display = "N/A"
        if post_time and post_time != "N/A":
            try:
                dt = datetime.fromisoformat(post_time)
                time_display = dt.strftime("%d/%m/%Y %H:%M")
            except (ValueError, TypeError):
                time_display = str(post_time)

        buyer_embed = discord.Embed(
            title="🔍 Nhu Cầu Tìm Đối Tác / Nguồn Hàng (Buyer)",
            description=f"```\n{text_preview}\n```",
            color=discord.Color(0x0066FF),
            timestamp=datetime.now()
        )

        if post_url:
            buyer_embed.add_field(name="🔗 Facebook", value=f"[Xem bài viết]({post_url})", inline=True)

        buyer_embed.add_field(name="📊 Buyer Intent", value=f"**{int(buyer_score * 100)}%**", inline=True)
        buyer_embed.add_field(name="👥 Group", value=f"`{group_id}`", inline=True)
        buyer_embed.add_field(name="⏰ Đăng lúc", value=time_display, inline=True)
        buyer_embed.add_field(
            name="🏢 Doanh nghiệp phù hợp",
            value=f"Tìm thấy **{len(matches)}** doanh nghiệp khớp nhu cầu",
            inline=False
        )
        buyer_embed.set_footer(text="ThongtinCty B2B Matching Engine • Powered by SBERT")
        await channel.send(embed=buyer_embed)

        # === EMBED 2+: EACH MATCHED COMPANY ===
        for i, result in enumerate(matches):
            comp = result["company"]
            breakdown = result["score_breakdown"]
            total = result["total_score"]
            pct = int(total * 100)

            # Màu theo score
            if total >= 0.65:
                color = discord.Color.green()
            elif total >= 0.45:
                color = discord.Color.gold()
            else:
                color = discord.Color.orange()

            # Score bars
            sem_bar = "█" * int(breakdown["semantic"] * 10) + "░" * (10 - int(breakdown["semantic"] * 10))
            lex_bar = "█" * int(breakdown["lexical"] * 10) + "░" * (10 - int(breakdown["lexical"] * 10))
            loc_bar = "█" * int(breakdown["location"] * 10) + "░" * (10 - int(breakdown["location"] * 10))

            # Truncate description
            desc = comp.get("description", "")
            if len(desc) > 300:
                desc = desc[:300] + "..."

            comp_embed = discord.Embed(
                title=f"#{i+1} — {comp['name']}",
                description=desc if desc else "*(Chưa có mô tả)*",
                color=color,
                timestamp=datetime.now()
            )

            comp_embed.add_field(name="🎯 Độ Phù Hợp", value=f"**{pct}%**", inline=True)
            comp_embed.add_field(name="🏭 Ngành", value=comp["main_industry"][:50] or "N/A", inline=True)
            comp_embed.add_field(name="📍 Khu vực", value=comp["city"] or "N/A", inline=True)

            comp_embed.add_field(
                name="📊 Chi Tiết Điểm",
                value=(
                    f"```\n"
                    f"Ngữ nghĩa (SBERT): {sem_bar} {int(breakdown['semantic']*100)}%\n"
                    f"Từ khoá (Lexical): {lex_bar} {int(breakdown['lexical']*100)}%\n"
                    f"Vị trí (Location): {loc_bar} {int(breakdown['location']*100)}%\n"
                    f"```"
                ),
                inline=False
            )

            # Thông tin liên hệ
            contact_parts = []
            if comp.get("email"):
                contact_parts.append(f"📧 {comp['email']}")
            if comp.get("phone"):
                contact_parts.append(f"📞 {comp['phone']}")
            if comp.get("mst"):
                contact_parts.append(f"🔑 MST: {comp['mst']}")

            if contact_parts:
                comp_embed.add_field(
                    name="📇 Liên Hệ",
                    value="\n".join(contact_parts),
                    inline=False
                )

            comp_embed.set_footer(text=f"ThongtinCty • Match #{i+1}/{len(matches)}")
            await channel.send(embed=comp_embed)

            # Rate limit protection
            await asyncio.sleep(0.5)

        logger.info(f"   ✅ Đã gửi {len(matches)} kết quả matching cho bài viết {post.get('post_id', 'N/A')} tới Discord")

    except Exception as e:
        logger.error(f"❌ Lỗi gửi matching results tới Discord: {e}")
        import traceback
        traceback.print_exc()


# ===================== CORE SCRAPE + MATCH PIPELINE =====================
async def scrape_and_match_all_groups(bot) -> int:
    """
    Pipeline chính:
    1. Quét tất cả Facebook groups
    2. Lọc bài viết có buyer intent
    3. Chạy matching engine tìm top DN phù hợp
    4. Gửi kết quả về Discord
    
    Returns: Số bài viết đã match thành công
    """
    cookies = get_facebook_cookies()
    if cookies is None:
        return -1

    if not FB_GROUP_IDS:
        logger.error("❌ Chưa cấu hình danh sách group (FB_GROUP_IDS)")
        return -1

    logger.info(f"🔍 Bắt đầu quét {len(FB_GROUP_IDS)} group Facebook...")

    # Gửi thông báo bắt đầu
    channel = bot.get_channel(DISCORD_CHANNEL_ID)
    if not channel:
        try:
            channel = await bot.fetch_channel(DISCORD_CHANNEL_ID)
        except Exception as e:
            logger.error(f"❌ Không tìm thấy channel {DISCORD_CHANNEL_ID}: {e}")

    if channel:
        start_embed = discord.Embed(
            title="🔄 [B2B Matching] Bắt Đầu Quét & Matching",
            description=(
                f"Đang quét **{len(FB_GROUP_IDS)}** groups Facebook,\n"
                f"lọc buyer intent, rồi matching với **{len(matching_engine.companies) if matching_engine else '?'}** doanh nghiệp..."
            ),
            color=discord.Color(0x0066FF),
            timestamp=datetime.now()
        )
        groups_list = "\n".join(f"• [Group {g}](https://facebook.com/groups/{g})" for g in FB_GROUP_IDS[:10])
        if len(FB_GROUP_IDS) > 10:
            groups_list += f"\n... và {len(FB_GROUP_IDS)-10} groups khác"
        start_embed.add_field(name="👥 Groups", value=groups_list, inline=False)
        start_embed.add_field(name="⚖️ Weights", value=f"Semantic={MATCH_W_SEMANTIC} | Lexical={MATCH_W_LEXICAL} | Location={MATCH_W_LOCATION}", inline=False)
        start_embed.set_footer(text="ThongtinCty B2B Matching Engine • Vui lòng đợi...")
        try:
            await channel.send(embed=start_embed)
        except Exception as e:
            logger.error(f"❌ Không thể gửi thông báo bắt đầu: {e}")

    # Load danh sách post đã quét
    posts_data = load_scraped_posts()
    seen_ids = set(posts_data["posts"])

    # Dedup theo content hash
    seen_content_hashes = set()

    total_new = 0
    total_matched = 0
    total_companies_sent = 0

    # Initialize dynamic progress indicator on Discord
    status_msg = None
    if channel:
        try:
            status_msg = await channel.send(f"🔄 **[Tiến độ]** Bắt đầu quét... (0/{len(FB_GROUP_IDS)} nhóm)")
        except Exception as e:
            logger.error(f"❌ Không thể gửi tin nhắn tiến độ: {e}")

    for idx, group_id in enumerate(FB_GROUP_IDS):
        if status_msg:
            try:
                group_url = f"https://facebook.com/groups/{group_id}"
                await status_msg.edit(content=(
                    f"🔄 **[Tiến độ]** Đang quét nhóm **{idx+1}/{len(FB_GROUP_IDS)}**: `{group_id}`\n"
                    f"🔗 Link: [Facebook Group]({group_url})\n"
                    f"📊 Trạng thái: Đã thu thập **{total_new}** bài mới | Tìm thấy **{total_matched}** buyer matches"
                ))
            except Exception as e:
                logger.error(f"❌ Không thể cập nhật tin nhắn tiến độ: {e}")

        try:
            group_posts = await scrape_group_posts(group_id, cookies, SCRAPE_PAGES_LIMIT)

            for post in group_posts:
                pid = post["post_id"]
                if pid in seen_ids:
                    continue

                # Dedup theo nội dung
                content_fingerprint = hashlib.md5(
                    post["text"].strip()[:80].encode("utf-8", errors="ignore")
                ).hexdigest()

                if content_fingerprint in seen_content_hashes:
                    logger.info(f"   🔁 Bỏ qua bài [{pid}]: Nội dung trùng.")
                    seen_ids.add(pid)
                    posts_data["posts"].append(pid)
                    continue

                seen_ids.add(pid)
                seen_content_hashes.add(content_fingerprint)
                posts_data["posts"].append(pid)

                total_new += 1
                text_preview = post["text"][:150].replace("\n", " ")
                logger.info(f"   ⭐ Bài mới [{pid}]: {text_preview}...")

                # Kiểm tra buyer intent
                is_match, buyer_score = await asyncio.to_thread(check_partner_intent_embedding, post["text"])

                if is_match:
                    total_matched += 1
                    logger.info(f"   🎯 BUYER MATCH! Score={buyer_score:.2f}")

                    # === CHẠY B2B MATCHING ENGINE ===
                    matches = await asyncio.to_thread(run_matching, post["text"], MATCH_TOP_N)
                    
                    if matches:
                        logger.info(f"   🏢 Tìm thấy {len(matches)} DN phù hợp. Top: {matches[0]['company']['name']} ({int(matches[0]['total_score']*100)}%)")
                        total_companies_sent += len(matches)

                        # Lưu vào hàng đợi outreach (kênh: comment Facebook)
                        await asyncio.to_thread(save_fb_matches, post, matches)

                        # Gửi kết quả matching về Discord
                        await send_matching_results_to_discord(bot, post, buyer_score, matches)

                        # === CHẠY OUTREACH ENGINE PROTOTYPE ===
                        try:
                            action = outreach_engine.process_match_result(post, matches)
                            await send_outreach_preview(bot, action, outreach_engine, OUTREACH_REVIEW_CHANNEL_ID)
                        except Exception as oe:
                            logger.error(f"❌ Lỗi xử lý outreach: {oe}")
                    else:
                        logger.info(f"   ❌ Không tìm thấy DN nào phù hợp (min_score={MATCH_MIN_SCORE})")
                else:
                    logger.info(f"   ➖ Không phải buyer (score={buyer_score:.2f})")

            # Lưu sau mỗi group
            save_scraped_posts(posts_data)

        except Exception as e:
            logger.error(f"❌ Lỗi xử lý group {group_id}: {e}")
            import traceback
            traceback.print_exc()

    # Dọn dẹp tin nhắn tiến độ tạm thời
    if status_msg:
        try:
            await status_msg.delete()
        except Exception:
            pass

    # Gửi thông báo hoàn tất
    logger.info(f"\n✅ Quét xong! {total_new} bài mới, {total_matched} buyer match, {total_companies_sent} DN đã gửi.\n")

    if channel:
        end_embed = discord.Embed(
            title="✅ [B2B Matching] Hoàn Tất Quét & Matching",
            description="Quá trình quét Facebook, lọc buyer intent và matching doanh nghiệp đã hoàn thành.",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        end_embed.add_field(name="👥 Số nhóm đã quét", value=f"`{len(FB_GROUP_IDS)}` nhóm", inline=True)
        end_embed.add_field(name="📥 Bài viết mới", value=f"`{total_new}` bài", inline=True)
        end_embed.add_field(name="🎯 Buyer intent match", value=f"`{total_matched}` bài", inline=True)
        end_embed.add_field(name="🏢 DN đã gợi ý", value=f"`{total_companies_sent}` DN", inline=True)

        suggested_commands = (
            "• `!match` — Quét & matching ngay lập tức\n"
            "• `!match_test <nhu cầu>` — Test matching với nhu cầu tự nhập\n"
            "• `!match_status` — Xem trạng thái hệ thống\n"
            "• `!match_top <số>` — Điều chỉnh top N kết quả\n"
            "• `!match_threshold <0.0-1.0>` — Điều chỉnh ngưỡng lọc\n"
            "• `!match_help` — Hướng dẫn sử dụng"
        )
        end_embed.add_field(name="🎮 Câu lệnh", value=suggested_commands, inline=False)
        end_embed.set_footer(text="ThongtinCty B2B Matching Engine • Powered by SBERT")

        try:
            await channel.send(embed=end_embed)
        except Exception as e:
            logger.error(f"❌ Không thể gửi thông báo kết thúc: {e}")

    return total_matched


# ===================== DISCORD BOT =====================
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)


@bot.event
async def on_ready():
    logger.info(f"{'='*60}")
    logger.info(f"✅ Bot {bot.user} đã trực tuyến! (B2B Matching Mode)")
    logger.info(f"{'='*60}")
    logger.info(f"📌 Discord Channel: {DISCORD_CHANNEL_ID}")
    logger.info(f"👥 Facebook Groups: {len(FB_GROUP_IDS)} groups")
    logger.info(f"📊 Buyer threshold: {SIMILARITY_THRESHOLD}")
    logger.info(f"🏢 Nguồn dữ liệu DN: {os.getenv('SUPPLIER_SOURCE', 'auto')}")
    logger.info(f"{'='*60}\n")

    # Tải model embedding + matching engine
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, load_embedding_model)
    await loop.run_in_executor(None, load_matching_engine)

    # Gửi thông báo khởi động
    try:
        channel = bot.get_channel(DISCORD_CHANNEL_ID)
        if not channel:
            try:
                channel = await bot.fetch_channel(DISCORD_CHANNEL_ID)
            except Exception:
                channel = None

        if channel:
            embed = discord.Embed(
                title="🤖 B2B Matching Bot Đã Hoạt Động!",
                description=f"✅ Bot **{bot.user}** đã khởi động với B2B Matching Engine",
                color=discord.Color(0x0066FF),
                timestamp=datetime.now()
            )
            n_companies = len(matching_engine.companies) if matching_engine else 0
            embed.add_field(name="🏢 Doanh nghiệp đã index", value=f"`{n_companies}` DN", inline=True)
            embed.add_field(name="👥 Facebook Groups", value=f"`{len(FB_GROUP_IDS)}` groups", inline=True)
            embed.add_field(name="📊 Buyer threshold", value=f"`{SIMILARITY_THRESHOLD}`", inline=True)
            embed.add_field(name="⚖️ Matching weights", value=f"Semantic={MATCH_W_SEMANTIC} | Lexical={MATCH_W_LEXICAL} | Location={MATCH_W_LOCATION}", inline=False)
            embed.add_field(
                name="🎮 Commands",
                value=(
                    "`!match` — Quét & matching ngay\n"
                    "`!match_test <nhu cầu>` — Test matching\n"
                    "`!match_status` — Trạng thái\n"
                    "`!match_help` — Hướng dẫn"
                ),
                inline=False
            )
            embed.set_footer(text="ThongtinCty B2B Matching Engine • Powered by SBERT")
            await channel.send(embed=embed)
    except Exception as e:
        logger.error(f"❌ Lỗi gửi thông báo khởi động: {e}")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    logger.info(f"💬 Nhận tin nhắn từ {message.author} tại kênh {message.channel.name} (ID: {message.channel.id}): '{message.content}'")
    await bot.process_commands(message)

    # Bắt đầu task định kỳ
    if not schedule_scraper.is_running():
        schedule_scraper.start()


@tasks.loop(time=scrape_time)
async def schedule_scraper():
    """Task định kỳ quét & matching"""
    logger.info(f"\n⏰ Đã đến giờ quét định kỳ ({SCRAPE_HOUR:02d}:{SCRAPE_MINUTE:02d})")
    await scrape_and_match_all_groups(bot)


@schedule_scraper.before_loop
async def before_scraper():
    """Đợi bot ready"""
    await bot.wait_until_ready()


# ===================== DISCORD COMMANDS =====================
@bot.command(name='match', help="Quét Facebook Groups & matching doanh nghiệp ngay lập tức")
async def manual_match(ctx):
    """Quét & matching ngay"""
    await ctx.send("⏳ Đang kích hoạt quét Facebook + B2B Matching...")
    result = await scrape_and_match_all_groups(bot)
    if result == -1:
        await ctx.send("❌ Có lỗi. Kiểm tra cookies Facebook và file `.env.bot.facebook`.")


@bot.command(name='match_test', help="Test matching với nhu cầu tự nhập")
async def test_match(ctx, *, query: str = None):
    """Test matching engine với câu query tự nhập, không cần quét Facebook"""
    if not query:
        await ctx.send("⚠️ Vui lòng nhập nhu cầu. Ví dụ: `!match_test Cần tìm xưởng may đồng phục ở HCM`")
        return

    if matching_engine is None:
        await ctx.send("❌ Matching engine chưa sẵn sàng. Vui lòng đợi bot khởi động xong.")
        return

    await ctx.send(f"🔍 Đang matching: *{query[:100]}...*")
    
    matches = run_matching(query, top_n=MATCH_TOP_N)
    
    if not matches:
        await ctx.send(f"❌ Không tìm thấy DN nào phù hợp (min_score={MATCH_MIN_SCORE})")
        return

    # Tạo post giả để dùng lại hàm gửi
    fake_post = {
        "post_id": f"manual_test_{int(datetime.now().timestamp())}",
        "text": query,
        "time": None,
        "url": "https://facebook.com/manual_test_post",
        "group_id": "Manual Test",
    }
    
    # Check buyer score
    _, buyer_score = check_partner_intent_embedding(query)
    
    await send_matching_results_to_discord(bot, fake_post, buyer_score, matches)

    # === CHẠY OUTREACH ENGINE PROTOTYPE ===
    try:
        action = outreach_engine.process_match_result(fake_post, matches)
        await send_outreach_preview(bot, action, outreach_engine, ctx.channel.id)
    except Exception as oe:
        logger.error(f"❌ Lỗi xử lý outreach test: {oe}")


@bot.command(name='match_status', help="Xem trạng thái hệ thống matching")
async def match_status(ctx):
    """Xem trạng thái"""
    posts_data = load_scraped_posts()
    total_seen = len(posts_data.get("posts", []))

    model_status = "✅ Vietnamese SBERT" if embedding_model is not None else "⚠️ Keyword Matching"
    engine_status = f"✅ {len(matching_engine.companies)} DN" if matching_engine else "❌ Chưa sẵn sàng"
    source_status = supplier_source.describe() if supplier_source else "❌ Chưa tải"

    embed = discord.Embed(
        title="🤖 Trạng Thái B2B Matching Bot",
        color=discord.Color(0x0066FF),
        timestamp=datetime.now()
    )
    embed.add_field(name="🧠 SBERT Model", value=model_status, inline=True)
    embed.add_field(name="🏢 Matching Engine", value=engine_status, inline=True)
    embed.add_field(name="🗄️ Nguồn dữ liệu", value=source_status, inline=True)
    embed.add_field(name="👥 Số groups", value=str(len(FB_GROUP_IDS)), inline=True)
    embed.add_field(name="📋 Posts đã quét", value=str(total_seen), inline=True)
    embed.add_field(name="📊 Buyer threshold", value=f"`{SIMILARITY_THRESHOLD}`", inline=True)
    embed.add_field(name="⚖️ Matching weights", value=f"S={MATCH_W_SEMANTIC} L={MATCH_W_LEXICAL} G={MATCH_W_LOCATION}", inline=True)
    embed.add_field(name="🎯 Min match score", value=f"`{MATCH_MIN_SCORE}`", inline=True)
    embed.add_field(name="📊 Top N", value=f"`{MATCH_TOP_N}`", inline=True)

    await ctx.send(embed=embed)


@bot.command(name='match_threshold', help="Điều chỉnh ngưỡng buyer similarity (0.0-1.0)")
async def match_threshold_cmd(ctx, value: float = None):
    """Điều chỉnh ngưỡng buyer similarity"""
    global SIMILARITY_THRESHOLD
    if value is None:
        await ctx.send(f"📊 Ngưỡng hiện tại: `{SIMILARITY_THRESHOLD}`\nDùng `!match_threshold 0.6` để thay đổi.")
        return
    if not (0.0 <= value <= 1.0):
        await ctx.send("⚠️ Giá trị phải trong khoảng `0.0` đến `1.0`.")
        return
    old = SIMILARITY_THRESHOLD
    SIMILARITY_THRESHOLD = value
    await ctx.send(f"✅ Ngưỡng buyer: `{old}` → `{value}`")


@bot.command(name='match_top', help="Điều chỉnh số lượng top N kết quả (1-20)")
async def match_top_cmd(ctx, value: int = None):
    """Điều chỉnh top N"""
    global MATCH_TOP_N
    if value is None:
        await ctx.send(f"📊 Top N hiện tại: `{MATCH_TOP_N}`\nDùng `!match_top 10` để thay đổi.")
        return
    if not (1 <= value <= 20):
        await ctx.send("⚠️ Giá trị phải trong khoảng `1` đến `20`.")
        return
    old = MATCH_TOP_N
    MATCH_TOP_N = value
    await ctx.send(f"✅ Top N: `{old}` → `{value}`")


@bot.command(name='match_reload', help="Tải lại danh sách doanh nghiệp từ Supabase")
async def match_reload_cmd(ctx):
    """Tải lại dữ liệu supplier từ Supabase (không cần restart bot)."""
    if matching_engine is None:
        await ctx.send("❌ Matching engine chưa sẵn sàng.")
        return

    old_count = len(matching_engine.companies)
    msg = await ctx.send(f"🔄 Đang tải lại dữ liệu từ **{supplier_source.describe()}**...")

    try:
        await asyncio.to_thread(matching_engine.reload_data, True)
        new_count = len(matching_engine.companies)
        delta = new_count - old_count
        sign = f"+{delta}" if delta > 0 else str(delta)
        await msg.edit(content=(
            f"✅ Đã tải lại từ **{supplier_source.describe()}**\n"
            f"   `{old_count}` → `{new_count}` doanh nghiệp ({sign})"
        ))
    except Exception as e:
        logger.error(f"❌ Lỗi reload dữ liệu: {e}")
        await msg.edit(content=f"❌ Lỗi tải lại dữ liệu: `{e}`")


@bot.command(name='outreach_status', help="Xem thống kê của hệ thống outreach")
async def outreach_status_cmd(ctx):
    """Xem thống kê Ginfor Outreach"""
    stats = outreach_engine.get_stats()
    embed = discord.Embed(
        title="📨 Thống Kê Ginfor Outreach",
        color=discord.Color.green(),
        timestamp=datetime.now()
    )
    embed.add_field(name="📥 Tổng số đã xử lý", value=f"`{stats['total_processed']}` bài viết", inline=False)
    embed.add_field(name="📱 Ưu tiên SMS", value=f"`{stats['sms_count']}` bài", inline=True)
    embed.add_field(name="📧 Ưu tiên Gmail", value=f"`{stats['gmail_count']}` bài", inline=True)
    embed.add_field(name="💬 Chỉ Comment FB", value=f"`{stats['fb_comment_count']}` bài", inline=True)
    embed.add_field(name="✅ Đã duyệt gửi", value=f"`{stats['approved']}`", inline=True)
    embed.add_field(name="❌ Đã từ chối", value=f"`{stats['rejected']}`", inline=True)
    embed.add_field(name="⏳ Chờ duyệt", value=f"`{outreach_engine.get_pending_count()}`", inline=True)
    
    embed.set_footer(text="Ginfor Outreach Engine")
    await ctx.send(embed=embed)


@bot.command(name='match_help', help="Hướng dẫn sử dụng B2B Matching Bot")
async def match_help_cmd(ctx):
    """Hiển thị hướng dẫn"""
    embed = discord.Embed(
        title="🤖 Hướng Dẫn B2B Matching Bot & Outreach",
        description=(
            "Bot tự động quét Facebook groups, lọc bài viết tìm nguồn hàng/đối tác (buyer intent),\n"
            "matching doanh nghiệp và soạn thảo tin nhắn gửi đối tác qua Gmail/SMS/Facebook."
        ),
        color=discord.Color(0x0066FF),
        timestamp=datetime.now()
    )

    commands_text = (
        "🟢 **`!match`** — Quét Facebook + matching + outreach ngay\n\n"
        "🔵 **`!match_test <nhu cầu>`** — Test matching + preview outreach\n"
        "   *VD: `!match_test Cần tìm xưởng may ở HCM, LH: 0912345678`*\n\n"
        "🟡 **`!match_status`** — Xem trạng thái hệ thống matching\n\n"
        "🔄 **`!match_reload`** — Tải lại danh sách DN từ Supabase\n\n"
        "📧 **`!outreach_status`** — Xem thống kê Ginfor Outreach\n\n"
        "🟠 **`!match_threshold <0.0-1.0>`** — Điều chỉnh ngưỡng buyer\n\n"
        "🟣 **`!match_top <1-20>`** — Số DN gợi ý mỗi bài\n\n"
        "⚪ **`!match_help`** — Hiển thị hướng dẫn này"
    )
    embed.add_field(name="🎮 Commands", value=commands_text, inline=False)

    embed.add_field(
        name="🔄 Pipeline",
        value=(
            "1. 📥 Scrape bài viết từ Facebook groups\n"
            "2. 🧠 Lọc buyer intent bằng SBERT\n"
            "3. 🏢 Matching với cơ sở dữ liệu DN\n"
            "4. 📨 Trích xuất liên hệ & Soạn outreach (Gmail/SMS/Comment)\n"
            "5. 📤 Gửi preview lên Discord để admin phê duyệt"
        ),
        inline=False
    )
    
    embed.set_footer(text="ThongtinCty & Ginfor Outreach • Powered by SBERT")
    await ctx.send(embed=embed)


# ===================== CHẠY BOT =====================
if __name__ == "__main__":
    logger.info("\n🚀 Khởi động Facebook B2B Matching Bot...\n")

    if DISCORD_TOKEN == "YOUR_DISCORD_BOT_TOKEN" or not DISCORD_TOKEN:
        logger.error("❌ Chưa cấu hình DISCORD_TOKEN!")
        exit(1)

    if not FB_COOKIE_C_USER or not FB_COOKIE_XS:
        logger.warning("⚠️ Chưa cấu hình Facebook Cookies.")

    # Kiểm tra nguồn dữ liệu supplier trước khi khởi động bot
    from datasource.config import source_kind, supabase_url, supabase_key, supplier_table

    if source_kind() == "supabase":
        if not supabase_url() or not supabase_key():
            logger.error("❌ SUPPLIER_SOURCE=supabase nhưng thiếu SUPABASE_URL / SUPABASE_KEY trong .env")
            exit(1)
        logger.info(f"🗄️  Nguồn dữ liệu supplier: Supabase — bảng '{supplier_table()}'")
    else:
        if not os.path.exists(CSV_PATH):
            logger.error(f"❌ Không tìm thấy Business_dataset.csv tại: {CSV_PATH}")
            exit(1)
        logger.info(f"📄 Nguồn dữ liệu supplier: CSV — {CSV_PATH}")

    bot.run(DISCORD_TOKEN)
