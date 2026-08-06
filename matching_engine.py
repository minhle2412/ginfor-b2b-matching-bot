import os
import re
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class B2BMatchingEngine:
    """
    Matching Engine ghép nhu cầu buyer với doanh nghiệp supplier.

    Nguồn dữ liệu supplier được tiêm vào qua `source` (xem package `datasource`),
    nên engine không phụ thuộc việc dữ liệu nằm ở Supabase hay file CSV.

        from datasource import get_supplier_source
        engine = B2BMatchingEngine(source=get_supplier_source())

    Vẫn tương thích ngược với cách gọi cũ:

        engine = B2BMatchingEngine(csv_path="Business_dataset.csv")
    """

    def __init__(self, csv_path=None, model_name='keepitreal/vietnamese-sbert', source=None):
        if source is None:
            if csv_path:
                from datasource import CsvSupplierSource
                source = CsvSupplierSource(csv_path)
            else:
                from datasource import get_supplier_source
                source = get_supplier_source()

        self.source = source
        self.csv_path = csv_path            # giữ lại cho code cũ tham chiếu
        self.model_name = model_name
        self.model = None
        self.companies = []
        self.company_embeddings = None

    # ------------------------------------------------------------------
    # DATA
    # ------------------------------------------------------------------
    def load_data(self):
        """Tải danh sách doanh nghiệp từ nguồn đã cấu hình."""
        logger.info(f"Loading suppliers from {self.source.describe()}...")
        self.companies = self.source.load()
        logger.info(f"Loaded {len(self.companies)} companies successfully.")

    def reload_data(self, rebuild_index=True):
        """
        Tải lại dữ liệu từ nguồn (dùng khi Supabase có DN mới).
        Embeddings chỉ được build lại nếu nội dung dữ liệu thực sự thay đổi.
        """
        self.companies = self.source.load(force_refresh=True)
        logger.info(f"🔄 Đã tải lại {len(self.companies)} doanh nghiệp từ {self.source.describe()}")
        if rebuild_index:
            self.company_embeddings = None
            self.build_index()

    def load_model(self):
        """Loads SentenceTransformer model."""
        if self.model is None:
            from sentence_transformers import SentenceTransformer
            logger.info(f"Loading SBERT model '{self.model_name}'...")
            self.model = SentenceTransformer(self.model_name)
            logger.info("Model loaded successfully.")

    def _embed_text_for(self, company):
        """Ghép các trường của DN thành đoạn văn bản đưa vào SBERT."""
        return f"{company['name']} - Ngành: {company['main_industry']} - Mô tả: {company['description']}"

    def build_index(self):
        """Encodes company metadata for semantic search (with automatic local caching)."""
        import pickle

        if not self.companies:
            self.load_data()

        cache_path = self.source.cache_path()
        current_hash = self.source.content_hash()

        # Check if valid cache exists
        if os.path.exists(cache_path):
            try:
                logger.info(f"Loading cached embeddings from {cache_path}...")
                with open(cache_path, 'rb') as f:
                    cache_data = pickle.load(f)

                # Verify that cache corresponds to current data state and company count
                cached_hash = cache_data.get("content_hash") or cache_data.get("csv_hash")
                if cached_hash == current_hash and len(cache_data.get("embeddings", [])) == len(self.companies):
                    self.company_embeddings = cache_data["embeddings"]
                    logger.info("✅ Cached embeddings loaded successfully! Startup is instantaneous.")
                    return
                else:
                    logger.info("⚠️ Dữ liệu nguồn đã thay đổi hoặc cache không khớp. Đang build lại embeddings...")
            except Exception as e:
                logger.warning(f"⚠️ Error loading cache: {e}. Rebuilding embeddings...")

        # Re-build if cache is missing or stale
        self.load_model()

        texts_to_embed = [self._embed_text_for(c) for c in self.companies]

        logger.info(f"Encoding {len(texts_to_embed)} company profiles...")
        self.company_embeddings = self.model.encode(texts_to_embed, convert_to_tensor=True)

        # Save to cache
        try:
            logger.info(f"Saving embeddings cache to {cache_path}...")
            cache_data = {
                "content_hash": current_hash,
                "csv_hash": current_hash,          # tương thích ngược với cache cũ
                "source_id": self.source.source_id,
                "embeddings": self.company_embeddings,
            }
            with open(cache_path, 'wb') as f:
                pickle.dump(cache_data, f, protocol=pickle.HIGHEST_PROTOCOL)
            logger.info("✅ Embeddings cache saved successfully.")
        except Exception as e:
            logger.warning(f"⚠️ Failed to save cache: {e}")

        logger.info("Company index built successfully.")

    # ------------------------------------------------------------------
    # SCORING HELPERS
    # ------------------------------------------------------------------
    def _extract_location_mentions(self, text):
        """Extracts city names or provinces from text to identify geographic intent."""
        text_lower = text.lower()

        # Location mapping for major regions in Vietnam
        location_patterns = {
            "TP. Hồ Chí Minh": [r"\bhcm\b", r"\bhồ chí minh\b", r"\bsài gòn\b", r"\bsg\b", r"\bquận 1\b", r"\bq1\b", r"\bthành phố hồ chí minh\b"],
            "Hà Nội": [r"\bhà nội\b", r"\bhn\b", r"\bthủ đô\b"],
            "Bình Dương": [r"\bbình dương\b", r"\bbd\b"],
            "Đồng Nai": [r"\bđồng nai\b", r"\bđn\b"],
            "Long An": [r"\blong an\b", r"\bla\b"],
            "Đà Nẵng": [r"\bđà nẵng\b", r"\bđn\b"],
            "Hải Phòng": [r"\bhải phòng\b", r"\bhp\b"],
        }

        found_locations = []
        for location_name, patterns in location_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    found_locations.append(location_name)
                    break
        return found_locations

    def _calculate_lexical_score(self, query, company):
        """Calculates keyword match score based on overlap between query and company industries."""
        query_words = set(re.findall(r'\w+', query.lower()))
        if not query_words:
            return 0.0

        # Combine company keywords
        company_keywords_str = f"{company['name']} {company['main_industry']} {company['sub_industry']} {company['industry_group']} {company['classification']}"
        company_words = set(re.findall(r'\w+', company_keywords_str.lower()))

        # Calculate intersection
        overlap = query_words.intersection(company_words)

        # Normalize by length of query words to see how much of the query is satisfied
        if not overlap:
            return 0.0
        return len(overlap) / len(query_words)

    @staticmethod
    def _normalize_province(text):
        """
        Chuẩn hoá tên tỉnh/thành để so khớp được mọi định dạng lưu trữ:

            "TP. Hồ Chí Minh"                        → "hochiminh"
            "ho-chi-minh"           (province_slug)  → "hochiminh"
            "Quận 7, Tp Hồ Chí Minh" (location)      → "quan7hochiminh"

        Bỏ dấu tiếng Việt, hạ chữ thường, bỏ mọi ký tự không phải chữ/số,
        rồi bỏ tiền tố hành chính ("tp", "thanhpho", "tinh").
        """
        from datasource.config import normalize_key

        key = normalize_key(text)
        for prefix in ("thanhpho", "tinh", "tp"):
            if key.startswith(prefix):
                key = key[len(prefix):]
                break
        return key

    def _check_location_match(self, company, query_locations):
        """Check if a company's city matches any of the query locations."""
        if not query_locations:
            return True  # No location constraint → all match
        company_city = self._normalize_province(company["city"])
        if not company_city:
            return False
        for loc in query_locations:
            loc_key = self._normalize_province(loc)
            if loc_key and (loc_key in company_city or company_city in loc_key):
                return True
        return False

    # ------------------------------------------------------------------
    # MATCHING
    # ------------------------------------------------------------------
    def match(self, query, w_semantic=0.5, w_lexical=0.3, w_location=0.2, min_score=0.3):
        """
        Funnel Matching: Lexical → Location → SBERT

        Tối ưu tốc độ bằng cách thu hẹp danh sách ứng viên qua 3 tầng:
          Tầng 1 (Lexical):  Lọc theo từ khóa ngành nghề      → ~100-300 DN
          Tầng 2 (Location): Thu hẹp theo khu vực địa lý       → ~20-50 DN
          Tầng 3 (SBERT):    Chấm điểm ngữ nghĩa chính xác   → Top N
        """
        from sentence_transformers import util
        import time
        t_start = time.time()

        if not self.companies:
            self.load_data()
        if self.company_embeddings is None:
            self.build_index()

        # ================================================================
        # TẦNG 1: LEXICAL PRE-FILTER (Lọc theo từ khóa ngành nghề)
        # ================================================================
        # Nhanh: chỉ so sánh chuỗi, O(n) nhưng mỗi phép tính rất nhẹ
        candidates = []
        for idx, company in enumerate(self.companies):
            lex_score = self._calculate_lexical_score(query, company)
            if lex_score > 0:
                candidates.append((idx, company, lex_score))

        t_lexical = time.time()
        logger.info(f"⚡ Tầng 1 (Lexical): {len(candidates)}/{len(self.companies)} DN khớp từ khóa [{(t_lexical - t_start)*1000:.0f}ms]")

        # Nếu lexical quá ít kết quả, mở rộng tìm trong phần mô tả (description)
        if len(candidates) < 20:
            existing_indices = {c[0] for c in candidates}
            query_words = set(re.findall(r'\w+', query.lower()))
            # Loại bỏ stop words tiếng Việt phổ biến khỏi query
            stop_words = {"cần", "tìm", "đang", "muốn", "cho", "của", "và", "với", "các",
                          "một", "được", "này", "đến", "bên", "nào", "có", "không", "ở",
                          "tại", "từ", "về", "mình", "bạn", "ai", "giúp", "nhé", "lớn",
                          "số", "lượng", "giá", "tốt", "uy", "tín", "chất", "cao"}
            meaningful_words = query_words - stop_words

            for idx, company in enumerate(self.companies):
                if idx in existing_indices:
                    continue
                desc_text = f"{company.get('description', '')} {company.get('main_industry', '')} {company.get('sub_industry', '')}"
                desc_words = set(re.findall(r'\w+', desc_text.lower()))
                overlap = meaningful_words.intersection(desc_words)
                if len(overlap) >= 2:
                    lex_score = len(overlap) / len(query_words) if query_words else 0
                    candidates.append((idx, company, lex_score))

            logger.info(f"   ↳ Mở rộng (description): {len(candidates)} DN sau khi tìm mô tả")

        # Giới hạn tối đa số ứng viên đưa vào SBERT để đảm bảo tốc độ
        MAX_SBERT_CANDIDATES = 300
        if len(candidates) > MAX_SBERT_CANDIDATES:
            candidates.sort(key=lambda x: x[2], reverse=True)
            candidates = candidates[:MAX_SBERT_CANDIDATES]
            logger.info(f"   ↳ Cắt giảm còn top {MAX_SBERT_CANDIDATES} ứng viên lexical cao nhất")

        # FALLBACK: Nếu lexical không tìm được gì, dùng toàn bộ SBERT (logic cũ)
        if not candidates:
            logger.info("   ⚠️ Không tìm thấy DN nào qua lexical. Fallback: SBERT toàn bộ.")
            return self._match_full_sbert(query, w_semantic, w_lexical, w_location, min_score)

        # ================================================================
        # TẦNG 2: LOCATION FILTER (Thu hẹp theo khu vực địa lý)
        # ================================================================
        query_locations = self._extract_location_mentions(query)

        if query_locations:
            location_matched = []
            location_unmatched = []
            for idx, comp, lex in candidates:
                if self._check_location_match(comp, query_locations):
                    location_matched.append((idx, comp, lex, 1.0))
                else:
                    location_unmatched.append((idx, comp, lex, 0.0))

            # Ưu tiên DN đúng khu vực, giữ DN khác khu vực làm dự phòng
            candidates_scored = location_matched + location_unmatched
            t_location = time.time()
            logger.info(f"⚡ Tầng 2 (Location): {len(location_matched)} đúng khu vực, {len(location_unmatched)} khác khu vực [{(t_location - t_lexical)*1000:.0f}ms]")
        else:
            # Không có yêu cầu vị trí → tất cả DN đều trung lập (loc_score=1.0)
            candidates_scored = [(idx, comp, lex, 1.0) for idx, comp, lex in candidates]
            t_location = time.time()
            logger.info(f"⚡ Tầng 2 (Location): Không có yêu cầu vị trí → giữ nguyên {len(candidates_scored)} DN [{(t_location - t_lexical)*1000:.0f}ms]")

        # ================================================================
        # TẦNG 3: SBERT SEMANTIC SCORING (Chấm điểm ngữ nghĩa chính xác)
        # ================================================================
        # Chỉ chạy SBERT trên tập ứng viên đã được thu hẹp
        self.load_model()

        candidate_indices = [c[0] for c in candidates_scored]
        candidate_embeddings = self.company_embeddings[candidate_indices]

        query_embedding = self.model.encode(query, convert_to_tensor=True)
        cos_scores = util.cos_sim(query_embedding, candidate_embeddings)[0].cpu().numpy()

        t_sbert = time.time()
        logger.info(f"⚡ Tầng 3 (SBERT): Chấm điểm {len(candidate_indices)} DN [{(t_sbert - t_location)*1000:.0f}ms]")

        # ================================================================
        # TỔNG HỢP ĐIỂM & XẾP HẠNG
        # ================================================================
        results = []
        for i, (idx, comp, lex_score, loc_score) in enumerate(candidates_scored):
            sem_score = float(cos_scores[i])
            sem_score = max(0.0, min(1.0, sem_score))

            total_score = (w_semantic * sem_score) + (w_lexical * lex_score) + (w_location * loc_score)

            results.append({
                "company": comp,
                "score_breakdown": {
                    "semantic": sem_score,
                    "lexical": lex_score,
                    "location": loc_score
                },
                "total_score": round(total_score, 4)
            })

        filtered_results = [r for r in results if r["total_score"] >= min_score]
        filtered_results.sort(key=lambda x: x["total_score"], reverse=True)

        t_end = time.time()
        logger.info(f"✅ Matching hoàn tất: {len(filtered_results)} kết quả | Tổng thời gian: {(t_end - t_start)*1000:.0f}ms")

        return filtered_results

    def _match_full_sbert(self, query, w_semantic, w_lexical, w_location, min_score):
        """
        Fallback: Chạy SBERT trên toàn bộ danh sách DN (logic gốc).
        Chỉ được gọi khi Tầng 1 (Lexical) không tìm được ứng viên nào.
        """
        from sentence_transformers import util

        self.load_model()
        query_embedding = self.model.encode(query, convert_to_tensor=True)
        cos_scores = util.cos_sim(query_embedding, self.company_embeddings)[0].cpu().numpy()

        query_locations = self._extract_location_mentions(query)

        results = []
        for idx, company in enumerate(self.companies):
            sem_score = max(0.0, min(1.0, float(cos_scores[idx])))
            lex_score = self._calculate_lexical_score(query, company)

            if not query_locations:
                loc_score = 1.0
            else:
                loc_score = 1.0 if self._check_location_match(company, query_locations) else 0.0

            total_score = (w_semantic * sem_score) + (w_lexical * lex_score) + (w_location * loc_score)

            results.append({
                "company": company,
                "score_breakdown": {
                    "semantic": sem_score,
                    "lexical": lex_score,
                    "location": loc_score
                },
                "total_score": round(total_score, 4)
            })

        filtered_results = [r for r in results if r["total_score"] >= min_score]
        filtered_results.sort(key=lambda x: x["total_score"], reverse=True)

        return filtered_results
