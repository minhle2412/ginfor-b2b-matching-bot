# Implementation plan: Buyer-Business Matching Engine

**Phạm vi:** Match nhu cầu buyer (bài Facebook) với 80.000 doanh nghiệp, gửi kết quả qua Discord, có UI tinh chỉnh, sẵn sàng tích hợp website.
**Nền tảng có sẵn:** `facebook_scraper_bot.py` (scraping + buyer-intent detection bằng SBERT đã hoạt động).
**Kỹ thuật cốt lõi:** Vector embedding (dense semantic search) + industry bonus (lexical) + weighted scoring.

---

## Phase 0 — Chuẩn hoá dữ liệu doanh nghiệp (1 tuần)

Mục tiêu: dữ liệu đủ sạch để embedding và industry bonus hoạt động đúng.

| Việc cần làm | Chi tiết | Deliverable |
|---|---|---|
| Audit dữ liệu | Đếm % dòng thiếu `Nhom nganh`/`Nhóm phân loại`, kiểm tra trùng lặp MST | Báo cáo audit ngắn |
| Backfill taxonomy | Dùng LLM (batch) phân loại lại `Nganh chinh`/`Mo ta` thành `Nhom nganh` chuẩn cho các dòng thiếu | Script `backfill_taxonomy.py` + CSV đã điền đầy đủ |
| Chốt taxonomy chuẩn | Danh sách cố định các nhóm ngành (không để LLM tự sinh nhãn mới mỗi lần) | File `taxonomy.json` |
| Dedupe doanh nghiệp | Fuzzy match theo MST/tên/địa chỉ, loại trùng lặp do scrape nhiều nguồn | Script dedupe + số liệu trước/sau |

**Rủi ro:** nếu bỏ qua bước này, industry bonus gần như vô dụng (đã thấy rõ trong sample: hầu hết dòng trống `Nhom nganh`). Không nên bỏ qua để tiết kiệm thời gian.

---

## Phase 1 — MVP matching engine (1 tuần)

Mục tiêu: `business_matcher.py` chạy được trên dữ liệu thật, tích hợp vào bot hiện có.

| Việc cần làm | Chi tiết | Deliverable |
|---|---|---|
| Build index thật | Chạy `build_index()` trên CSV 80k dòng đã backfill, đo thời gian encode + kích thước cache | `business_embeddings.npy` + log thời gian |
| Patch bot | Thêm `business_matcher.match()` vào `scrape_all_groups()`, mở rộng `send_to_discord()` hiển thị top 5 DN | `facebook_scraper_bot.py` đã patch |
| Test end-to-end | Chạy `!fb_scrape` thật, kiểm tra kết quả match có hợp lý không (spot-check 20-30 bài) | Checklist test + ghi chú kết quả |
| Chốt trọng số & ngưỡng ban đầu | Dựa trên spot-check, đặt `MATCH_W_*` và `MATCH_MIN_SCORE` khởi điểm trong `.env` | `.env.bot.facebook` cập nhật |

**Rủi ro:** encode 80k dòng lần đầu có thể mất vài phút — nên chạy offline (không phải lúc bot khởi động), cache vào file rồi mới load.

---

## Phase 2 — UI tinh chỉnh có API thật (1 tuần)

Mục tiêu: nối `matching_tuning_prototype.html` với dữ liệu thật, không còn số liệu demo.

| Việc cần làm | Chi tiết | Deliverable |
|---|---|---|
| Viết API wrapper | FastAPI expose `BusinessMatcher.match()` qua endpoint `POST /match` (nhận post text, trả về danh sách DN + breakdown) | `api/main.py` |
| Nối UI với API | Thay dữ liệu mock trong HTML bằng `fetch()` gọi API thật | `matching_tuning_prototype.html` bản v2 |
| Thêm approve/reject | Nút duyệt/từ chối từng match, lưu nhãn vào DB nhỏ (SQLite/Postgres) | Bảng `match_feedback` |
| Auth nội bộ | Giới hạn ai truy cập được UI (vì có dữ liệu liên hệ DN) | Basic auth hoặc giới hạn IP nội bộ |

---

## Phase 3 — Vòng lặp đánh giá & cải thiện (liên tục, 2 tuần đầu quan sát)

Mục tiêu: biết hệ thống đang đúng bao nhiêu %, không đoán mò.

| Việc cần làm | Chi tiết | Deliverable |
|---|---|---|
| Precision@5 | Với mỗi bài buyer đã gửi Discord, người vận hành đánh giá top 5 DN đúng/sai | Số liệu precision hàng tuần |
| Phân tích lỗi | Xem các case sai nhiều nhất — do embedding lệch ngành? do thiếu taxonomy? | Ghi chú lỗi phổ biến |
| Điều chỉnh trọng số dựa trên dữ liệu | Không đoán, mà nhìn vào nhãn approve/reject để chỉnh `w_semantic`/`w_industry` | Trọng số v2 |

---

## Phase 4 — Nâng cấp độ chính xác (tuỳ ngân sách, sau khi có baseline)

Chỉ làm sau khi Phase 3 cho thấy baseline chưa đủ tốt (ví dụ precision@5 < 60%).

| Việc cần làm | Chi tiết | Ưu tiên |
|---|---|---|
| LLM structured extraction | Trích xuất nhu cầu buyer thành JSON (sản phẩm, số lượng, khu vực) thay vì so toàn văn bản thô | Cao — cải thiện rõ rệt, chi phí thấp (1 call/bài) |
| Cross-encoder re-ranking | Re-rank top 20-50 ứng viên bằng model đọc đồng thời cặp văn bản | Trung bình — tốn thêm compute, chỉ đáng làm nếu precision vẫn thấp sau khi có LLM extraction |
| Learning-to-rank | Dùng nhãn approve/reject tích luỹ để tự học trọng số tối ưu | Thấp — cần đủ dữ liệu nhãn (vài trăm-nghìn mẫu) mới có ý nghĩa |
| Vector DB (Qdrant/pgvector) | Chỉ cần nếu dữ liệu doanh nghiệp scale lên hàng triệu dòng hoặc cần multi-tenant filtering phức tạp | Thấp ở quy mô hiện tại (80k dòng) |

---

## Phase 5 — Tích hợp website (sau khi ổn định qua Discord)

| Việc cần làm | Chi tiết | Deliverable |
|---|---|---|
| Expose API chính thức | Bảo mật, rate limit, versioning cho `/match` endpoint | API production-ready |
| UI trên website | Chuyển từ prototype nội bộ sang giao diện cho end-user (buyer tự nhập nhu cầu thay vì chỉ lấy từ Facebook) | Trang matching trên thongtincty.com |
| Đồng bộ dữ liệu | Job định kỳ cập nhật index khi có doanh nghiệp mới/scrape mới | Cron job đồng bộ |

---

## Tóm tắt timeline

| Tuần | Nội dung chính |
|---|---|
| 1 | Phase 0 — backfill taxonomy, dedupe |
| 2 | Phase 1 — build index thật, patch bot, test end-to-end |
| 3 | Phase 2 — API + UI thật + approve/reject |
| 3-5 | Phase 3 — quan sát, đo precision, điều chỉnh trọng số |
| Sau đó | Phase 4 (nếu cần) → Phase 5 |

## Điều kiện để coi MVP thành công
- Mỗi bài buyer trả về ít nhất 1 DN match với điểm ≥ ngưỡng trong > 80% trường hợp có nhu cầu rõ ràng.
- Precision@5 (đánh giá thủ công) đạt mức chấp nhận được để người vận hành thấy hữu ích, không phải bỏ qua Discord message.
- Người vận hành có thể tự đổi trọng số qua UI mà không cần dev can thiệp code.

## Rủi ro cần theo dõi xuyên suốt
- Chất lượng taxonomy (`Nhom nganh`) là yếu tố quyết định chất lượng industry bonus — không nên bỏ qua Phase 0 để đi nhanh.
- Encode lại toàn bộ 80k dòng mỗi khi có DN mới sẽ chậm dần theo thời gian — nên thiết kế incremental update (chỉ encode dòng mới) ngay từ Phase 1 thay vì rebuild toàn bộ.
- Việc scraping Facebook bằng cookie cá nhân có rủi ro về điều khoản sử dụng của Facebook — nằm ngoài phạm vi matching engine nhưng cần đội ngũ pháp lý/vận hành nắm rõ.
