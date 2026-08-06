# Chuyển từ dữ liệu mẫu sang Supabase

Tài liệu hướng dẫn cấu hình hệ thống B2B Matching lấy danh sách doanh nghiệp
supplier từ Supabase thay cho file mẫu `Business_dataset.csv`.

---

## 1. Kiến trúc sau khi cấu hình lại

```
                         ┌──────────────────────────────┐
                         │   SUPABASE (bảng supplier)   │
                         │   dữ liệu DN chính thức      │
                         └──────────────┬───────────────┘
                                        │ PostgREST API (phân trang, cache offline)
                                        ▼
                         ┌──────────────────────────────┐
                         │  datasource/  (mapping cột)  │
                         └──────────────┬───────────────┘
                                        ▼
                         ┌──────────────────────────────┐
                         │   matching_engine.py         │
                         │   Lexical → Location → SBERT │
                         └───────┬──────────────┬───────┘
             bài đăng buyer      │              │      bài đăng buyer
             Facebook group      │              │      trang B2B e-commerce
             (tiếng Việt)        │              │      (tiếng Anh → cần dịch)
                                 │              │              ▲
                                 │              │       ┌──────┴───────┐
                                 │              │       │ translation/ │
                                 │              │       │  Anh → Việt  │
                                 │              │       └──────────────┘
                                 ▼              ▼
                    ┌────────────────────┐  ┌────────────────────┐
                    │ fb_matching_bot.py │  │ecommerce_matching.py│
                    └─────────┬──────────┘  └─────────┬──────────┘
                              ▼                       ▼
                    ┌───────────────────────────────────────────┐
                    │  b2b_harvester.db → buyer_supplier_matches│
                    │  outreach_channel='facebook_comment'      │
                    │  outreach_channel='email'                 │
                    └───────────────────────────────────────────┘
                              │                       │
                              ▼                       ▼
                    Comment vào bài viết        Email marketing
                    (triển khai sau)            (triển khai sau)
```

Điểm mấu chốt: **Matching Engine không còn biết dữ liệu đến từ đâu**. Việc lấy
dữ liệu nằm trong package `datasource/`, đổi nguồn chỉ cần đổi biến môi trường.

---

## 2. Các bước cấu hình

### Bước 1 — Tạo file `.env`

```bash
cd "B2B Matching funtion"
cp .env.example .env
```

Điền 3 giá trị bắt buộc (lấy tại Supabase Dashboard → Project Settings → API):

```env
SUPPLIER_SOURCE=supabase
SUPABASE_URL=https://<project-ref>.supabase.co
SUPABASE_KEY=<service_role key hoặc anon key>
SUPABASE_SUPPLIER_TABLE=<tên bảng doanh nghiệp>
```

> Dùng `service_role` key nếu bảng bật RLS. Key này có toàn quyền — chỉ để trong
> `.env` (đã nằm trong `.gitignore`), không đưa lên client.

### Bước 2 — Kiểm tra kết nối và dò tên cột

```bash
python -m datasource.introspect --list-tables   # xem có những bảng nào
python -m datasource.introspect                 # kiểm tra bảng đã cấu hình
```

Lệnh này in ra:
1. Trạng thái kết nối + số dòng trong bảng
2. Toàn bộ tên cột thật
3. Mapping `canonical field → cột thật` mà hệ thống tự dò được
4. **Đoạn `.env` đã điền sẵn** để bạn dán vào (chỉ cần sửa dòng nào dò sai)
5. 3 dòng dữ liệu mẫu sau khi chuẩn hoá

Bộ dò tự bỏ dấu tiếng Việt, bỏ gạch dưới và không phân biệt hoa thường, nên
`Ten cong ty`, `ten_cong_ty`, `TenCongTy`, `company_name` đều nhận ra như nhau.
Chỉ khi tên cột quá khác thường mới phải chỉ định tay:

```env
SUPPLIER_COL_NAME=ten_doanh_nghiep_day_du
SUPPLIER_COL_DESCRIPTION=gioi_thieu_nang_luc
```

Trường **bắt buộc** phải map được là `name`. Các trường còn lại thiếu thì để
rỗng, matching vẫn chạy nhưng độ chính xác giảm — nên có ít nhất `main_industry`,
`description` và `city`.

### Bước 3 — Chạy thử

```bash
# Dashboard tinh chỉnh trọng số
python app.py
# → mở http://127.0.0.1:8000
# → GET /api/source   xem nguồn dữ liệu + mapping cột đang dùng
# → POST /api/reload  tải lại dữ liệu từ Supabase không cần restart

# Bot Facebook (nhánh comment)
./run_matching_bot.sh

# Nhánh B2B e-commerce (nhánh email)
python ecommerce_matching.py --limit 20
```

Lần chạy đầu tiên sau khi đổi sang Supabase sẽ mất vài phút để encode embeddings
cho toàn bộ doanh nghiệp. Các lần sau đọc từ cache (`.cache/embeddings_supabase_*.pkl`)
và khởi động tức thì. Cache tự build lại khi dữ liệu trên Supabase thay đổi.

---

## 2b. Cấu hình thực tế của dự án này

Đã kiểm chứng bằng dữ liệu thật ngày 06/08/2026:

| Hạng mục | Giá trị |
|---|---|
| Project | `https://xaszpyiyhzwsibpphuit.supabase.co` |
| Bảng | `company_profiles` — 85.865 dòng, 63 cột |
| Filter đang áp | `or=(main_industry.not.is.null,description.not.is.null)` → **12.555 DN** |
| Thời gian tải | ~10 giây (13 trang) |

Lý do lọc: 73.310 DN (85,4%) trong bảng chỉ có tên + địa chỉ + MST, không có ngành
nghề lẫn mô tả. Với những dòng đó, chuỗi đưa vào SBERT chỉ còn mỗi tên công ty —
không đủ để khớp nhu cầu buyer, mà lại tạo nhiễu và đẩy DN tốt xuống hạng.
Bỏ filter bằng cách xoá dòng `SUPABASE_SUPPLIER_FILTER` trong `.env`.

Độ phủ trong tập 12.555 DN đã lọc:

| Trường | Cột Supabase | Độ phủ |
|---|---|---|
| `name` | `name` | 100% |
| `phone` | `phone` | 100% |
| `website` | `website` | 100% |
| `description` | `description` | 99.9% |
| `email` | `business_email` | 99.6% |
| `main_industry` | `main_industry` | 95.7% |
| `city` | `location` \| `province_slug` \| `address` | 98.9% |
| `sub_industry` | `other_industries` | 88.4% |
| `industry_group`, `classification` | *(bảng không có cột tương ứng)* | — |

### Hai điểm phải chú ý khi đổi bảng/cột

1. **Bộ tự dò có thể chọn nhầm cột rỗng.** Ở đây nó chọn `province_code` cho
   `city`, trong khi cột đó rỗng 100%. Luôn xem phần "dữ liệu mẫu" mà
   `introspect` in ra để kiểm chứng, đừng chỉ tin bảng mapping.

2. **Một canonical field có thể ghép nhiều cột dự phòng**, ngăn cách bằng `|`,
   lấy cột đầu tiên khác rỗng ở từng dòng:

   ```env
   SUPPLIER_COL_CITY=location|province_slug|address
   ```

   Ở dự án này `location` chỉ phủ 24.3% trong tập đã lọc, `province_slug` 42.1%,
   `address` 98.9% — ghép cả ba mới đạt 98.9%.

---

## 3. Bảng ánh xạ trường dữ liệu

| Canonical field  | Ý nghĩa            | Cột tương ứng trong CSV mẫu | Dùng để          |
|------------------|--------------------|-----------------------------|------------------|
| `supplier_id`    | ID định danh       | *(dùng MST)*                | Khoá hàng đợi    |
| `name`           | Tên công ty ⚠️ bắt buộc | `Ten cong ty`          | SBERT + lexical  |
| `mst`            | Mã số thuế         | `MST`                       | Hiển thị         |
| `email`          | Email liên hệ      | `Email`                     | Outreach         |
| `phone`          | Số điện thoại      | `SDT`                       | Outreach         |
| `main_industry`  | Ngành chính        | `Nganh chinh`               | SBERT + lexical  |
| `sub_industry`   | Ngành phụ          | `Nganh phu`                 | Lexical          |
| `address`        | Địa chỉ            | `Dia chi`                   | Hiển thị         |
| `city`           | Tỉnh/Thành         | `Tinh/Thanh`                | Điểm vị trí      |
| `type`           | Loại hình          | `Loai hinh`                 | Hiển thị         |
| `description`    | Mô tả / sản phẩm   | `Mo ta`                     | SBERT            |
| `industry_group` | Nhóm ngành         | `Nhom nganh`                | Lexical          |
| `classification` | Nhóm phân loại     | `Nhóm phân loại`            | Lexical          |
| `website`        | Website            | *(không có)*                | Hiển thị         |

---

## 4. Hai nhánh matching và kênh tiếp cận

Kết quả matching của cả hai nhánh vào chung bảng `buyer_supplier_matches`
(trong `b2b_harvester/b2b_harvester.db`), phân biệt bằng cột `outreach_channel`:

| Nguồn bài đăng buyer                     | Script                  | `outreach_channel`  | Kênh tiếp cận       |
|------------------------------------------|-------------------------|---------------------|---------------------|
| Facebook group                           | `fb_matching_bot.py`    | `facebook_comment`  | Comment vào bài viết|
| TradeWheel, EC21, GlobalSources, Go4WB   | `ecommerce_matching.py` | `email`             | Email marketing     |

Mỗi dòng là một cặp *(bài đăng buyer × doanh nghiệp phù hợp)* kèm điểm số chi
tiết và `outreach_status` (`pending` → `sent` / `failed`). Bước gửi thật chỉ cần
đọc hàng đợi này:

```python
db.get_pending_matches("email")             # gom nhóm theo buyer
db.get_pending_matches("facebook_comment")
db.mark_match_sent(match_id)                # sau khi gửi xong
```

Xem thống kê hàng đợi:

```bash
python ecommerce_matching.py --stats
```

---

## 4b. Dịch bài đăng buyer (Anh → Việt)

Bài đăng trên các trang B2B e-commerce viết bằng tiếng Anh, còn mô tả doanh nghiệp
trong Supabase là tiếng Việt và `vietnamese-sbert` là model đơn ngữ. Không dịch thì
điểm ngữ nghĩa gần như vô nghĩa. Package [translation/](translation/README.md) xử lý
việc này, bật mặc định trong `ecommerce_matching.py`.

Bài đăng Facebook đã là tiếng Việt nên được tự động bỏ qua, không tốn công dịch.

```bash
python -m translation.cli --buyers 5        # xem thử bản dịch bài đăng thật
python -m translation.cli --stats           # thống kê cache dịch
python ecommerce_matching.py --no-translate # tắt dịch cho một lần chạy
```

Chi tiết kiến trúc, cách chọn model và kết quả kiểm chứng: [translation/README.md](translation/README.md).

---

## 5. Lệnh thường dùng

```bash
# Nhánh B2B e-commerce
python ecommerce_matching.py                      # match buyer chưa xử lý
python ecommerce_matching.py --limit 20           # 20 buyer mới nhất
python ecommerce_matching.py --source tradewheel  # lọc theo nền tảng
python ecommerce_matching.py --all                # match lại cả buyer cũ
python ecommerce_matching.py --top-n 5 --min-score 0.35
python ecommerce_matching.py --export ket_qua.csv
python ecommerce_matching.py --stats

# Kiểm tra Supabase
python -m datasource.introspect
python -m datasource.introspect --table ten_bang_khac
python -m datasource.introspect --list-tables

# Trong Discord (bot Facebook)
!match_status     # xem nguồn dữ liệu + số DN đã index
!match_reload     # tải lại DN từ Supabase, không cần restart bot
```

---

## 6. Xử lý sự cố

| Hiện tượng | Nguyên nhân & cách xử lý |
|------------|--------------------------|
| `Thiếu SUPABASE_URL hoặc SUPABASE_KEY` | Chưa có file `.env` ở thư mục gốc, hoặc chưa cài `python-dotenv` (`pip install python-dotenv`). |
| `Bảng '...' rỗng hoặc RLS đang chặn` | Sai tên bảng, hoặc `anon` key không có quyền đọc. Chạy `--list-tables`, hoặc đổi sang `service_role` key. |
| `Không dò được cột cho trường bắt buộc: name` | Tên cột quá khác thường. Chạy `python -m datasource.introspect` rồi điền `SUPPLIER_COL_NAME=` vào `.env`. |
| Chỉ lấy được 1000 dòng | PostgREST giới hạn mặc định. Hệ thống đã tự phân trang; nếu vẫn thiếu, kiểm tra `max-rows` trong cấu hình API của project. |
| Chạy chậm ở lần khởi động đầu | Đang encode embeddings lần đầu. Các lần sau dùng cache trong `.cache/`. |
| Supabase lỗi mạng khi đang chạy | Hệ thống tự dùng snapshot offline gần nhất trong `.cache/suppliers_supabase_*.json` và ghi cảnh báo, thay vì dừng bot. |
| Muốn quay lại dữ liệu mẫu | Đặt `SUPPLIER_SOURCE=csv` trong `.env`. |
