# Product Requirements Document (PRD) — Ginfor B2B Matching & Automated Outreach System

## 1. Giới thiệu & Mục tiêu (Introduction & Objectives)
Dự án **Ginfor B2B Matching & Automated Outreach System** là giải pháp công nghệ toàn diện nhằm tự động hóa quy trình kết nối kinh doanh (B2B Matching) giữa người mua (buyer) và nhà cung cấp (supplier). Hệ thống tự động thu thập nhu cầu mua sắm công khai trên mạng xã hội, phân tích và đề xuất đối tác phù hợp nhất từ cơ sở dữ liệu doanh nghiệp có sẵn, đồng thời tự động soạn thảo tin nhắn tiếp cận thông qua các kênh tối ưu (Gmail, SMS, Facebook Comment).

### Mục tiêu chiến lược:
- **Tối ưu hóa quy trình kết nối B2B**: Chuyển đổi phương thức tìm kiếm đối tác thủ công sang tự động hoàn toàn, rút ngắn thời gian từ vài ngày xuống còn vài phút.
- **Tăng tỷ lệ chuyển đổi**: Gửi trực tiếp danh sách doanh nghiệp phù hợp kèm đầy đủ thông tin liên hệ ngay khi người mua phát sinh nhu cầu.
- **Tiếp cận đa kênh (Omnichannel Outreach)**: Đảm bảo khả năng tiếp cận người mua thông qua mọi thông tin liên hệ thu thập được.

---

## 2. Đối tượng sử dụng (Target Users)
1. **Bên có nhu cầu (Buyer)**: Cá nhân hoặc tổ chức đăng tin tìm kiếm nguồn hàng, nhà gia công hoặc đối tác B2B trên mạng xã hội.
2. **Nhà cung cấp (Supplier/Partner)**: Các doanh nghiệp Việt Nam nằm trong cơ sở dữ liệu của hệ thống, mong muốn nhận được cơ hội kinh doanh phù hợp.
3. **Quản trị viên hệ thống (Admin/Moderator)**: Người kiểm duyệt các kết quả matching, chỉnh sửa nội dung tin nhắn chào hàng trước khi phê duyệt gửi đi qua giao diện Discord.

---

## 3. Phạm vi sản phẩm (Product Scope)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          HỆ THỐNG GINFOR B2B                            │
├───────────────────┬──────────────────────┬──────────────────────────────┤
│ 1. THU THẬP       │ 2. XỬ LÝ & KHỚP NỐI  │ 3. TIẾP CẬN & PHÊ DUYỆT      │
│ - Facebook Scrap  │ - SBERT Intent Filter│ - Trích xuất SĐT/Email       │
│ - Pyppeteer Auto  │ - 3-Tier Matching    │ - Đa kênh SMS/Email/Comment  │
│ - Cookie-based    │ - Vector Database    │ - Discord Approve/Reject View│
└───────────────────┴──────────────────────┴──────────────────────────────┘
```

### 3.1. Phân hệ 1: Thu thập thông tin tự động (Scraper Module)
- **Tự động hóa trình duyệt**: Sử dụng Pyppeteer giả lập hành vi người dùng cuộn trang để vượt qua cơ chế tải động (lazy-loading) của Facebook.
- **Quản lý danh sách nhóm**: Hỗ trợ cấu hình danh sách hàng chục group Facebook B2B mục tiêu khác nhau.
- **Nhận diện & Lọc trùng**: Tự động bóc tách ID bài đăng và băm MD5 nội dung để loại bỏ các bài viết trùng lặp giữa các nhóm.

### 3.2. Phân hệ 2: Lọc ý định & Thuật toán khớp nối (Matching Engine)
- **Bộ lọc ý định mua hàng (SBERT Intent Filter)**: Chuyển đổi nội dung bài đăng thành không gian vector và so sánh độ tương đồng cosine với 41 mẫu nhu cầu chuẩn nhằm loại bỏ bài viết quảng cáo, tuyển dụng, spam.
- **Phễu lọc doanh nghiệp 3 tầng (3-Tier Funnel)**:
  - **Tầng 1 (Lexical Filter)**: So khớp từ khóa tần suất cao giữa nhu cầu và phân loại ngành nghề của doanh nghiệp để rút gọn tập dữ liệu lớn.
  - **Tầng 2 (Location Filter)**: Trích xuất địa danh Việt Nam từ bài đăng và ưu tiên khớp nối doanh nghiệp cùng khu vực hoạt động.
  - **Tầng 3 (Semantic Match)**: Dùng mô hình học sâu xếp hạng chính xác độ phù hợp dựa trên mô tả doanh nghiệp.

### 3.3. Phân hệ 3: Tự động tiếp cận đa kênh (Outreach Engine)
- **Trích xuất thông tin liên hệ**: Bóc tách số điện thoại di động, cố định và email trực tiếp từ bài đăng của người mua.
- **Quy tắc chọn kênh tự động**:
  - Ưu tiên 1: Gửi **SMS** nếu trích xuất được số điện thoại.
  - Ưu tiên 2: Gửi **Gmail** nếu có email và không có số điện thoại.
  - Mặc định: Gửi **Facebook Comment** phản hồi trực tiếp bài viết của người mua.
- **Soạn tin chuyên nghiệp**: Tự động điền danh sách 5 đối tác phù hợp nhất trực tiếp vào tin nhắn kèm lời mời truy cập `thongtincty.com` để mở rộng kết nối.

### 3.4. Phân hệ 4: Dashboard Quản trị & Điều khiển
- **Discord Bot Interface**:
  - Giao diện Admin để nhận thông báo thời gian thực về các match mới.
  - Xem và phê duyệt (Approve/Reject) tin nhắn tiếp cận thông qua nút bấm tương tác.
  - Các lệnh cấu hình nhanh: điều chỉnh ngưỡng lọc (`!match_threshold`), số lượng DN đề xuất (`!match_top`), trạng thái hệ thống (`!match_status`).
- **FastAPI Web Dashboard**:
  - Bản đồ dữ liệu các doanh nghiệp đang được lưu trữ.
  - Giao diện web chạy thử và xem trực quan kết quả khớp nối doanh nghiệp.

---

## 5. Lộ trình phát triển & Yêu cầu tương lai (Roadmap)
1. **Giai đoạn 1 (Hiện tại)**: Hoàn thành lõi matching thuật toán, công cụ trích xuất liên hệ đa kênh, giao diện tương duyệt trên Discord và mock senders.
2. **Giai đoạn 2**: Tích hợp các cổng kết nối API thực tế bao gồm Google OAuth2 (Gmail), Twilio/Vonage (SMS) và Facebook Graph API (Comments).
3. **Giai đoạn 3**: Nghiên cứu cải tiến hiệu năng matching lên dữ liệu 80.000 doanh nghiệp và tích hợp AI tạo sinh (LLM) để nâng cao chất lượng tóm tắt nhu cầu.
