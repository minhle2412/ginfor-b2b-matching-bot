# Product Requirements Document (PRD) — Ginfor B2B Matching & Outreach Bot

## 1. Giới thiệu & Mục tiêu (Introduction & Objectives)
Hệ thống **Ginfor B2B Matching & Outreach Bot** là một nền tảng tự động kết nối nhu cầu giao dịch giữa các bên mua (buyer) và doanh nghiệp cung cấp (supplier) dựa trên dữ liệu mạng xã hội. 

Mục tiêu chính:
- **Tự động hóa phát hiện nhu cầu**: Quét và nhận diện các bài đăng có nhu cầu tìm nguồn cung cấp, đối tác hoặc sản phẩm trên các group Facebook B2B.
- **Khớp nối thông minh (B2B Matching)**: Tìm ra Top 5 doanh nghiệp phù hợp nhất từ cơ sở dữ liệu hơn 9.600 doanh nghiệp của hệ thống bằng công nghệ xử lý ngôn ngữ tự nhiên (Vietnamese SBERT).
- **Soạn thảo và tiếp cận tự động (Outreach)**: Trích xuất thông tin liên hệ của người mua để soạn thảo tin nhắn chào hàng chuyên nghiệp thông qua kênh tối ưu nhất (SMS, Gmail, hoặc Facebook Comment), giúp giới thiệu nhà cung cấp phù hợp nhất đến họ.

---

## 2. Đối tượng người dùng (Target Audience)
1. **Admin / Moderator (Người vận hành)**: Duyệt các tin nhắn tiếp cận khách hàng trên Discord trước khi hệ thống thực hiện gửi đi.
2. **Bên có nhu cầu (Buyer)**: Các cá nhân/doanh nghiệp đăng bài tìm đối tác trên Facebook, được nhận danh sách doanh nghiệp gợi ý miễn phí qua SMS/Gmail/FB Comment.
3. **Doanh nghiệp cung cấp (Supplier)**: Các công ty trong cơ sở dữ liệu của Ginfor được kết nối trực tiếp đến khách hàng có nhu cầu thực tế.

---

## 3. Danh sách tính năng chính (Feature Requirements)

### 3.1. Facebook Group Scraper (Thu thập dữ liệu)
- Tự động quét danh sách các Facebook group B2B đã cấu hình định kỳ hoặc theo yêu cầu.
- Sử dụng headless browser automation (Pyppeteer) để tải nội dung bài đăng động một cách an toàn.
- Trích xuất thông tin: ID bài đăng, URL, nội dung văn bản.

### 3.2. Lọc ý định mua hàng (Buyer Intent Filter)
- Sử dụng mô hình học sâu **Vietnamese SBERT** để so khớp ngữ nghĩa bài viết với tập câu hỏi mẫu tìm nguồn cung cấp.
- Bộ lọc từ khóa phủ định (`NEGATIVE_KEYWORDS`) để loại bỏ triệt để các bài đăng không mong muốn: bài chào hàng bán sỉ/lẻ, bài tuyển dụng nhân sự, spam, đa cấp.

### 3.3. B2B Matching Engine (So khớp đối tác)
- Thực hiện khớp nối qua 3 tầng (3-Funnel):
  1. **Tầng 1 (Lexical Filter)**: Lọc thô bằng từ khóa ngành nghề để rút gọn danh sách ứng viên (từ 9.600+ xuống top 300).
  2. **Tầng 2 (Location Filter)**: Nhận diện vị trí địa lý trong bài đăng (HCM, Hà Nội, Bình Dương...) để so khớp với khu vực hoạt động của doanh nghiệp.
  3. **Tầng 3 (Semantic Scoring)**: Sử dụng SBERT tính cosine similarity để xếp hạng chi tiết mức độ phù hợp.
- Trả về Top 5 doanh nghiệp có điểm matching cao nhất.

### 3.4. Ginfor Outreach Engine (Soạn tin tiếp cận)
- **Trích xuất thông tin**: Tự động nhận diện SĐT Việt Nam (di động/cố định) và email từ bài viết.
- **Lựa chọn kênh ưu tiên**:
  - Có SĐT $\rightarrow$ Ưu tiên kênh **SMS**.
  - Không có SĐT, có Email $\rightarrow$ Ưu tiên kênh **Gmail**.
  - Không có cả hai $\rightarrow$ Mặc định kênh **Facebook Comment**.
- **Soạn tin chuyên nghiệp**: Tự động sinh nội dung tin nhắn tiếng Việt chuẩn mực B2B. Đính kèm trực tiếp thông tin liên hệ của Top 5 đối tác và giới thiệu truy cập `thongtincty.com` để tìm kiếm thêm.

### 3.5. Discord UI Review (Giao diện phê duyệt)
- Gửi tin nhắn Embed chi tiết mô tả thông tin bài đăng gốc, nhu cầu, kênh gửi và toàn bộ nội dung tin nhắn preview lên Discord.
- Tích hợp 2 nút bấm tương tác: **Duyệt & Gửi (Approve)** và **Từ chối (Reject)** để quản trị viên quyết định trước khi gửi thật.

---

## 4. Kế hoạch phát triển (Roadmap)
- **Phase 1 (Hiện tại - Prototype)**: Đã hoàn thiện logic lõi, giao diện duyệt Discord và các bộ gửi tin mô phỏng (stubs).
- **Phase 2 (Tích hợp thực tế)**:
  - Tích hợp **Gmail API (OAuth2)** để gửi email tự động.
  - Tích hợp **Twilio/Vonage API** để gửi SMS tự động.
  - Tích hợp **Facebook Graph API** (yêu cầu Page Access Token + App Review) để tự động comment dưới bài viết.
- **Phase 3 (Tự động hóa hoàn toàn)**: Cấu hình ngưỡng tin cậy để tự động gửi mà không cần qua bước duyệt thủ công đối với các bài viết có điểm matching cực cao.
