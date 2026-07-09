import os
import csv
import re
import numpy as np
import logging
from sentence_transformers import SentenceTransformer, util

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class B2BMatchingEngine:
    def __init__(self, csv_path, model_name='keepitreal/vietnamese-sbert'):
        self.csv_path = csv_path
        self.model_name = model_name
        self.model = None
        self.companies = []
        self.company_embeddings = None
        
    def load_data(self):
        """Loads company data from CSV file."""
        logger.info(f"Loading data from {self.csv_path}...")
        if not os.path.exists(self.csv_path):
            raise FileNotFoundError(f"CSV file not found at {self.csv_path}")
            
        companies = []
        with open(self.csv_path, mode='r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                companies.append({
                    "name": row.get("Ten cong ty", "").strip(),
                    "mst": row.get("MST", "").strip(),
                    "email": row.get("Email", "").strip(),
                    "phone": row.get("SDT", "").strip(),
                    "main_industry": row.get("Nganh chinh", "").strip(),
                    "sub_industry": row.get("Nganh phu", "").strip(),
                    "address": row.get("Dia chi", "").strip(),
                    "city": row.get("Tinh/Thanh", "").strip(),
                    "type": row.get("Loai hinh", "").strip(),
                    "description": row.get("Mo ta", "").strip(),
                    "industry_group": row.get("Nhom nganh", "").strip(),
                    "classification": row.get("Nhóm phân loại", "").strip(),
                })
        self.companies = companies
        logger.info(f"Loaded {len(self.companies)} companies successfully.")
        
    def load_model(self):
        """Loads SentenceTransformer model."""
        if self.model is None:
            logger.info(f"Loading SBERT model '{self.model_name}'...")
            self.model = SentenceTransformer(self.model_name)
            logger.info("Model loaded successfully.")
            
    def _get_csv_hash(self):
        """Generates MD5 hash of the CSV file to validate cache integrity."""
        import hashlib
        if not os.path.exists(self.csv_path):
            return ""
        hasher = hashlib.md5()
        with open(self.csv_path, 'rb') as f:
            buf = f.read(65536)
            while len(buf) > 0:
                hasher.update(buf)
                buf = f.read(65536)
        return hasher.hexdigest()

    def build_index(self):
        """Encodes company metadata for semantic search (with automatic local caching)."""
        import pickle
        
        cache_path = self.csv_path + ".embeddings.pkl"
        current_hash = self._get_csv_hash()
        
        # Check if valid cache exists
        if os.path.exists(cache_path):
            try:
                logger.info(f"Loading cached embeddings from {cache_path}...")
                with open(cache_path, 'rb') as f:
                    cache_data = pickle.load(f)
                
                # Verify that cache corresponds to the current CSV file state and company count
                if cache_data.get("csv_hash") == current_hash and len(cache_data.get("embeddings", [])) == len(self.companies):
                    self.company_embeddings = cache_data["embeddings"]
                    logger.info("✅ Cached embeddings loaded successfully! Startup is instantaneous.")
                    return
                else:
                    logger.info("⚠️ CSV file has changed or cache is mismatching. Rebuilding embeddings...")
            except Exception as e:
                logger.warning(f"⚠️ Error loading cache: {e}. Rebuilding embeddings...")

        # Re-build if cache is missing or stale
        self.load_model()
        
        texts_to_embed = []
        for c in self.companies:
            # Combine name, main industry, and description for a richer semantic representation
            text = f"{c['name']} - Ngành: {c['main_industry']} - Mô tả: {c['description']}"
            texts_to_embed.append(text)
            
        logger.info(f"Encoding {len(texts_to_embed)} company profiles...")
        # Convert to numpy array for fast cosine similarity calculations
        self.company_embeddings = self.model.encode(texts_to_embed, convert_to_tensor=True)
        
        # Save to cache
        try:
            logger.info(f"Saving embeddings cache to {cache_path}...")
            cache_data = {
                "csv_hash": current_hash,
                "embeddings": self.company_embeddings
            }
            with open(cache_path, 'wb') as f:
                pickle.dump(cache_data, f, protocol=pickle.HIGHEST_PROTOCOL)
            logger.info("✅ Embeddings cache saved successfully.")
        except Exception as e:
            logger.warning(f"⚠️ Failed to save cache: {e}")
            
        logger.info("Company index built successfully.")
        
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

    def _check_location_match(self, company, query_locations):
        """Check if a company's city matches any of the query locations."""
        if not query_locations:
            return True  # No location constraint → all match
        company_city = company["city"].lower()
        for loc in query_locations:
            if loc.lower() in company_city or company_city in loc.lower():
                return True
        return False

    def match(self, query, w_semantic=0.5, w_lexical=0.3, w_location=0.2, min_score=0.3):
        """
        Funnel Matching: Lexical → Location → SBERT
        
        Tối ưu tốc độ bằng cách thu hẹp danh sách ứng viên qua 3 tầng:
          Tầng 1 (Lexical):  Lọc theo từ khóa ngành nghề      → ~100-300 DN
          Tầng 2 (Location): Thu hẹp theo khu vực địa lý       → ~20-50 DN  
          Tầng 3 (SBERT):    Chấm điểm ngữ nghĩa chính xác   → Top N
        """
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

