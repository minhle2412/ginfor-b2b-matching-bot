"""
Executive Leader Report Generator for B2B Harvester System
Generates human-readable summary reports (Markdown, HTML, and CSV) specifically
designed to present project results and insights to Team Leaders and Management.

Outputs:
1. leader_summary_report.md
2. leader_summary_report.html
3. leader_summary_report.csv
"""

import sqlite3
import csv
import json
import logging
from pathlib import Path
from database import DatabaseManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("b2b_harvester.leader_report")

def generate_reports():
    db = DatabaseManager()
    conn = db.get_connection()
    cursor = conn.cursor()

    # 1. Fetch Summary Stats
    cursor.execute("SELECT COUNT(*) FROM buyers")
    total_buyers = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM suppliers_vietnam")
    total_suppliers = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM supplier_posts")
    total_supplier_posts = cursor.fetchone()[0]

    # Stats by Platform for Buyers
    cursor.execute("SELECT source_platform, COUNT(*) as cnt FROM buyers GROUP BY source_platform")
    buyers_by_platform = dict(cursor.fetchall())

    # Stats by Platform for Supplier Posts
    cursor.execute("SELECT source_platform, COUNT(*) as cnt FROM supplier_posts GROUP BY source_platform")
    posts_by_platform = dict(cursor.fetchall())

    # Top Buyer Countries
    cursor.execute("SELECT buyer_country, COUNT(*) as cnt FROM buyers WHERE buyer_country != '' GROUP BY buyer_country ORDER BY cnt DESC LIMIT 5")
    top_buyer_countries = cursor.fetchall()

    # Sample Buyers (clean text, max 10)
    cursor.execute("SELECT title, source_platform, buyer_country, quantity, contact_email, contact_phone, detail_url FROM buyers ORDER BY created_at DESC LIMIT 10")
    sample_buyers = cursor.fetchall()

    # Sample Supplier Enterprise Directory (max 10)
    cursor.execute("SELECT company_name, mst_tax_code, main_products, province_city, contact_phone, contact_email, website FROM suppliers_vietnam ORDER BY created_at DESC LIMIT 10")
    sample_suppliers = cursor.fetchall()

    # Sample Supplier Sell Posts (max 10)
    cursor.execute("SELECT source_platform, company_name, product_title, category, moq_price, contact_info, detail_url FROM supplier_posts ORDER BY created_at DESC LIMIT 10")
    sample_supplier_posts = cursor.fetchall()

    conn.close()

    base_dir = Path(__file__).resolve().parent

    # ==================== 1. GENERATE MARKDOWN REPORT ====================
    md_content = f"""# 📊 BÁO CÁO TỔNG QUAN DỮ LIỆU B2B HARVESTER (TRÌNH LEADER)

**Dự án**: Hệ thống cào dữ liệu B2B tự động kết nối với website **thongtincty.com**  

---

## I. TỔNG QUAN BÁO CÁO DỮ LIỆU (EXECUTIVE SUMMARY)

| Chỉ Số Thống Kê | Số Lượng Thu Thập | Mô Tả Chi Tiết |
| :--- | :---: | :--- |
| 🛒 **Tổng số Buyer Leads (Nhu cầu mua)** | **{total_buyers:,}** | Bài đăng nhu cầu mua từ các sàn B2B quốc tế (Phase 1) |
| 🏭 **Tổng số Doanh Nghiệp VN Xuất Khẩu** | **{total_suppliers:,}** | Danh bạ doanh nghiệp sản xuất/xuất khẩu Việt Nam (Phase 2) |
| 📦 **Tổng số Bài Đăng Bán Hàng (Sell Offers)** | **{total_supplier_posts:,}** | Bài chào hàng xuất khẩu sản phẩm chủ lực từ 4 nguồn B2B |

---

## II. PHÂN PHỐI DỮ LIỆU THEO NGUỒN (PLATFORM DISTRIBUTION)

### 1. Nguồn Nhu Cầu Mua Hàng (Buyers)
"""
    for platform, count in buyers_by_platform.items():
        md_content += f"- **{platform.upper()}**: {count:,} bài đăng\n"

    md_content += "\n### 2. Nguồn Bài Đăng Bán Hàng (Supplier Sell Posts)\n"
    for platform, count in posts_by_platform.items():
        md_content += f"- **{platform.upper()}**: {count:,} chào hàng xuất khẩu\n"

    md_content += "\n### 3. Quốc gia người mua tiềm năng hàng đầu\n"
    for row in top_buyer_countries:
        md_content += f"- **{row['buyer_country']}**: {row['cnt']:,} nhu cầu mua\n"

    md_content += """

---

## III. MẪU BÀI ĐĂNG BÁN HÀNG CỦA DOANH NGHIỆP VIỆT NAM (SUPPLIER SELL POSTS)

| STT | Nguồn | Doanh Nghiệp Việt Nam | Bài Đăng Chào Hàng | Ngành Hàng | Giá / MOQ | Thông Tin Liên Hệ | Link Bài Đăng |
| :---: | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
"""
    for idx, sp in enumerate(sample_supplier_posts, 1):
        md_content += f"| {idx} | `{sp['source_platform']}` | {sp['company_name'][:40]} | {sp['product_title'][:45]} | {sp['category']} | {sp['moq_price']} | {sp['contact_info'] or 'Có trong DB'} | [Link Gốc]({sp['detail_url']}) |\n"

    md_content += """

---

## IV. MẪU DỮ LIỆU BUYER LEADS TIÊU BIỂU (NHU CẦU MUA QUỐC TẾ)

| STT | Nguồn | Tiêu Đề Nhu Cầu | Quốc Gia | Số Lượng | Email / SĐT Liên Hệ | Link Gốc |
| :---: | :--- | :--- | :---: | :---: | :--- | :--- |
"""
    for idx, b in enumerate(sample_buyers, 1):
        contact_str = f"{b['contact_email']} {b['contact_phone']}".strip() or "Chờ mở khóa"
        md_content += f"| {idx} | `{b['source_platform']}` | {b['title'][:60]} | {b['buyer_country'] or 'Global'} | {b['quantity'] or 'N/A'} | {contact_str} | [Xem chi tiết]({b['detail_url']}) |\n"

    md_content += """

---

## V. MẪU DANH BẠ DOANH NGHIỆP VIỆT NAM XUẤT KHẨU (ENTERPRISE DIRECTORY)

| STT | Mã Số Thuế | Tên Công Ty Việt Nam | Ngành Sản Xuất / Xuất Khẩu | Tỉnh / Thành | SĐT / Email |
| :---: | :---: | :--- | :--- | :---: | :--- |
"""
    for idx, s in enumerate(sample_suppliers, 1):
        contact_str = f"{s['contact_phone']} {s['contact_email']}".strip() or "Đã lưu DB"
        md_content += f"| {idx} | `{s['mst_tax_code'] or 'N/A'}` | {s['company_name'][:45]} | {s['main_products'][:40]} | {s['province_city']} | {contact_str} |\n"

    md_path = base_dir / "leader_summary_report.md"
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(md_content)
    logger.info(f"✅ Generated Markdown Leader Report: {md_path}")


    # ==================== 2. GENERATE CLEAN CSV FOR LEADER ====================
    csv_path = base_dir / "leader_summary_report.csv"
    with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["Loai_Du_Lieu", "Nguon_San", "Tieu_De_Doanh_Nghiep", "Nganh_Hang_Mo_Ta", "Quoc_Gia_Tinh_Thanh", "So_Luong_MOQ", "Email_SDT_Lien_He", "Link_Url"])
        
        # Write Supplier Posts
        for sp in sample_supplier_posts:
            writer.writerow(["SUPPLIER_SELL_POST", sp['source_platform'], sp['company_name'], sp['product_title'], "Vietnam", sp['moq_price'], sp['contact_info'], sp['detail_url']])

        # Write Buyers
        for b in sample_buyers:
            writer.writerow(["BUYER_LEAD", b['source_platform'], b['title'], "Nhu cầu nhập khẩu", b['buyer_country'], b['quantity'], f"{b['contact_email']} {b['contact_phone']}".strip(), b['detail_url']])

        # Write Suppliers
        for s in sample_suppliers:
            writer.writerow(["SUPPLIER_DIRECTORY", "thongtincty_db", s['company_name'], s['main_products'], s['province_city'], "Sản xuất/Xuất khẩu", f"{s['contact_phone']} {s['contact_email']}".strip(), s['website']])

    logger.info(f"✅ Generated Leader Summary CSV Table: {csv_path}")

    # ==================== 3. GENERATE EXECUTIVE HTML REPORT ====================
    html_content = f"""<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <title>Báo Cáo Tổng Quan Dữ Liệu B2B Harvester</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; margin: 30px; background-color: #f8fafc; color: #0f172a; }}
        h1, h2 {{ color: #1e293b; border-bottom: 2px solid #e2e8f0; padding-bottom: 8px; }}
        .card-container {{ display: flex; gap: 20px; margin-bottom: 25px; }}
        .card {{ background: white; border-radius: 8px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); flex: 1; text-align: center; border-top: 4px solid #2563eb; }}
        .card .number {{ font-size: 32px; font-weight: bold; color: #2563eb; margin-top: 5px; }}
        table {{ width: 100%; border-collapse: collapse; background: white; margin-bottom: 30px; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }}
        th, td {{ padding: 12px 15px; text-align: left; border-bottom: 1px solid #e2e8f0; font-size: 14px; }}
        th {{ background-color: #f1f5f9; font-weight: 600; color: #334155; }}
        tr:hover {{ background-color: #f8fafc; }}
        a {{ color: #2563eb; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
        .badge {{ background: #e0f2fe; color: #0369a1; padding: 3px 8px; border-radius: 12px; font-size: 12px; font-weight: 500; }}
    </style>
</head>
<body>
    <h1>📊 BÁO CÁO KẾT QUẢ CÀO DỮ LIỆU B2B HARVESTER</h1>
    <p><i>Phục vụ kết nối doanh nghiệp B2B và tích hợp sản phẩm thongtincty.com</i></p>

    <div class="card-container">
        <div class="card">
            <div>🛒 TỔNG BUYER LEADS (PHASE 1)</div>
            <div class="number">{total_buyers:,}</div>
        </div>
        <div class="card" style="border-top-color: #059669;">
            <div>📦 BÀI ĐĂNG BÁN HÀNG SUPPLIER</div>
            <div class="number" style="color: #059669;">{total_supplier_posts:,}</div>
        </div>
        <div class="card" style="border-top-color: #d97706;">
            <div>🏭 DOANH NGHIỆP VN XUẤT KHẨU</div>
            <div class="number" style="color: #d97706;">{total_suppliers:,}</div>
        </div>
    </div>

    <h2>I. Mẫu Bài Đăng Bán Hàng Của DN Việt Nam (Supplier Product Sell Offers)</h2>
    <table>
        <thead>
            <tr>
                <th>STT</th>
                <th>Sàn B2B</th>
                <th>Doanh Nghiệp Việt Nam</th>
                <th>Bài Đăng Chào Hàng / Sản Phẩm</th>
                <th>Ngành Hàng</th>
                <th>Giá / MOQ</th>
                <th>Liên Hệ</th>
                <th>Link Gốc</th>
            </tr>
        </thead>
        <tbody>
"""
    for idx, sp in enumerate(sample_supplier_posts, 1):
        html_content += f"""
            <tr>
                <td>{idx}</td>
                <td><span class="badge">{sp['source_platform']}</span></td>
                <td><b>{sp['company_name']}</b></td>
                <td>{sp['product_title']}</td>
                <td>{sp['category']}</td>
                <td>{sp['moq_price']}</td>
                <td>{sp['contact_info']}</td>
                <td><a href="{sp['detail_url']}" target="_blank">Xem chào hàng</a></td>
            </tr>"""

    html_content += """
        </tbody>
    </table>

    <h2>II. Mẫu Nhu Cầu Mua Hàng Quốc Tế (Buyer Leads - Phase 1)</h2>
    <table>
        <thead>
            <tr>
                <th>STT</th>
                <th>Sàn B2B</th>
                <th>Tiêu Đề Nhu Cầu Mua</th>
                <th>Quốc Gia</th>
                <th>Số Lượng Yêu Cầu</th>
                <th>Thông Tin Liên Hệ</th>
                <th>Link Gốc</th>
            </tr>
        </thead>
        <tbody>
"""
    for idx, b in enumerate(sample_buyers, 1):
        contact_str = f"{b['contact_email']} {b['contact_phone']}".strip() or "Chờ mở khóa"
        html_content += f"""
            <tr>
                <td>{idx}</td>
                <td><span class="badge">{b['source_platform']}</span></td>
                <td><b>{b['title']}</b></td>
                <td>{b['buyer_country'] or 'Global'}</td>
                <td>{b['quantity'] or 'Theo thỏa thuận'}</td>
                <td>{contact_str}</td>
                <td><a href="{b['detail_url']}" target="_blank">Xem bài đăng</a></td>
            </tr>"""

    html_content += """
        </tbody>
    </table>
</body>
</html>
"""

    html_path = base_dir / "leader_summary_report.html"
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    logger.info(f"✅ Generated Executive HTML Report: {html_path}")

if __name__ == "__main__":
    generate_reports()
