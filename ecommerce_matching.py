# -*- coding: utf-8 -*-
"""
B2B E-commerce Matching Pipeline
==================================
Nhánh thứ hai của hệ thống (song song với bot Facebook):

    Bài đăng buyer trên các trang xúc tiến thương mại (TradeWheel, EC21,
    GlobalSources, Go4WorldBusiness — đã được B2B Harvester thu thập vào
    b2b_harvester.db)
        → matching với doanh nghiệp supplier lấy từ Supabase
        → ghi kết quả vào hàng đợi `buyer_supplier_matches`
           với outreach_channel = 'email'

Bước gửi email marketing đọc hàng đợi này (sẽ triển khai sau).
Nhánh Facebook group dùng cùng bảng nhưng outreach_channel = 'facebook_comment'.

Cách chạy
---------
    python ecommerce_matching.py                    # match toàn bộ buyer chưa xử lý
    python ecommerce_matching.py --limit 20         # chỉ 20 buyer mới nhất
    python ecommerce_matching.py --source tradewheel
    python ecommerce_matching.py --all              # match lại cả buyer đã xử lý
    python ecommerce_matching.py --min-score 0.35 --top-n 5
    python ecommerce_matching.py --export matches.csv
    python ecommerce_matching.py --stats            # chỉ xem thống kê hàng đợi
"""

import argparse
import csv
import logging
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
sys.path.insert(0, os.path.join(BASE_DIR, "b2b_harvester"))

from datasource import get_supplier_source                    # noqa: E402
from datasource.config import load_env                        # noqa: E402
from matching_engine import B2BMatchingEngine                 # noqa: E402
from translation import get_translator                        # noqa: E402
from translation.service import is_translation_enabled        # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("ecommerce_matching")

#: Nhánh này luôn tiếp cận buyer bằng email marketing
OUTREACH_CHANNEL = "email"
SOURCE_TYPE = "b2b_ecommerce"


def build_buyer_query(buyer: dict, translator=None) -> str:
    """
    Ghép các trường của bài đăng buyer thành một câu truy vấn cho Matching Engine.
    Ưu tiên title + description vì đó là phần mô tả nhu cầu thực.

    Bài đăng trên các trang B2B e-commerce viết bằng tiếng Anh, trong khi mô tả
    doanh nghiệp trong Supabase là tiếng Việt và model SBERT là model đơn ngữ
    tiếng Việt. Nếu có `translator`, các trường nội dung được dịch sang tiếng
    Việt trước khi ghép — hai đầu về cùng ngôn ngữ thì điểm ngữ nghĩa mới có ý
    nghĩa. Bài đã là tiếng Việt sẽ được giữ nguyên (translator tự nhận biết).

    Args:
        buyer: dict một dòng trong bảng `buyers`
        translator: Translator, hoặc None để dùng nguyên văn bản gốc

    Returns:
        Câu truy vấn đã sẵn sàng đưa vào Matching Engine
    """
    content = [
        buyer.get("title") or "",
        buyer.get("description") or "",
        buyer.get("category") or "",
    ]

    if translator is not None:
        content = translator.translate_many(content)

    parts = list(content)
    quantity = buyer.get("quantity")
    if quantity:
        parts.append(f"Số lượng: {quantity}")
    country = buyer.get("buyer_country")
    if country:
        parts.append(f"Thị trường: {country}")

    return " ".join(p.strip() for p in parts if p and p.strip())


def match_buyers(
    db,
    engine,
    limit=None,
    only_unmatched=True,
    source_platform=None,
    top_n=5,
    min_score=0.30,
    w_semantic=0.50,
    w_lexical=0.30,
    w_location=0.20,
    translator=None,
) -> list[dict]:
    """
    Chạy matching cho các bài đăng buyer và ghi kết quả vào hàng đợi outreach.

    Returns:
        list các dòng match đã ghi (dùng để export CSV / in báo cáo)
    """
    buyers = db.get_buyers(limit=limit, only_unmatched=only_unmatched, source_platform=source_platform)
    if not buyers:
        logger.warning("Không có bài đăng buyer nào cần matching.")
        return []

    logger.info(f"🔍 Bắt đầu matching {len(buyers)} bài đăng buyer với {len(engine.companies)} doanh nghiệp...")

    # Dịch trước toàn bộ bài đăng trong một lô. Gọi model một lần cho tất cả
    # đoạn văn nhanh hơn nhiều so với dịch lẻ từng bài trong vòng lặp.
    if translator is not None:
        logger.info("🌐 Dịch trước nội dung bài đăng sang tiếng Việt...")
        fields = []
        for b in buyers:
            fields.extend([b.get("title") or "", b.get("description") or "", b.get("category") or ""])
        translated = translator.translate_many(fields)
        for idx, b in enumerate(buyers):
            b["title_vi"], b["description_vi"], b["category_vi"] = translated[idx * 3: idx * 3 + 3]
        logger.info(f"   {translator.get_stats()}")

    saved_rows = []
    buyers_with_match = 0

    for i, buyer in enumerate(buyers, 1):
        # Dùng bản đã dịch nếu có, ngược lại dùng nguyên bản
        query_source = {
            **buyer,
            "title": buyer.get("title_vi", buyer.get("title")),
            "description": buyer.get("description_vi", buyer.get("description")),
            "category": buyer.get("category_vi", buyer.get("category")),
        }
        query = build_buyer_query(query_source)
        if not query:
            logger.info(f"[{i}/{len(buyers)}] Bỏ qua buyer {buyer['buyer_id']}: không có nội dung.")
            continue

        logger.info(f"[{i}/{len(buyers)}] {buyer.get('source_platform')} — {(buyer.get('title') or '')[:70]}")

        try:
            results = engine.match(
                query=query,
                w_semantic=w_semantic,
                w_lexical=w_lexical,
                w_location=w_location,
                min_score=min_score,
            )[:top_n]
        except Exception as e:
            logger.error(f"   ❌ Lỗi matching buyer {buyer['buyer_id']}: {e}")
            continue

        if not results:
            logger.info(f"   ➖ Không có DN nào đạt ngưỡng {min_score}")
            continue

        buyers_with_match += 1
        logger.info(
            f"   ✅ {len(results)} DN phù hợp | Top: {results[0]['company']['name']} "
            f"({int(results[0]['total_score'] * 100)}%)"
        )

        for rank, result in enumerate(results, 1):
            company = result["company"]
            breakdown = result["score_breakdown"]

            row = {
                "buyer_id": buyer["buyer_id"],
                "buyer_source": buyer.get("source_platform", ""),
                "source_type": SOURCE_TYPE,
                "outreach_channel": OUTREACH_CHANNEL,
                "buyer_title": buyer.get("title", ""),
                "buyer_query": query,
                "buyer_url": buyer.get("detail_url", ""),
                "buyer_email": buyer.get("contact_email") or "",
                "buyer_phone": buyer.get("contact_phone") or "",
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

            if db.save_match(row):
                saved_rows.append(row)

    logger.info(
        f"\n✅ Hoàn tất: {buyers_with_match}/{len(buyers)} buyer có kết quả, "
        f"{len(saved_rows)} cặp match đã vào hàng đợi email."
    )
    return saved_rows


def export_csv(rows: list[dict], path: str):
    """Xuất kết quả matching ra CSV để rà soát thủ công."""
    if not rows:
        logger.warning("Không có dữ liệu để export.")
        return
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    logger.info(f"📄 Đã export {len(rows)} dòng ra {path}")


def print_stats(db):
    """In thống kê hàng đợi outreach."""
    stats = db.get_stats()
    print("\n" + "=" * 64)
    print("THỐNG KÊ B2B HARVESTER DATABASE")
    print("=" * 64)
    print(f"  Bài đăng buyer          : {stats['buyers_total']}")
    print(f"  Supplier (đã scrape)    : {stats['suppliers_vietnam_total']}")
    print(f"  Bài đăng supplier       : {stats['supplier_posts_total']}")
    print(f"  Cặp matching đã tạo     : {stats['matches_total']}")

    match_stats = db.get_match_stats()
    if match_stats:
        print("\n  Hàng đợi outreach:")
        for row in match_stats:
            print(
                f"    • {row['outreach_channel']:<18} {row['outreach_status']:<10} "
                f"{row['n']:>6} cặp / {row['buyers']:>4} buyer"
            )
    print("=" * 64 + "\n")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Matching bài đăng buyer từ các trang B2B e-commerce với supplier trên Supabase."
    )
    parser.add_argument("--limit", type=int, help="Số bài đăng buyer tối đa cần xử lý")
    parser.add_argument("--all", action="store_true", help="Match lại cả buyer đã có kết quả trước đó")
    parser.add_argument("--source", help="Chỉ xử lý buyer của một nền tảng (tradewheel, ec21, ...)")
    parser.add_argument("--top-n", type=int, default=5, help="Số DN gợi ý mỗi buyer (mặc định 5)")
    parser.add_argument("--min-score", type=float, default=0.30, help="Ngưỡng điểm tối thiểu (mặc định 0.30)")
    parser.add_argument("--w-semantic", type=float, default=0.50)
    parser.add_argument("--w-lexical", type=float, default=0.30)
    parser.add_argument("--w-location", type=float, default=0.20)
    parser.add_argument("--export", help="Đường dẫn file CSV để xuất kết quả")
    parser.add_argument("--stats", action="store_true", help="Chỉ in thống kê rồi thoát")
    parser.add_argument("--env", help="Đường dẫn file .env cụ thể")
    parser.add_argument("--no-translate", action="store_true",
                        help="Không dịch bài đăng sang tiếng Việt (dùng nguyên bản tiếng Anh)")
    args = parser.parse_args(argv)

    load_env(args.env, override=bool(args.env))

    from database import DatabaseManager
    db = DatabaseManager()

    if args.stats:
        print_stats(db)
        return 0

    # Bài đăng trên các trang B2B e-commerce viết bằng tiếng Anh, cần dịch sang
    # tiếng Việt trước khi matching (xem package `translation`).
    translator = None
    if not args.no_translate and is_translation_enabled():
        translator = get_translator()
        logger.info(f"🌐 Bộ dịch: {translator.backend.name}")
    else:
        logger.warning("⚠️ Đã TẮT dịch bài đăng — điểm ngữ nghĩa với bài tiếng Anh sẽ rất thấp.")

    source = get_supplier_source()
    logger.info(f"🗄️  Nguồn dữ liệu supplier: {source.describe()}")

    engine = B2BMatchingEngine(source=source)
    engine.load_data()
    engine.build_index()

    rows = match_buyers(
        db,
        engine,
        limit=args.limit,
        only_unmatched=not args.all,
        source_platform=args.source,
        top_n=args.top_n,
        min_score=args.min_score,
        w_semantic=args.w_semantic,
        w_lexical=args.w_lexical,
        w_location=args.w_location,
        translator=translator,
    )

    if args.export:
        export_csv(rows, args.export)

    print_stats(db)
    return 0


if __name__ == "__main__":
    sys.exit(main())
