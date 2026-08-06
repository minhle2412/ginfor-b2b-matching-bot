# -*- coding: utf-8 -*-
"""
CLI kiểm tra và quản lý bộ dịch.
==================================
    python -m translation.cli "Looking for white rice suppliers"
    python -m translation.cli --buyers 5        # dịch thử 5 bài đăng buyer thật
    python -m translation.cli --stats           # thống kê cache
    python -m translation.cli --clear-cache     # xoá toàn bộ cache dịch
    python -m translation.cli --backend glossary "broken rice 5%"
"""

import argparse
import logging
import os
import sqlite3
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from .backends import get_backend                                  # noqa: E402
from .detect import detect_language                                # noqa: E402
from .glossary import find_terms                                   # noqa: E402
from .service import Translator, TranslationCache                  # noqa: E402


def show_stats():
    cache = TranslationCache()
    stats = cache.stats()
    print("=" * 66)
    print("CACHE DỊCH")
    print("=" * 66)
    print(f"  File      : {stats['db_path']}")
    print(f"  Tổng bản dịch: {stats['total']:,}")
    for backend, n in (stats["by_backend"] or {}).items():
        print(f"    • {backend:<12} {n:,}")

    if stats["total"]:
        conn = sqlite3.connect(stats["db_path"])
        conn.row_factory = sqlite3.Row
        print("\n  3 bản dịch gần nhất:")
        for r in conn.execute(
            "SELECT source_text, translated, backend FROM translations "
            "ORDER BY created_at DESC LIMIT 3"
        ):
            print(f"    [{r['backend']}] EN: {r['source_text'][:70]}")
            print(f"                VI: {r['translated'][:70]}\n")
        conn.close()
    print("=" * 66)


def clear_cache():
    cache = TranslationCache()
    conn = sqlite3.connect(cache.db_path)
    n = conn.execute("SELECT COUNT(*) FROM translations").fetchone()[0]
    conn.execute("DELETE FROM translations")
    conn.commit()
    conn.close()
    print(f"✅ Đã xoá {n:,} bản dịch khỏi cache ({cache.db_path})")


def translate_buyers(translator, limit):
    """Dịch thử các bài đăng buyer thật trong b2b_harvester.db."""
    db_path = os.path.join(BASE_DIR, "b2b_harvester", "b2b_harvester.db")
    if not os.path.exists(db_path):
        print(f"❌ Không tìm thấy database: {db_path}")
        return 1

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute(
        "SELECT title, description, category, source_platform FROM buyers LIMIT ?", (limit,)
    )]
    conn.close()

    if not rows:
        print("❌ Chưa có bài đăng buyer nào trong database.")
        return 1

    titles = translator.translate_many([r["title"] or "" for r in rows])
    descs = translator.translate_many([r["description"] or "" for r in rows])

    for i, (row, title_vi, desc_vi) in enumerate(zip(rows, titles, descs), 1):
        print(f"\n{'=' * 66}")
        print(f"#{i} [{row['source_platform']}]  (ngôn ngữ gốc: {detect_language(row['title'] or '')})")
        print(f"{'=' * 66}")
        print(f"  EN  {row['title']}")
        print(f"  VI  {title_vi}")
        terms = find_terms(row["title"] or "")
        if terms:
            print(f"  Thuật ngữ B2B nhận ra: {', '.join(terms)}")
        if row["description"]:
            print(f"\n  EN  {row['description'][:220].strip()}...")
            print(f"\n  VI  {desc_vi[:320].strip()}...")

    print(f"\n{translator.get_stats()}")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="Kiểm tra bộ dịch bài đăng buyer Anh → Việt.")
    parser.add_argument("text", nargs="*", help="Văn bản cần dịch")
    parser.add_argument("--buyers", type=int, metavar="N",
                        help="Dịch thử N bài đăng buyer thật trong database")
    parser.add_argument("--backend", choices=["nmt", "glossary"], help="Ép dùng backend cụ thể")
    parser.add_argument("--model", help="Tên model NMT (mặc định Helsinki-NLP/opus-mt-en-vi)")
    parser.add_argument("--stats", action="store_true", help="Xem thống kê cache dịch")
    parser.add_argument("--clear-cache", action="store_true", help="Xoá toàn bộ cache dịch")
    parser.add_argument("--no-cache", action="store_true", help="Bỏ qua cache, luôn dịch lại")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    for noisy in ("httpx", "urllib3", "filelock", "transformers"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    if args.stats:
        show_stats()
        return 0
    if args.clear_cache:
        clear_cache()
        return 0

    if args.model:
        os.environ["TRANSLATION_MODEL"] = args.model

    backend = get_backend(args.backend) if args.backend else None
    cache = TranslationCache(":memory:") if args.no_cache else None
    translator = Translator(backend=backend, cache=cache)

    if args.buyers:
        return translate_buyers(translator, args.buyers)

    if not args.text:
        parser.print_help()
        return 1

    text = " ".join(args.text)
    print(f"Ngôn ngữ phát hiện : {detect_language(text)}")
    terms = find_terms(text)
    if terms:
        print(f"Thuật ngữ B2B      : {', '.join(terms)}")
    print(f"\nEN  {text}")
    print(f"VI  {translator.translate(text)}")
    print(f"\n{translator.get_stats()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
