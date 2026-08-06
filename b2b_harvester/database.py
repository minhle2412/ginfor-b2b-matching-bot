"""
Database Manager for B2B Harvester
Manages SQLite storage for:
1. buyers (Global Buyer Leads)
2. suppliers_vietnam (Vietnamese Exporting Enterprise Directory)
3. supplier_posts (Vietnamese Supplier Product Sell Offers / Bài đăng bán hàng)

Tailored for direct integration into thongtincty.com and Leader reporting.
"""

import sqlite3
import json
import logging
import hashlib
from datetime import datetime
from config import DB_PATH

logger = logging.getLogger("b2b_harvester.database")

class DatabaseManager:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self.init_db()

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        """Initializes database schema if tables do not exist."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Table 1: buyers (Global Buyer Leads / Buy RFQs)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS buyers (
                buyer_id TEXT PRIMARY KEY,
                source_platform TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                category TEXT,
                buyer_name TEXT,
                buyer_country TEXT,
                quantity TEXT,
                destination_port TEXT,
                payment_terms TEXT,
                posted_date TEXT,
                contact_email TEXT,
                contact_phone TEXT,
                detail_url TEXT NOT NULL,
                vector_embedding TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Upgrade schema if contact_email or contact_phone columns missing
        cursor.execute("PRAGMA table_info(buyers)")
        cols = [row[1] for row in cursor.fetchall()]
        if "contact_email" not in cols:
            cursor.execute("ALTER TABLE buyers ADD COLUMN contact_email TEXT")
        if "contact_phone" not in cols:
            cursor.execute("ALTER TABLE buyers ADD COLUMN contact_phone TEXT")

        # Table 2: suppliers_vietnam (Vietnamese Exporting Supplier Directory)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS suppliers_vietnam (
                supplier_id TEXT PRIMARY KEY,
                source_platform TEXT NOT NULL,
                company_name TEXT NOT NULL,
                mst_tax_code TEXT,
                country TEXT DEFAULT 'Vietnam',
                province_city TEXT,
                address TEXT,
                main_products TEXT,
                export_markets TEXT,
                moq_capacity TEXT,
                certifications TEXT,
                contact_phone TEXT,
                contact_email TEXT,
                website TEXT,
                detail_url TEXT NOT NULL,
                vector_embedding TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Table 3: supplier_posts (Vietnamese Supplier Product Sell Offers / Bài đăng bán hàng xuất khẩu)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS supplier_posts (
                post_id TEXT PRIMARY KEY,
                source_platform TEXT NOT NULL,
                company_name TEXT NOT NULL,
                product_title TEXT NOT NULL,
                description TEXT,
                category TEXT,
                moq_price TEXT,
                country TEXT DEFAULT 'Vietnam',
                contact_info TEXT,
                detail_url TEXT NOT NULL,
                vector_embedding TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Table 4: buyer_supplier_matches (Hàng đợi kết quả matching chờ outreach)
        # Mỗi dòng = 1 cặp (bài đăng buyer × doanh nghiệp supplier phù hợp).
        # outreach_channel quyết định kênh tiếp cận:
        #   - 'facebook_comment' : buyer đến từ Facebook group  → comment vào bài viết
        #   - 'email'            : buyer đến từ trang B2B e-commerce → gửi email marketing
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS buyer_supplier_matches (
                match_id TEXT PRIMARY KEY,
                buyer_id TEXT NOT NULL,
                buyer_source TEXT NOT NULL,
                source_type TEXT NOT NULL,
                outreach_channel TEXT NOT NULL,
                buyer_title TEXT,
                buyer_query TEXT,
                buyer_url TEXT,
                buyer_email TEXT,
                buyer_phone TEXT,
                supplier_id TEXT,
                supplier_name TEXT,
                supplier_email TEXT,
                supplier_phone TEXT,
                supplier_city TEXT,
                supplier_industry TEXT,
                rank_position INTEGER,
                score_total REAL,
                score_semantic REAL,
                score_lexical REAL,
                score_location REAL,
                outreach_status TEXT DEFAULT 'pending',
                outreach_sent_at TIMESTAMP,
                outreach_error TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_matches_pending
            ON buyer_supplier_matches (outreach_channel, outreach_status)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_matches_buyer
            ON buyer_supplier_matches (buyer_id, score_total DESC)
        ''')

        conn.commit()
        conn.close()
        logger.info(f"Database initialized at {self.db_path}")

    @staticmethod
    def generate_id(source_platform, detail_url):
        """Generates deterministic MD5 ID based on source platform and detail URL."""
        raw = f"{source_platform}:{detail_url}".strip().lower()
        return hashlib.md5(raw.encode('utf-8')).hexdigest()

    def save_buyer(self, item):
        """Saves a buyer record to database."""
        buyer_id = self.generate_id(item.get("source_platform"), item.get("detail_url"))
        conn = self.get_connection()
        cursor = conn.cursor()
        embedding_str = json.dumps(item.get("vector_embedding")) if item.get("vector_embedding") is not None else None

        try:
            cursor.execute('''
                INSERT INTO buyers (
                    buyer_id, source_platform, title, description, category,
                    buyer_name, buyer_country, quantity, destination_port,
                    payment_terms, posted_date, contact_email, contact_phone,
                    detail_url, vector_embedding
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(buyer_id) DO UPDATE SET
                    title = excluded.title,
                    description = excluded.description,
                    contact_email = COALESCE(NULLIF(excluded.contact_email, ''), buyers.contact_email),
                    contact_phone = COALESCE(NULLIF(excluded.contact_phone, ''), buyers.contact_phone),
                    posted_date = excluded.posted_date
            ''', (
                buyer_id,
                item.get("source_platform", "unknown"),
                item.get("title", ""),
                item.get("description", ""),
                item.get("category", ""),
                item.get("buyer_name", ""),
                item.get("buyer_country", ""),
                item.get("quantity", ""),
                item.get("destination_port", ""),
                item.get("payment_terms", ""),
                item.get("posted_date", ""),
                item.get("contact_email", ""),
                item.get("contact_phone", ""),
                item.get("detail_url", ""),
                embedding_str
            ))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error saving buyer {buyer_id}: {e}")
            return False
        finally:
            conn.close()

    def save_supplier(self, item):
        """Saves a Vietnamese supplier record to database."""
        supplier_id = self.generate_id(item.get("source_platform"), item.get("detail_url"))
        conn = self.get_connection()
        cursor = conn.cursor()
        embedding_str = json.dumps(item.get("vector_embedding")) if item.get("vector_embedding") is not None else None

        try:
            cursor.execute('''
                INSERT INTO suppliers_vietnam (
                    supplier_id, source_platform, company_name, mst_tax_code,
                    country, province_city, address, main_products, export_markets,
                    moq_capacity, certifications, contact_phone, contact_email,
                    website, detail_url, vector_embedding
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(supplier_id) DO UPDATE SET
                    company_name = excluded.company_name,
                    main_products = excluded.main_products,
                    address = excluded.address
            ''', (
                supplier_id,
                item.get("source_platform", "unknown"),
                item.get("company_name", ""),
                item.get("mst_tax_code", ""),
                item.get("country", "Vietnam"),
                item.get("province_city", ""),
                item.get("address", ""),
                item.get("main_products", ""),
                item.get("export_markets", ""),
                item.get("moq_capacity", ""),
                item.get("certifications", ""),
                item.get("contact_phone", ""),
                item.get("contact_email", ""),
                item.get("website", ""),
                item.get("detail_url", ""),
                embedding_str
            ))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error saving supplier {supplier_id}: {e}")
            return False
        finally:
            conn.close()

    def save_supplier_post(self, item):
        """Saves a Vietnamese Supplier Product Sell Offer / Bài đăng bán hàng to database."""
        post_id = self.generate_id(item.get("source_platform"), item.get("detail_url"))
        conn = self.get_connection()
        cursor = conn.cursor()
        embedding_str = json.dumps(item.get("vector_embedding")) if item.get("vector_embedding") is not None else None

        try:
            cursor.execute('''
                INSERT INTO supplier_posts (
                    post_id, source_platform, company_name, product_title,
                    description, category, moq_price, country, contact_info,
                    detail_url, vector_embedding
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(post_id) DO UPDATE SET
                    product_title = excluded.product_title,
                    description = excluded.description,
                    moq_price = excluded.moq_price
            ''', (
                post_id,
                item.get("source_platform", "unknown"),
                item.get("company_name", ""),
                item.get("product_title", ""),
                item.get("description", ""),
                item.get("category", ""),
                item.get("moq_price", ""),
                item.get("country", "Vietnam"),
                item.get("contact_info", ""),
                item.get("detail_url", ""),
                embedding_str
            ))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error saving supplier post {post_id}: {e}")
            return False
        finally:
            conn.close()

    # ==================================================================
    # BUYER × SUPPLIER MATCHES (hàng đợi outreach)
    # ==================================================================
    def get_buyers(self, limit=None, only_unmatched=False, source_platform=None):
        """
        Lấy danh sách bài đăng buyer để đưa vào matching.

        Args:
            limit: giới hạn số bài (None = tất cả)
            only_unmatched: chỉ lấy buyer chưa từng có kết quả matching
            source_platform: lọc theo nền tảng nguồn (tradewheel, ec21, ...)
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        sql = """
            SELECT buyer_id, source_platform, title, description, category,
                   buyer_name, buyer_country, quantity, detail_url,
                   contact_email, contact_phone, posted_date
            FROM buyers
        """
        conditions, params = [], []
        if only_unmatched:
            conditions.append(
                "buyer_id NOT IN (SELECT DISTINCT buyer_id FROM buyer_supplier_matches)"
            )
        if source_platform:
            conditions.append("source_platform = ?")
            params.append(source_platform)
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += " ORDER BY created_at DESC"
        if limit:
            sql += f" LIMIT {int(limit)}"

        rows = cursor.execute(sql, params).fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def save_match(self, item):
        """
        Lưu 1 cặp matching (buyer × supplier) vào hàng đợi outreach.
        Chạy lại matching cho cùng cặp sẽ cập nhật điểm, KHÔNG tạo bản ghi trùng
        và không reset trạng thái outreach đã gửi.
        """
        match_id = hashlib.md5(
            f"{item.get('buyer_id')}:{item.get('supplier_id')}".encode("utf-8")
        ).hexdigest()

        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO buyer_supplier_matches (
                    match_id, buyer_id, buyer_source, source_type, outreach_channel,
                    buyer_title, buyer_query, buyer_url, buyer_email, buyer_phone,
                    supplier_id, supplier_name, supplier_email, supplier_phone,
                    supplier_city, supplier_industry, rank_position,
                    score_total, score_semantic, score_lexical, score_location
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(match_id) DO UPDATE SET
                    rank_position   = excluded.rank_position,
                    score_total     = excluded.score_total,
                    score_semantic  = excluded.score_semantic,
                    score_lexical   = excluded.score_lexical,
                    score_location  = excluded.score_location,
                    supplier_email  = COALESCE(NULLIF(excluded.supplier_email, ''), buyer_supplier_matches.supplier_email),
                    supplier_phone  = COALESCE(NULLIF(excluded.supplier_phone, ''), buyer_supplier_matches.supplier_phone)
            ''', (
                match_id,
                item.get("buyer_id", ""),
                item.get("buyer_source", ""),
                item.get("source_type", ""),
                item.get("outreach_channel", ""),
                item.get("buyer_title", ""),
                item.get("buyer_query", ""),
                item.get("buyer_url", ""),
                item.get("buyer_email", ""),
                item.get("buyer_phone", ""),
                item.get("supplier_id", ""),
                item.get("supplier_name", ""),
                item.get("supplier_email", ""),
                item.get("supplier_phone", ""),
                item.get("supplier_city", ""),
                item.get("supplier_industry", ""),
                item.get("rank_position", 0),
                item.get("score_total", 0.0),
                item.get("score_semantic", 0.0),
                item.get("score_lexical", 0.0),
                item.get("score_location", 0.0),
            ))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error saving match {match_id}: {e}")
            return False
        finally:
            conn.close()

    def get_pending_matches(self, outreach_channel="email", limit=None):
        """
        Lấy các kết quả matching chưa gửi outreach, gom nhóm theo buyer.

        Returns:
            list[dict] mỗi phần tử: {buyer: {...}, matches: [...]}
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        sql = """
            SELECT * FROM buyer_supplier_matches
            WHERE outreach_channel = ? AND outreach_status = 'pending'
            ORDER BY buyer_id, rank_position ASC
        """
        rows = [dict(r) for r in cursor.execute(sql, (outreach_channel,)).fetchall()]
        conn.close()

        grouped: dict[str, dict] = {}
        for row in rows:
            bucket = grouped.setdefault(row["buyer_id"], {
                "buyer": {
                    "buyer_id": row["buyer_id"],
                    "buyer_source": row["buyer_source"],
                    "source_type": row["source_type"],
                    "title": row["buyer_title"],
                    "query": row["buyer_query"],
                    "url": row["buyer_url"],
                    "email": row["buyer_email"],
                    "phone": row["buyer_phone"],
                },
                "matches": [],
            })
            bucket["matches"].append(row)

        result = list(grouped.values())
        return result[:limit] if limit else result

    def mark_match_sent(self, match_id, error=None):
        """Đánh dấu 1 match đã gửi outreach (hoặc gửi lỗi)."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                UPDATE buyer_supplier_matches
                SET outreach_status = ?, outreach_sent_at = CURRENT_TIMESTAMP, outreach_error = ?
                WHERE match_id = ?
            ''', ("failed" if error else "sent", error, match_id))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def get_match_stats(self):
        """Thống kê hàng đợi matching theo kênh và trạng thái."""
        conn = self.get_connection()
        cursor = conn.cursor()
        rows = cursor.execute('''
            SELECT outreach_channel, outreach_status, COUNT(*) AS n,
                   COUNT(DISTINCT buyer_id) AS buyers
            FROM buyer_supplier_matches
            GROUP BY outreach_channel, outreach_status
        ''').fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_stats(self):
        """Returns row count statistics for database."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM buyers")
        buyer_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM suppliers_vietnam")
        supplier_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM supplier_posts")
        supplier_post_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM buyer_supplier_matches")
        match_count = cursor.fetchone()[0]
        conn.close()
        return {
            "buyers_total": buyer_count,
            "suppliers_vietnam_total": supplier_count,
            "supplier_posts_total": supplier_post_count,
            "matches_total": match_count
        }
