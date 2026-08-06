# Plan: Đưa bài đăng buyer lên mục "Cơ hội" của thongtincty

> Bản kế hoạch — chưa triển khai. Khảo sát Supabase + phân tích dữ liệu: 06/08/2026.

## Tóm tắt quyết định

| | Quyết định |
|---|---|
| Kiến trúc | Dùng lại bảng `social_leads` đang chạy, **không tạo bảng mới** |
| Phân nhóm | Thêm trường `source_group`: `facebook` hoặc `website` |
| Hiển thị | Song ngữ — tiếng Việt trước, nguyên văn tiếng Anh bên dưới |
| Lên Cơ hội | Facebook → **duyệt tay** (giữ như hiện tại) · Website → **tự động** (có bộ lọc) |
| Vector | Giữ **cả hai loại**: OpenAI 1536 chiều + SBERT 768 chiều |

---

## Phần 1 — Tách 2 nhóm nguồn

Hiện `social_leads` chỉ có cột `platform` với một giá trị duy nhất `facebook_group`.
Ta thêm một cột phân loại **cấp cao hơn** để tách bạch hai nhóm, vì toàn bộ luồng xử
lý phía sau (duyệt tay hay tự động) phụ thuộc vào nó:

```
source_group = 'facebook'   ←  platform = 'facebook_group'
source_group = 'website'    ←  platform = 'go4worldbusiness' | 'ec21'
                                        | 'globalsources'    | 'tradewheel'
```

Vì sao tách thành cột riêng thay vì suy ra từ `platform`: quy tắc nghiệp vụ (duyệt tay
hay tự động) gắn với **nhóm**, không gắn với từng trang. Sau này thêm trang thứ 5 chỉ
cần gán đúng `source_group`, không phải sửa code ở mọi nơi.

```sql
alter table public.social_leads
  add column if not exists source_group text;

-- Gán cho 152 bài Facebook đang có
update public.social_leads
   set source_group = 'facebook'
 where source_group is null;

-- Từ nay bắt buộc phải có
alter table public.social_leads
  alter column source_group set default 'facebook',
  alter column source_group set not null;

alter table public.social_lead_sources
  add column if not exists source_group text not null default 'facebook';
```

Thêm 4 nguồn website, làm y như cách 5 nguồn Facebook đang được khai báo:

```sql
insert into public.social_lead_sources
  (platform, source_group, external_ref, name, enabled, scan_interval_minutes, filters, status)
values
  ('go4worldbusiness','website','go4worldbusiness','Go4WorldBusiness — RFQ quốc tế',true,1440,'{}'::jsonb,'active'),
  ('ec21',            'website','ec21',            'EC21 — RFQ quốc tế',            true,1440,'{}'::jsonb,'active'),
  ('globalsources',   'website','globalsources',   'GlobalSources — RFQ quốc tế',   true,1440,'{}'::jsonb,'active'),
  ('tradewheel',      'website','tradewheel',      'TradeWheel — RFQ quốc tế',      true,1440,'{}'::jsonb,'active');
```

Toàn bộ cột phân loại trong Supabase đều là **text tự do, không phải enum** (đã kiểm
tra qua OpenAPI spec), nên thêm giá trị mới không cần `ALTER TYPE`, không khoá bảng.

---

## Phần 2 — Thêm ô trống cho dữ liệu website

Tất cả đều **cho phép để trống**, nên 152 bài Facebook hiện có không bị ảnh hưởng.

```sql
alter table public.social_leads
  -- Tiêu đề riêng: bài RFQ có title tách biệt, bài Facebook thì không
  add column if not exists title            text,

  -- Song ngữ
  add column if not exists title_vi         text,
  add column if not exists content_vi       text,
  add column if not exists source_lang      text,   -- 'en' | 'vi'

  -- Điều khoản thương mại đặc thù RFQ quốc tế
  add column if not exists buyer_country    text,
  add column if not exists destination_port text,
  add column if not exists payment_terms    text,
  add column if not exists shipping_terms   text,
  add column if not exists contact_email    text,
  add column if not exists contact_phone    text,

  -- Vector cho matching engine nội bộ (xem phần 5)
  add column if not exists embedding_sbert  extensions.vector(768),

  -- Điểm chất lượng dùng cho tự động đăng (xem phần 4)
  add column if not exists quality_score    int;

create index if not exists idx_social_leads_group_status
  on public.social_leads (source_group, status, ingested_at desc);
```

**7 loại thông tin dùng lại ô có sẵn, không cần thêm:**

| Dữ liệu website | Ô có sẵn trong `social_leads` |
|---|---|
| `title` + `description` | `content` |
| `quantity` | `scale_or_quantity` |
| `buyer_name` | `author_name` |
| `detail_url` | `permalink_url` |
| `buyer_id` (mã MD5) | `external_post_id` |
| `category` | `product_or_service` |
| `posted_date` | `posted_at` |

**Bảng matching không cần sửa gì.** `social_lead_matches` dùng nguyên, vì `supplier_id`
trong hàng đợi nội bộ **chính là `company_profiles.id`** — khoá ngoại khớp sẵn.

---

## Phần 3 — Đẩy dữ liệu lên

Viết `sync_to_supabase.py`:

```
b2b_harvester.db · buyers (64 bài)      ──►  social_leads  (source_group='website')
.cache/translations.db (135 bản dịch)   ──►  title_vi, content_vi
buyer_supplier_matches (320 cặp)        ──►  social_lead_matches
```

- Ghi đè theo cặp `(platform, external_post_id)` — chạy lại nhiều lần không sinh bài trùng.
- Bắt buộc có `--dry-run` in trước số dòng sẽ thêm / sửa / bỏ qua.
- Bản dịch lấy từ cache đã có, **không phải dịch lại**.

⚠️ **Lưu ý:** `social_leads.source_id` là bắt buộc và trỏ tới `social_lead_sources`,
nên phải chạy xong phần 1 (tạo 4 nguồn) rồi mới đẩy được bài.

---

## Phần 4 — Lên Cơ hội: hai luồng khác nhau

### 4.1 Nhánh Facebook — giữ nguyên duyệt tay

Không đụng gì tới luồng hiện tại. Bài Facebook vẫn đi qua trạng thái
`processing → matched → converted` và cần người bấm duyệt.

### 4.2 Nhánh Website — tự động, nhưng phải có bộ lọc

> **Đây là chỗ tôi phải báo bạn một kết quả trái với dự đoán.**

Bạn nhận định bài từ website đa số là xuất nhập khẩu nên đáng tin hơn. Về **chủ đề**
thì đúng — không có spam đa cấp, tuyển dụng như bên Facebook. Nhưng về **độ đầy đủ
thông tin** thì dữ liệu thật cho thấy phân hoá rất mạnh:

| Nguồn | Số bài | Mô tả (trung vị) | Có số lượng | Đánh giá |
|---|---|---|---|---|
| Go4WorldBusiness | 20 | **374 ký tự** | 20/20 | ✅ RFQ đầy đủ, có thông số kỹ thuật, cảng đến, điều khoản thanh toán |
| EC21 | 40 | **46 ký tự** | 0/40 | ❌ Mô tả chỉ lặp lại tiêu đề |
| TradeWheel | 4 | **38 ký tự** | 0/4 | ❌ Tương tự EC21 |

Một bài EC21 điển hình, đây là **toàn bộ** nội dung:

```
Tiêu đề : We Buy Rice
Mô tả   : "Buy Lead Requirement: We Buy Rice"
Nước    : Global          ← không phải nước thật
```

Ngoài ra: **13/64 bài trùng nhau** (riêng "We Buy Rice" xuất hiện 8 lần), chỉ còn
khoảng 51 bài thực sự khác biệt. Và 0% bài có ngày đăng hay email liên hệ.

Nếu tự động đăng tất cả, **44/64 bài rỗng tuếch kiểu "Chúng tôi mua gạo" sẽ lên trang
Cơ hội**. Đó là lý do vẫn cần bộ lọc dù nguồn đáng tin hơn Facebook.

### 4.3 Bộ quy tắc lọc đề xuất

Chấm điểm độ đầy đủ thông tin, thang 100:

| Tiêu chí | Điểm |
|---|---|
| Mô tả ≥ 150 ký tự **và không chỉ lặp lại tiêu đề** | +30 |
| Mô tả ≥ 80 ký tự và không lặp tiêu đề | +15 |
| Có số lượng cần mua | +25 |
| Có điều khoản thanh toán | +15 |
| Có điều khoản vận chuyển / cảng đến (CIF, FOB, CNF…) | +10 |
| Xác định được ngành hàng | +10 |
| Nước của buyer cụ thể (không phải "Global") | +10 |

**Điều kiện bắt buộc** (không đạt là loại, bất kể điểm số):

- Chưa từng đăng (chống trùng bằng `content_hash`)
- Xác định được ngành hàng — vì `opportunities.field` cần có giá trị
- Mô tả không chỉ là bản sao của tiêu đề

**Ngưỡng đề xuất: 50 điểm.**

Kiểm chứng trên 64 bài thật:

```
Go4WorldBusiness :  20 bài — tất cả đạt 100 điểm  ✅ đăng
EC21             :  40 bài — tất cả  10 điểm      ❌ loại
TradeWheel       :   4 bài — tất cả  10 điểm      ❌ loại

→ 20/64 bài lên Cơ hội
```

Dữ liệu **phân cực hoàn toàn**, không có vùng xám: mọi ngưỡng từ 20 đến 100 đều cho
cùng một kết quả. Nghĩa là bộ lọc rất ổn định, không cần tinh chỉnh liên tục.

Nhóm bị loại **không bị xoá**, chỉ nằm ở trạng thái `not_need` kèm `quality_score`,
để bạn xem lại và duyệt tay nếu muốn.

### 4.4 Mapping sang bảng `opportunities`

Đã đối chiếu với cặp lead↔cơ hội thật đang có trên hệ thống:

| Cột `opportunities` | Lấy từ |
|---|---|
| `user_id` | `b7dd5ac2-6869-4625-9302-a0960eaf21d1` (tài khoản hệ thống) |
| `project_name` | `title_vi`, thiếu thì `summary` |
| `description` | Song ngữ (xem dưới) |
| `field` | `industry_section` — mã ngành VSIC, tra bảng `industry_sectors` |
| `location` | `location` |
| `investor_name` | `author_name` + `buyer_country`, vd *"TradeWheel Buyer — India"* |
| `source_url` | `permalink_url` |
| `source_type` | `'social_lead'` (FB) / `'b2b_ecommerce'` (website) |
| `stage` · `tag` · `currency` · `closed` · `images` | `'bid_invitation'` · `'ITB'` · `'VND'` · `false` · `[]` |

Nội dung song ngữ:

```html
<p>{bản tiếng Việt, đã escape}</p>
<hr>
<p><em>Nguyên văn (English):</em></p>
<p>{bản gốc tiếng Anh, đã escape}</p>
```

**Bắt buộc escape** trước khi bọc HTML — đây là nội dung người lạ viết trên mạng.

Sau khi tạo cơ hội: ghi ngược `opportunity_id` và đặt `status='converted'` **trong
cùng một giao dịch**. Tách rời thì lỗi giữa chừng sẽ để lại cơ hội mồ côi.

---

## Phần 5 — Vector: dùng cả hai loại

Bạn chọn tích hợp cả hai. Thiết kế:

| Cột | Loại | Số chiều | Dùng để làm gì |
|---|---|---|---|
| `embedding` | OpenAI `text-embedding-3-small` | 1536 | Đồng bộ với hệ thống thongtincty — tìm kiếm trên web, matching của đội vận hành |
| `embedding_sbert` | `keepitreal/vietnamese-sbert` | 768 | Matching engine nội bộ đang chạy (12.555 DN đã đánh chỉ mục sẵn) |

**Vì sao giữ cả hai chứ không bỏ một:**

- Bỏ SBERT: mất chỉ mục 12.555 doanh nghiệp đã dựng, phải sinh lại toàn bộ bằng OpenAI.
- Bỏ OpenAI: bài đăng không hoà vào hệ thống tìm kiếm sẵn có của thongtincty.

**Lợi ích bất ngờ của OpenAI embedding:** nó là model **đa ngữ** — so sánh trực tiếp
được câu tiếng Anh với mô tả tiếng Việt mà **không cần dịch**. Đây là cách giải quyết
tận gốc vấn đề lệch ngôn ngữ. Ta vẫn giữ phần dịch, vì cần bản tiếng Việt để **hiển
thị** song ngữ trên web, chứ không chỉ để matching.

**Chi phí** (`text-embedding-3-small`, $0.02 / 1 triệu token):

| Việc | Ước tính |
|---|---|
| 64 bài đăng buyer | ~13.000 token → **$0.0003** |
| 12.555 doanh nghiệp đang dùng | ~1,3 triệu token → **$0.03** |
| Toàn bộ 85.865 doanh nghiệp | ~8,6 triệu token → **$0.17** |

Chi phí không đáng kể. Cần `OPENAI_API_KEY`.

⚠️ **Lưu ý:** `company_profiles.embedding` hiện **rỗng 100%** trên cả 85.865 dòng.
Nghĩa là phía thongtincty đã tạo cột nhưng chưa sinh dữ liệu. Muốn matching bằng vector
OpenAI hoạt động thì phải sinh cho cả hai phía — nên xác nhận với đội vận hành xem họ
có kế hoạch làm chưa, tránh làm trùng.

---

## Phần 6 — Các bước triển khai

| # | Việc | Thời gian |
|---|---|---|
| 1 | Chạy SQL phần 1 + 2 (staging trước, rồi production) | 0,5 ngày |
| 2 | `sync_to_supabase.py` — đẩy 64 bài + 320 cặp match + bản dịch | 1 ngày |
| 3 | Sinh embedding OpenAI cho bài đăng và doanh nghiệp | 0,5 ngày |
| 4 | `publish_opportunities.py` — bộ lọc + tạo cơ hội, hai luồng riêng | 1 ngày |
| 5 | Chạy thử 3 bài → kiểm tra hiển thị → mở toàn bộ | 0,5 ngày |
| | **Tổng** | **3,5 ngày** |

---

## Phần 7 — Rủi ro

| Rủi ro | Mức | Cách xử lý |
|---|---|---|
| **Web lọc cứng theo `source_type`** → bài website vào đúng bảng nhưng không hiện | **Cao** | Câu hỏi số 1 phần 8 — phải hỏi trước khi bắt đầu |
| Tự động đăng bài chất lượng thấp | **Đã xử lý** | Bộ lọc phần 4.3 loại 44/64 bài; chạy thử 3 bài trước |
| Sửa bảng đang chạy | Trung bình | Mọi cột thêm đều cho phép trống; không sửa/xoá cột nào đang có; chạy staging trước |
| Trùng bài với hệ thống đang chạy | Trung bình | Ràng buộc `(platform, external_post_id)` duy nhất + `content_hash` |
| Nội dung người dùng phá vỡ HTML | Trung bình | Escape trước khi bọc thẻ `<p>` |
| Sinh embedding OpenAI cho 85.865 DN chạy lâu | Thấp | Chạy theo lô, có thể tiếp tục giữa chừng; chi phí $0,17 |

---

## Phần 8 — Câu hỏi cần đội thongtincty trả lời trước khi bắt đầu

1. **Mục Cơ hội trên web lọc bài theo điều kiện gì?** Nếu code web viết cứng
   `source_type = 'social_lead'` thì bài website sẽ không hiện. → Cần biết để chọn:
   thêm giá trị `'b2b_ecommerce'` hay dùng chung `'social_lead'`.
2. `b7dd5ac2-6869-4625-9302-a0960eaf21d1` có đúng là tài khoản hệ thống không?
3. Ai đang vận hành `social_leads`? Khâu tạo cơ hội mới đạt **2/152**, khâu outreach
   **0/372** — cần biết họ có đang làm dở không để tránh chồng chéo.
4. `content_hash` đang tính bằng công thức nào? Phải khớp thì chống trùng mới có tác dụng.
5. Đội có kế hoạch sinh `company_profiles.embedding` (đang rỗng 100%) không?
