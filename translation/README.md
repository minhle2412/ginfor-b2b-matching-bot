# Dịch bài đăng buyer (Anh → Việt)

## Vì sao cần

Matching Engine dùng `keepitreal/vietnamese-sbert` — model nhúng **đơn ngữ tiếng
Việt**. Trong khi đó:

| Nguồn bài đăng buyer | Ngôn ngữ | Ngôn ngữ mô tả DN (Supabase) |
|---|---|---|
| Facebook group | Tiếng Việt | Tiếng Việt ✅ cùng ngôn ngữ |
| Go4WorldBusiness, EC21, GlobalSources, TradeWheel | **Tiếng Anh** | Tiếng Việt ❌ lệch ngôn ngữ |

Khi hai đầu khác ngôn ngữ, vector nhúng nằm ở hai vùng khác nhau nên điểm cosine
gần như vô nghĩa. Biểu hiện thực tế đã ghi nhận: bài `"Rice Buyers"` từng khớp
cao nhất với một công ty **mã vạch** ở mức 48%.

Dịch bài đăng sang tiếng Việt trước khi matching đưa cả hai đầu về cùng không
gian ngữ nghĩa.

## Luồng xử lý

```
Bài đăng buyer
     │
     ├─ Rỗng ────────────────────────────► trả về nguyên trạng
     │
     ├─ detect_language() == 'vi' ───────► trả về nguyên trạng (bài Facebook)
     │
     ├─ Có trong cache ──────────────────► trả về bản dịch đã lưu
     │
     └─ Cắt đoạn ─► Backend dịch ─► Ghép ─► Bổ sung thuật ngữ B2B ─► Lưu cache
```

**Phát hiện ngôn ngữ** ([detect.py](detect.py)) dùng heuristic, không cần thư viện
ngoài: đếm ký tự có dấu riêng của tiếng Việt, cộng thêm từ chức năng không dấu để
bắt cả văn bản mất dấu. Đủ tin cậy cho việc chỉ cần phân biệt "Việt / không Việt",
và không đoán sai với tiêu đề RFQ ngắn như `langdetect`.

**Cắt đoạn** ([backends.py](backends.py)) theo ranh giới tự nhiên (xuống dòng →
câu → cụm), giới hạn 400 ký tự mỗi đoạn để không vượt ngưỡng 512 token của model.

**Cache** ([service.py](service.py)) lưu trong SQLite ở cả hai mức — toàn văn bản
và từng đoạn. Các bài RFQ dùng chung rất nhiều câu khuôn mẫu
(`"Buyer is interested to receive quotations for the following RFQ"`), nên cache
mức đoạn tiết kiệm đáng kể. Khoá cache gắn với tên backend: đổi model thì bản dịch
cũ không bị dùng lại.

**Từ điển B2B** ([glossary.py](glossary.py)) chứa ~150 thuật ngữ xuất nhập khẩu.
Có hai vai trò:
- *Bổ sung sau khi dịch*: nối thêm thuật ngữ tiếng Việt chuẩn ngành mà model dịch
  không dùng đúng (`broken rice` → **tấm**, không phải "gạo vỡ"), giúp tầng lexical
  bắt đúng từ khoá doanh nghiệp dùng để mô tả mình.
- *Dự phòng*: khi không nạp được model, thay thế từng thuật ngữ vẫn hơn để nguyên
  tiếng Anh.

## Chọn model — kết quả kiểm chứng thật

Đã thử 3 model trên chính dữ liệu buyer của dự án:

| Model | Kết quả | Kết luận |
|---|---|---|
| `Helsinki-NLP/opus-mt-en-vi` (300MB) | `"wants to import long grain white rice"` → `"muốn **tính tiền** gạo trắng dài"`<br>`"cashew kernels"` → `"**thu ngân**"` | ❌ Không dùng được, sai cả với câu văn tự nhiên |
| `VietAI/envit5-translation` | `TypeError: argument 'vocab'` | ❌ Không tương thích `transformers` 5.x |
| **`facebook/nllb-200-distilled-600M`** (2.4GB) | `"muốn nhập khẩu gạo trắng hạt dài với 5%..."` ✅ | ✅ **Đang dùng** |

Hai điểm yếu còn lại của NLLB, đều đã có cơ chế bù:

1. **Tiêu đề dạng liệt kê bị bỏ nguyên tiếng Anh** (`"Rice Like Steam Basmati Rice"`).
   → [preprocess.py](preprocess.py) xoá boilerplate (`"WANTED :"`) để phần còn lại
   giống câu hoàn chỉnh hơn; phần mô tả (là câu đầy đủ) vẫn dịch tốt và đóng góp
   chính vào điểm ngữ nghĩa.

2. **Sai thuật ngữ ngành**: `"cashew kernels"` → `"hạt cà phê"` (phải là *nhân hạt điều*).
   → [glossary.py](glossary.py) nối thêm thuật ngữ tiếng Việt chuẩn ngành vào bản
   dịch, nên tầng lexical vẫn bắt đúng dù câu dịch sai.

Cả hai cơ chế này là lý do kiến trúc không phụ thuộc hoàn toàn vào chất lượng model.

## Cấu hình

```env
TRANSLATE_BUYER_POSTS=true                        # bật/tắt toàn cục
TRANSLATION_BACKEND=nmt                           # nmt | glossary
TRANSLATION_MODEL=Helsinki-NLP/opus-mt-en-vi      # model NMT
TRANSLATION_BATCH_SIZE=8
# TRANSLATION_CACHE_DB=.cache/translations.db
```

Backend `nmt` cần thêm hai gói: `pip install sentencepiece sacremoses`
(MarianTokenizer bắt buộc có SentencePiece — thiếu sẽ báo lỗi khó hiểu về
`AutoTokenizer`, hệ thống tự lùi về `glossary`).

## Sử dụng

```bash
# Dịch một câu
python -m translation.cli "Looking for white rice suppliers, MOQ 20 containers"

# Dịch thử bài đăng buyer thật trong database
python -m translation.cli --buyers 5

# So sánh backend
python -m translation.cli --backend glossary "broken rice 5% and cashew kernel"

# Quản lý cache
python -m translation.cli --stats
python -m translation.cli --clear-cache
```

Trong pipeline matching, dịch được bật mặc định:

```bash
python ecommerce_matching.py --limit 20        # có dịch
python ecommerce_matching.py --no-translate    # tắt dịch cho lần chạy này
```

## Dùng trong code

```python
from translation import get_translator

tr = get_translator()
tr.translate("Buyer needs 500 MT of white rice")
tr.translate_many([...])       # dịch cả lô, nhanh hơn nhiều so với gọi lẻ
tr.get_stats()                 # {'translated', 'cache_hits', 'skipped_vi', ...}
```

Luôn ưu tiên `translate_many()` khi có nhiều văn bản: nó gom toàn bộ đoạn của mọi
văn bản vào một lô duy nhất rồi mới gọi model.
