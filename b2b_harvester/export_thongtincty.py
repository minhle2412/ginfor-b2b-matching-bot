"""
Export Utility for thongtincty.com Integration
Exports 2 core datasets from SQLite database:
1. buyers (Global Buyer Leads / Bài đăng nhu cầu người mua)
2. suppliers_vietnam (Vietnamese Enterprise Directory / Thông tin doanh nghiệp supplier)

Exports to BOTH JSON and CSV formats for maximum integration flexibility.
"""

import json
import csv
import argparse
import logging
from pathlib import Path
from database import DatabaseManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("b2b_harvester.export")

def export_buyers(db, json_path, csv_path):
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM buyers ORDER BY created_at DESC")
    rows = cursor.fetchall()
    
    data = [dict(row) for row in rows]
    if not data:
        logger.warning("No buyer records found.")
        return

    # Parse vector_embedding string to JSON list for JSON output
    json_data = []
    for item in data:
        item_copy = item.copy()
        if item_copy.get("vector_embedding"):
            try:
                item_copy["vector_embedding"] = json.loads(item_copy["vector_embedding"])
            except:
                pass
        json_data.append(item_copy)

    # 1. Export JSON
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)
    logger.info(f"✅ Exported {len(data)} buyer records to JSON: {json_path}")

    # 2. Export CSV
    fields = list(data[0].keys())
    with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(data)
    logger.info(f"✅ Exported {len(data)} buyer records to CSV: {csv_path}")

def export_suppliers(db, json_path, csv_path):
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM suppliers_vietnam ORDER BY created_at DESC")
    rows = cursor.fetchall()
    
    data = [dict(row) for row in rows]
    if not data:
        logger.warning("No supplier records found in database.")
        return

    # Parse vector_embedding string to JSON list for JSON output
    json_data = []
    for item in data:
        item_copy = item.copy()
        if item_copy.get("vector_embedding"):
            try:
                item_copy["vector_embedding"] = json.loads(item_copy["vector_embedding"])
            except:
                pass
        json_data.append(item_copy)

    # 1. Export JSON
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)
    logger.info(f"✅ Exported {len(data)} Vietnam supplier records to JSON: {json_path}")

    # 2. Export CSV
    fields = list(data[0].keys())
    with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(data)
    logger.info(f"✅ Exported {len(data)} Vietnam supplier records to CSV: {csv_path}")

def export_supplier_posts(db, json_path, csv_path):
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM supplier_posts ORDER BY created_at DESC")
    rows = cursor.fetchall()
    
    data = [dict(row) for row in rows]
    if not data:
        logger.warning("No supplier posts found in database.")
        return

    json_data = []
    for item in data:
        item_copy = item.copy()
        if item_copy.get("vector_embedding"):
            try:
                item_copy["vector_embedding"] = json.loads(item_copy["vector_embedding"])
            except:
                pass
        json_data.append(item_copy)

    # 1. Export JSON
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)
    logger.info(f"✅ Exported {len(data)} supplier post records to JSON: {json_path}")

    # 2. Export CSV
    fields = list(data[0].keys())
    with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(data)
    logger.info(f"✅ Exported {len(data)} supplier post records to CSV: {csv_path}")

def main():
    parser = argparse.ArgumentParser(description="Export B2B Harvester Data for thongtincty.com")
    parser.add_argument("--buyers-json", default="buyers_thongtincty.json", help="Output path for buyers JSON")
    parser.add_argument("--buyers-csv", default="buyers_thongtincty.csv", help="Output path for buyers CSV")
    parser.add_argument("--suppliers-json", default="suppliers_vietnam_thongtincty.json", help="Output path for suppliers JSON")
    parser.add_argument("--suppliers-csv", default="suppliers_vietnam_thongtincty.csv", help="Output path for suppliers CSV")
    parser.add_argument("--export-posts", action="store_true", help="Export legacy supplier sell posts if present")
    args = parser.parse_args()

    db = DatabaseManager()
    export_buyers(db, args.buyers_json, args.buyers_csv)
    export_suppliers(db, args.suppliers_json, args.suppliers_csv)
    if args.export_posts:
        export_supplier_posts(db, "supplier_posts_thongtincty.json", "supplier_posts_thongtincty.csv")

if __name__ == "__main__":
    main()

