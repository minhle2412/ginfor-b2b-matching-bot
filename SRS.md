# Software Requirements Specification (SRS) — Ginfor B2B Matching & Outreach Bot

## 1. Kiến trúc hệ thống (System Architecture)
Hệ thống được thiết kế theo dạng hướng sự kiện (Event-driven) và xử lý tuần tự theo luồng (Pipeline).

```
[ Facebook Groups ] 
       │ (Headless Chrome / Pyppeteer)
       ▼
[ Scraper Module ] ──► Lọc Buyer Intent (SBERT + Neg Keywords)
       │
       ▼ (Nếu là Buyer)
[ B2B Matching Engine ] (Funnel 3 tầng: Ngữ nghĩa + Từ khóa + Địa lý)
       │
       ▼ (Top 5 doanh nghiệp phù hợp)
[ Ginfor Outreach Engine ] (Trích xuất SĐT/Email & Soạn tin nhắn)
       │
       ▼ (Gửi tin nhắn duyệt)
[ Discord Review Channel ] (Embeds + Approve/Reject Buttons)
       │
  ┌────┴────────────┐
  ▼ (Approve)       ▼ (Reject)
[ Senders (Stubs) ]  [ Log & Cancel ]
```

---

## 2. Công nghệ sử dụng (Technology Stack)
- **Ngôn ngữ lập trình**: Python 3.10+
- **Thư viện AI**:
  - `sentence-transformers` (Vietnamese SBERT model: `keepitreal/vietnamese-sbert` - chạy tăng tốc phần cứng thông qua thiết bị `mps` trên Mac Silicon).
  - `scikit-learn` & `numpy` để tính toán khoảng cách vector.
- **Thư viện Crawler**:
  - `pyppeteer` (Headless Chrome Automation).
  - `beautifulsoup4` (Phân tích cấu trúc HTML).
- **Giao diện Chatbot**: `discord.py` phiên bản 2.x (hỗ trợ Discord UI Buttons & Views).
- **Lưu trữ cấu hình**: `python-dotenv`.

---

## 3. Cấu trúc dữ liệu chính (Data Structures)

### 3.1. Company (Doanh nghiệp)
```python
{
    "name": str,            # Tên công ty
    "mst": str,             # Mã số thuế
    "email": str,           # Địa chỉ email liên hệ
    "phone": str,           # Số điện thoại
    "main_industry": str,   # Ngành nghề chính
    "sub_industry": str,    # Ngành nghề phụ
    "address": str,         # Địa chỉ
    "city": str,            # Tỉnh/Thành phố
    "type": str,            # Loại hình doanh nghiệp
    "description": str,     # Mô tả năng lực/sản phẩm
}
```

### 3.2. OutreachAction (Hành động tiếp cận)
```python
class OutreachAction:
    post_id: str
    post_url: str
    post_text: str
    buyer_need_summary: str
    channel: OutreachChannel   # SMS | GMAIL | FACEBOOK_COMMENT
    recipient: str             # SĐT, Email hoặc URL bài đăng
    message_content: str       # Nội dung chính
    matches_used: list         # Danh sách 5 DN đã match
    fb_comment_content: str    # Comment mặc định kèm theo
    gmail_message: GmailMessage # Email chi tiết (nếu gửi bằng Gmail)
    status: str                # pending_review | approved | rejected | sent
```

---

## 4. Đặc tả thuật toán Matching (Matching Algorithm)

Điểm phù hợp tổng hợp (Total Score) được tính theo công thức:
$$TotalScore = w_{semantic} \cdot S_{semantic} + w_{lexical} \cdot S_{lexical} + w_{location} \cdot S_{location}$$

Trong đó, cấu hình trọng số mặc định:
- $w_{semantic} = 0.50$ (Điểm tương đồng vector ngữ nghĩa bằng SBERT)
- $w_{lexical} = 0.30$ (Điểm trùng khớp từ khóa ngành nghề)
- $w_{location} = 0.20$ (Điểm trùng khớp khu vực địa lý - $1.0$ nếu khớp hoặc không ghi rõ khu vực, $0.0$ nếu lệch khu vực)

---

## 5. Đặc tả mô-đun gửi tin nhắn (Outreach Senders)
Các bộ gửi tin trong giai đoạn prototype sử dụng các stubs:
- **`SMSSender`**: Loại bỏ dấu tiếng Việt (chuyển đổi ký tự UTF-8 về ASCII), kiểm tra độ dài tin nhắn và ghi nhận log console dạng `📱 [SMS STUB]`.
- **`GmailSender`**: Soạn thảo email dạng HTML đẹp có chứa bảng thông tin chi tiết của 5 đối tác và gửi qua email tạm thời `lenhatminh24122004@gmail.com`. Ghi log dạng `📧 [GMAIL STUB]`.
- **`FacebookCommentSender`**: Soạn comment quảng bá thương hiệu Ginfor và thongtincty.com, ghi log dạng `💬 [FB COMMENT STUB]`.

---

## 6. Yêu cầu phi chức năng (Non-Functional Requirements)
- **Bảo mật**: Các khóa bí mật (`DISCORD_TOKEN`, `FB_COOKIE_C_USER`, `FB_COOKIE_XS`) tuyệt đối không được đưa lên Git repo công khai. Phải lưu trữ trong `.env.bot.facebook` nằm trong danh mục `.gitignore`.
- **Tốc độ xử lý**: Quá trình khớp nối dữ liệu với 9.600+ doanh nghiệp phải hoàn thành dưới **10 giây** nhờ việc lưu cache embeddings dạng pickle (`Business_dataset.csv.embeddings.pkl`).
