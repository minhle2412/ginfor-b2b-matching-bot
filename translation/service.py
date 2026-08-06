# -*- coding: utf-8 -*-
"""
Translator — điều phối dịch + cache bền vững.
================================================
Dịch bằng NMT trên CPU khá chậm (~1-2 giây mỗi đoạn), nên cache là bắt buộc:
mỗi đoạn văn bản chỉ dịch đúng một lần trong suốt vòng đời hệ thống, kể cả khi
chạy lại pipeline nhiều lần hay khởi động lại tiến trình.

Luồng xử lý một văn bản:
    1. Rỗng → trả về nguyên trạng
    2. Đã là tiếng Việt → trả về nguyên trạng (không dịch)
    3. Có trong cache → trả về bản dịch đã lưu
    4. Cắt thành đoạn ngắn → dịch qua backend → ghép lại
    5. Bổ sung thuật ngữ B2B tiếng Việt → lưu cache → trả về
"""

import hashlib
import logging
import os
import sqlite3
import threading
import time

from .backends import get_backend, split_into_chunks
from .detect import detect_language
from .glossary import augment_with_glossary
from .preprocess import clean_boilerplate

logger = logging.getLogger("translation.service")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def default_cache_path() -> str:
    custom = os.getenv("TRANSLATION_CACHE_DB", "").strip()
    if custom:
        return custom
    cache_dir = os.path.join(BASE_DIR, ".cache")
    os.makedirs(cache_dir, exist_ok=True)
    return os.path.join(cache_dir, "translations.db")


class TranslationCache:
    """Cache bản dịch trong SQLite, khoá theo SHA-256 của văn bản gốc."""

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or default_cache_path()
        self._lock = threading.Lock()
        # SQLite in-memory chỉ tồn tại trong đúng connection tạo ra nó. Mở lại
        # connection mới là mất sạch bảng, nên phải giữ một connection dùng chung.
        self._is_memory = self.db_path == ":memory:"
        self._shared_conn = None
        if self._is_memory:
            self._shared_conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._shared_conn.row_factory = sqlite3.Row
        self._init_db()

    def _connect(self):
        if self._shared_conn is not None:
            return self._shared_conn
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    def _close(self, conn):
        """Chỉ đóng connection dùng một lần; connection in-memory phải giữ lại."""
        if conn is not self._shared_conn:
            conn.close()

    def _init_db(self):
        conn = self._connect()
        conn.execute('''
            CREATE TABLE IF NOT EXISTS translations (
                text_hash    TEXT PRIMARY KEY,
                source_lang  TEXT NOT NULL,
                target_lang  TEXT NOT NULL,
                source_text  TEXT NOT NULL,
                translated   TEXT NOT NULL,
                backend      TEXT,
                created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        self._close(conn)

    @staticmethod
    def make_key(text: str, backend: str, target_lang: str) -> str:
        """Khoá cache gắn với cả backend: đổi model thì bản dịch cũ không bị dùng lại."""
        raw = f"{backend}|{target_lang}|{text}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get(self, key: str) -> str | None:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT translated FROM translations WHERE text_hash = ?", (key,)
            ).fetchone()
            return row["translated"] if row else None
        finally:
            self._close(conn)

    def put(self, key, source_text, translated, source_lang, target_lang, backend):
        with self._lock:
            conn = self._connect()
            try:
                conn.execute('''
                    INSERT INTO translations
                        (text_hash, source_lang, target_lang, source_text, translated, backend)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(text_hash) DO UPDATE SET translated = excluded.translated
                ''', (key, source_lang, target_lang, source_text, translated, backend))
                conn.commit()
            except Exception as e:
                logger.warning(f"⚠️ Không ghi được cache dịch: {e}")
            finally:
                self._close(conn)

    def stats(self) -> dict:
        conn = self._connect()
        try:
            total = conn.execute("SELECT COUNT(*) FROM translations").fetchone()[0]
            by_backend = {
                r["backend"]: r["n"] for r in conn.execute(
                    "SELECT backend, COUNT(*) AS n FROM translations GROUP BY backend"
                )
            }
            return {"total": total, "by_backend": by_backend, "db_path": self.db_path}
        finally:
            self._close(conn)


class Translator:
    """
    Dịch văn bản sang tiếng Việt, có cache và bỏ qua văn bản đã là tiếng Việt.

        tr = Translator()
        tr.translate("Looking for white rice suppliers")
        tr.translate_many([...])          # dịch cả lô, tận dụng batch của model
    """

    def __init__(self, backend=None, cache=None, target_lang="vi",
                 use_glossary=True, clean_input=True):
        self.backend = backend or get_backend()
        self.cache = cache if cache is not None else TranslationCache()
        self.target_lang = target_lang
        self.use_glossary = use_glossary
        self.clean_input = clean_input
        self._stats = {"translated": 0, "cache_hits": 0, "skipped_vi": 0, "chunks": 0}

    # ------------------------------------------------------------------
    def translate(self, text: str) -> str:
        """Dịch một văn bản sang tiếng Việt. Văn bản tiếng Việt được giữ nguyên."""
        return self.translate_many([text])[0]

    def translate_many(self, texts: list[str]) -> list[str]:
        """
        Dịch nhiều văn bản cùng lúc.

        Gom tất cả đoạn cần dịch của mọi văn bản vào một lô duy nhất rồi mới gọi
        model — nhanh hơn nhiều so với dịch từng văn bản một.
        """
        results: list[str | None] = [None] * len(texts)
        pending_chunks: list[str] = []          # các đoạn thực sự phải gọi model
        chunk_owner: list[tuple[int, int]] = []  # (chỉ số văn bản, thứ tự đoạn)
        doc_chunks: dict[int, list[str | None]] = {}

        # Xác định backend thực sự sẽ dùng TRƯỚC khi tính khoá cache. Nếu model
        # không nạp được và hệ thống lùi về từ điển, bản dịch phải được lưu dưới
        # khoá 'glossary' để lần sau model chạy được không đọc trúng bản kém.
        needs_translation = any(
            t and t.strip() and detect_language(t) != self.target_lang for t in texts
        )
        backend_name = self.backend.ensure_ready() if needs_translation else self.backend.name

        for i, text in enumerate(texts):
            if not text or not text.strip():
                results[i] = text or ""
                continue

            if detect_language(text) == self.target_lang:
                results[i] = text
                self._stats["skipped_vi"] += 1
                continue

            key = self.cache.make_key(text, backend_name, self.target_lang)
            cached = self.cache.get(key)
            if cached is not None:
                results[i] = cached
                self._stats["cache_hits"] += 1
                continue

            # Bỏ câu khuôn mẫu của trang B2B trước khi đưa vào model. Khoá cache
            # vẫn tính trên văn bản GỐC để lần gọi sau vẫn trúng cache.
            working = clean_boilerplate(text) if self.clean_input else text

            chunks = split_into_chunks(working)
            doc_chunks[i] = [None] * len(chunks)
            for j, chunk in enumerate(chunks):
                # Cache cả ở mức đoạn: các bài RFQ dùng chung nhiều câu khuôn mẫu
                chunk_key = self.cache.make_key(chunk, backend_name, self.target_lang)
                chunk_cached = self.cache.get(chunk_key)
                if chunk_cached is not None:
                    doc_chunks[i][j] = chunk_cached
                else:
                    pending_chunks.append(chunk)
                    chunk_owner.append((i, j))

        # Gọi model một lần cho toàn bộ đoạn còn thiếu
        if pending_chunks:
            t0 = time.time()
            logger.info(f"🌐 Đang dịch {len(pending_chunks)} đoạn sang tiếng Việt...")
            translated_chunks = self.backend.translate_batch(pending_chunks)
            self._stats["chunks"] += len(pending_chunks)
            logger.info(f"   ✅ Dịch xong {len(pending_chunks)} đoạn trong {time.time() - t0:.1f}s")

            for (i, j), source, translated in zip(chunk_owner, pending_chunks, translated_chunks):
                doc_chunks[i][j] = translated
                self.cache.put(
                    self.cache.make_key(source, backend_name, self.target_lang),
                    source, translated, "en", self.target_lang, backend_name,
                )

        # Ghép đoạn, bổ sung thuật ngữ, lưu cache mức văn bản
        for i, parts in doc_chunks.items():
            source = texts[i]
            merged = " ".join(p for p in parts if p).strip()
            if self.use_glossary:
                merged = augment_with_glossary(source, merged)
            results[i] = merged
            self._stats["translated"] += 1
            self.cache.put(
                self.cache.make_key(source, backend_name, self.target_lang),
                source, merged, "en", self.target_lang, backend_name,
            )

        return [r if r is not None else "" for r in results]

    # ------------------------------------------------------------------
    def get_stats(self) -> dict:
        return dict(self._stats, backend=self.backend.name)


_default_translator: Translator | None = None


def get_translator(**kwargs) -> Translator:
    """Trả về Translator dùng chung toàn tiến trình (model chỉ nạp một lần)."""
    global _default_translator
    if _default_translator is None or kwargs:
        translator = Translator(**kwargs)
        if not kwargs:
            _default_translator = translator
        return translator
    return _default_translator


def is_translation_enabled() -> bool:
    """Bật/tắt toàn cục qua biến môi trường TRANSLATE_BUYER_POSTS (mặc định bật)."""
    return os.getenv("TRANSLATE_BUYER_POSTS", "true").strip().lower() not in ("false", "0", "no")
