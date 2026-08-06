# B2B Harvester — Hệ Thống Cào Dữ Liệu Tự Động Cho thongtincty.com

Module độc lập thu thập dữ liệu **Buyer (Phase 1)** và **Supplier Việt Nam (Phase 2)** từ 4 sàn B2B lớn:
1. **Go4WorldBusiness** (`https://www.go4worldbusiness.com/`)
2. **EC21** (`https://importer.ec21.com/` & `https://www.ec21.com/`)
3. **GlobalSources** (`https://www.globalsources.com/`)
4. **TradeWheel** (`https://www.tradewheel.com/buyers/`)

---

## 📌 Tính Độc Lập Dự Án
Tàn bộ mã nguồn và dữ liệu của **B2B Harvester** nằm gói gọn trong thư mục `b2b_harvester/`. Hệ thống chỉ kế thừa logic SBERT embedding và không thay đổi bất kỳ file nào của hệ thống B2B Matching Bot hoặc Discord Bot sẵn có.

---

## ⚙️ Hướng Dẫn Sử Dụng

### 1. Chạy cào dữ liệu ngay lập tức (Manual Run)
```bash
# Cào toàn bộ (Buyer & Supplier Việt Nam)
python3 run_harvester.py --phase all

# Chỉ cào Buyer Leads (Phase 1)
python3 run_harvester.py --phase 1 --keywords rice coffee cashew

# Chỉ cào Supplier Việt Nam (Phase 2)
python3 run_harvester.py --phase 2 --keywords garment seafood wood
```

### 2. Kích hoạt dịch vụ cào tự động định kỳ (Scheduler)
Dịch vụ Scheduler sẽ tự động:
- Cào **Buyer Leads (Phase 1)**: **1 ngày / 1 lần** vào lúc 07:00 AM ICT.
- Cào **Supplier Việt Nam (Phase 2)**: **1 tuần / 1 lần** (Thứ Hai lúc 08:00 AM ICT).

```bash
python3 scheduler.py
```

### 3. Xuất dữ liệu tích hợp vào website thongtincty.com
```bash
python3 export_thongtincty.py --buyers-out buyers.json --suppliers-out suppliers.csv
```

---

## 🗄️ Cấu Trúc Database (`b2b_harvester.db`)

- **Bảng `buyers`**: Lưu trữ toàn bộ thông tin nhu cầu người mua quốc tế (`buyer_id`, `source_platform`, `title`, `description`, `buyer_country`, `quantity`, `destination_port`, `payment_terms`, `detail_url`, `vector_embedding`).
- **Bảng `suppliers_vietnam`**: Lưu trữ thông tin doanh nghiệp Việt Nam xuất khẩu (`supplier_id`, `company_name`, `country`, `province_city`, `main_products`, `export_markets`, `contact_phone`, `contact_email`, `website`, `vector_embedding`).
