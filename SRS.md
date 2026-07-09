# Software Requirements Specification (SRS) — Ginfor B2B Matching & Automated Outreach System

## 1. Kiến trúc hệ thống tổng thể (System Architecture)
Hệ thống được thiết kế theo mô hình kiến trúc phân lớp kết hợp mô hình Pipeline hướng sự kiện.

```
                  ┌───────────────────────────────┐
                  │      Facebook Group Data      │
                  └──────────────┬────────────────┘
                                 │ (Pyppeteer headlessly crawls)
                                 ▼
                  ┌───────────────────────────────┐
                  │      Scraper Module (Bot)     │
                  └──────────────┬────────────────┘
                                 │ (Post ID & content hash dedup)
                                 ▼
                  ┌───────────────────────────────┐
                  │  SBERT Intent Filter Module   │
                  └──────────────┬────────────────┘
                                 │ (Reject spam, sales, jobs)
                                 ▼
                  ┌───────────────────────────────┐
                  │      B2B Matching Engine      │
                  │   - Tier 1: Lexical Filter    │
                  │   - Tier 2: Location Match    │
                  │   - Tier 3: SBERT Cos Sim     │
                  └──────────────┬────────────────┘
                                 │ (Top 5 matched suppliers)
                                 ▼
                  ┌───────────────────────────────┐
                  │   Ginfor Outreach Engine      │
                  │   - Contact Extractor         │
                  │   - Channel Router            │
                  │   - Template Generator        │
                  └──────────────┬────────────────┘
                                 │
         ┌───────────────────────┴────────────────────────┐
         ▼ (Send preview)                                 ▼ (Expose APIs)
┌─────────────────────────────────┐             ┌─────────────────────────────────┐
│     Discord Admin Channel       │             │       FastAPI Web Admin         │
│   (Approve/Reject UI Buttons)   │             │   - /api/match endpoint         │
│                                 │             │   - Web Dashboard (UI)          │
└────────────────┬────────────────┘             └─────────────────────────────────┘
                 │
      ┌──────────┴──────────┐
      ▼ (Approve)           ▼ (Reject)
┌───────────┴───────────┐ ┌─────┴─────┐
│  Senders (SMS/Email)  │ │   Log &   │
│  (Stub logs & stubs)  │ │  Discard  │
└───────────────────────┘ └───────────┘
```

---

## 2. Đặc tả kỹ thuật các phân hệ (Component Specifications)

### 2.1. Phân hệ Scraper & Lọc trùng bài viết
- **Thu thập dữ liệu**: Trình duyệt Chromium được điều khiển qua `pyppeteer`, nạp cookie `c_user` và `xs` của Facebook từ tệp môi trường để vượt qua trang đăng nhập.
- **Phân tích nội dung**: Trích xuất mã ID bài viết gốc và nội dung dạng văn bản thô qua `BeautifulSoup4`.
- **Bộ lọc trùng (Deduplication)**: 
  - Lưu trữ 2000 bài viết gần nhất trong tệp JSON để so khớp ID bài viết.
  - Sử dụng hàm băm MD5 cho 80 ký tự đầu tiên của bài đăng để lọc trùng các bài viết chia sẻ chéo (cross-posts) giữa các nhóm.

### 2.2. Bộ lọc ý định mua hàng (SBERT Intent Filter)
- Nạp mô hình ngôn ngữ `keepitreal/vietnamese-sbert` vào bộ nhớ.
- Tạo ma trận vector mẫu bằng cách mã hóa trước 41 câu truy vấn ý định mua hàng mẫu (`PARTNER_QUERIES`).
- Khi phát hiện bài viết mới, tiến hành vector hóa và tính điểm tương đồng Cosine cực đại.
- Nếu điểm tương đồng tối đa nhỏ hơn `SIMILARITY_THRESHOLD` (mặc định: `0.55`), bài đăng bị bỏ qua.
- **Loại bỏ tin tuyển dụng & bán hàng**: Sử dụng mảng `NEGATIVE_KEYWORDS` để lọc phủ định nhanh (như: "tuyển dụng", "mô tả công việc", "tuyển sỉ", "giảm giá").

### 2.3. Thuật toán so khớp đối tác (B2B Matching Engine)
Khớp bài đăng với cơ sở dữ liệu `Business_dataset.csv` (gồm 9.630 doanh nghiệp) thông qua phễu lọc 3 tầng:
1. **Tầng 1 - Lọc Lexical**: Tokenize từ ngữ của nhu cầu và so sánh tập từ khóa ngành nghề chính/phụ của doanh nghiệp. Chỉ giữ lại top 300 doanh nghiệp có số lượng từ khóa trùng khớp cao nhất.
2. **Tầng 2 - Lọc Vị trí**: Sử dụng Regular Expression trích xuất các địa danh Việt Nam phổ biến trong bài đăng (HCM, Hà Nội, Bình Dương, v.v.). Doanh nghiệp cùng khu vực sẽ nhận điểm $S_{location} = 1.0$, ngược lại nhận $0.0$.
3. **Tầng 3 - So khớp ngữ nghĩa**: Sử dụng SBERT mã hóa mô tả doanh nghiệp của top 300 ứng viên, so sánh cosine với vector bài viết để nhận điểm $S_{semantic}$.
4. **Tính điểm tổng hợp**: 
   $$TotalScore = 0.50 \cdot S_{semantic} + 0.30 \cdot S_{lexical} + 0.20 \cdot S_{location}$$

### 2.4. Phân hệ Outreach & Senders
- **Trích xuất thông tin liên lạc**:
  - Số điện thoại: Regex `(?:\+84|0)(?:[\s.\-]?\d){9,10}` trích xuất các SĐT 10-11 chữ số, tự động chuyển đầu số `+84` về `0` và loại bỏ các chuỗi trùng với MST.
  - Email: Regex lọc chuẩn định dạng hòm thư điện tử toàn cầu.
- **Quy tắc Router**: Kênh gửi SMS được chọn nếu có SĐT, Gmail nếu có Email (và không có SĐT), FB Comment làm mặc định.
- **Biến đổi định dạng**:
  - SMS: Tự động loại bỏ dấu tiếng Việt (UTF-8 sang ASCII) để giảm dung lượng ký tự xuống dưới giới hạn 160 ký tự tiêu chuẩn.
  - Gmail: Soạn thảo mã HTML hiển thị bảng biểu chi tiết (Tên doanh nghiệp, MST, Ngành nghề, Địa chỉ, Liên hệ, Điểm phù hợp).

### 2.5. Giao diện phê duyệt Discord UI
- Sử dụng API `discord.Embed` định dạng các trường thông tin có cấu trúc.
- Tạo lớp `OutreachReviewView` kế thừa từ `discord.ui.View` chứa hai nút bấm tương tác:
  - Nút **Approve**: Đổi trạng thái `OutreachAction` thành `approved`, kích hoạt lớp gửi tin `BaseSender` tương ứng và cập nhật giao diện nút bấm thành Disabled.
  - Nút **Reject**: Hủy hành động gửi tin, cập nhật trạng thái `rejected`.

### 2.6. Trang quản trị Web (FastAPI)
- Khởi chạy Web Server bằng `uvicorn` trên cổng cấu hình `8000`.
- Endpoint `POST /api/match` nhận JSON yêu cầu matching thủ công, trả về danh sách đối tác phù hợp có cấu trúc.
- Endpoint `GET /` tải giao diện Dashboard xây dựng từ file `templates/index.html`.

---

## 3. Đặc tả cơ sở dữ liệu & Tệp cấu hình (Data & Storage)
- **Cơ sở dữ liệu doanh nghiệp**: File `Business_dataset.csv` chứa thông tin chi tiết của 9.630 doanh nghiệp.
- **Pickle Vector Index**: Tệp `Business_dataset.csv.embeddings.pkl` lưu trữ các vector nhúng (embeddings) được sinh ra từ SBERT để tránh mã hóa lại trên mỗi lần khởi động bot.
- **Tệp cấu hình**: `.env.bot.facebook` lưu trữ các khóa bí mật:
  - `DISCORD_TOKEN`: Token kết nối bot Discord.
  - `DISCORD_CHANNEL_ID`: Kênh nhận log kết quả matching.
  - `OUTREACH_REVIEW_CHANNEL_ID`: Kênh duyệt tin nhắn tiếp cận của Admin.
  - `FB_COOKIE_C_USER`, `FB_COOKIE_XS`: Cookies định danh đăng nhập Facebook.

---

## 4. Yêu cầu phi chức năng (Non-functional Requirements)
- **Tương thích phần cứng**: Hỗ trợ tăng tốc tính toán Tensor thông qua Apple Silicon GPU (`mps` device trong PyTorch).
- **Thời gian phản hồi**: Thời gian khớp nối dữ liệu và trích xuất tin nhắn chào hàng không được vượt quá 10 giây đối với tập dữ liệu 10.000 doanh nghiệp.
- **Bảo mật dữ liệu**: Các tệp chứa mã khóa bí mật, cookie định danh và dữ liệu thu thập thực tế phải được liệt kê đầy đủ trong tệp `.gitignore` để tránh rò rỉ lên các kho lưu trữ công cộng.
