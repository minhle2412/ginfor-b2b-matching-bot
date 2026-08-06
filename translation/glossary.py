# -*- coding: utf-8 -*-
"""
Từ điển thuật ngữ B2B xuất nhập khẩu Anh → Việt.
==================================================
Model NMT phổ thông hay dịch sai thuật ngữ ngành ("broken rice" → "gạo vỡ" thay vì
"tấm", "cashew kernel" → "hạt nhân điều" thay vì "nhân hạt điều"). Từ điển này có
hai vai trò:

1. **Bổ sung sau khi dịch** (`augment_with_glossary`): nối thêm các thuật ngữ tiếng
   Việt chuẩn ngành vào cuối bản dịch. Nhờ vậy tầng lexical của Matching Engine bắt
   được đúng từ khoá ngành nghề mà doanh nghiệp dùng để mô tả mình, kể cả khi câu
   dịch của NMT không dùng từ đó.

2. **Dự phòng khi không có model** (`glossary_translate`): thay thế từng thuật ngữ,
   vẫn tốt hơn là để nguyên tiếng Anh.
"""

import re

#: Thuật ngữ tiếng Anh → các cách gọi tiếng Việt (cách gọi đầu tiên là chuẩn nhất).
#: Khoá phải viết thường. Ưu tiên cụm dài trước khi khớp (xem _SORTED_KEYS).
B2B_GLOSSARY: dict[str, list[str]] = {
    # --- Nông sản & lương thực ---
    "rice": ["gạo"],
    "white rice": ["gạo trắng"],
    "long grain rice": ["gạo hạt dài"],
    "broken rice": ["tấm", "gạo tấm"],
    "jasmine rice": ["gạo thơm jasmine"],
    "glutinous rice": ["gạo nếp"],
    "brown rice": ["gạo lứt"],
    "parboiled rice": ["gạo đồ"],
    "paddy": ["lúa"],
    "coffee": ["cà phê"],
    "robusta coffee": ["cà phê robusta"],
    "arabica coffee": ["cà phê arabica"],
    "green coffee beans": ["cà phê nhân"],
    "instant coffee": ["cà phê hoà tan"],
    "cashew": ["hạt điều"],
    "cashew nut": ["hạt điều"],
    "cashew kernel": ["nhân hạt điều"],
    "raw cashew nut": ["hạt điều thô"],
    "pepper": ["hạt tiêu", "tiêu"],
    "black pepper": ["tiêu đen"],
    "white pepper": ["tiêu trắng"],
    "cinnamon": ["quế"],
    "star anise": ["hoa hồi"],
    "spices": ["gia vị"],
    "tea": ["chè", "trà"],
    "rubber": ["cao su"],
    "natural rubber": ["cao su thiên nhiên"],
    "cassava": ["sắn", "khoai mì"],
    "tapioca starch": ["tinh bột sắn"],
    "corn": ["ngô", "bắp"],
    "maize": ["ngô", "bắp"],
    "soybean": ["đậu tương", "đậu nành"],
    "peanut": ["lạc", "đậu phộng"],
    "sesame": ["vừng", "mè"],
    "coconut": ["dừa"],
    "desiccated coconut": ["cơm dừa sấy"],
    "coconut oil": ["dầu dừa"],
    "dragon fruit": ["thanh long"],
    "banana": ["chuối"],
    "mango": ["xoài"],
    "lychee": ["vải thiều"],
    "longan": ["nhãn"],
    "durian": ["sầu riêng"],
    "passion fruit": ["chanh dây"],
    "pineapple": ["dứa", "thơm"],
    "dried fruit": ["trái cây sấy"],
    "fresh fruit": ["trái cây tươi"],
    "vegetables": ["rau củ"],
    "honey": ["mật ong"],
    "sugar": ["đường"],
    "salt": ["muối"],
    "flour": ["bột mì"],
    "animal feed": ["thức ăn chăn nuôi"],
    "fertilizer": ["phân bón"],

    # --- Thuỷ sản ---
    "seafood": ["thuỷ sản", "hải sản"],
    "frozen seafood": ["thuỷ sản đông lạnh"],
    "shrimp": ["tôm"],
    "prawn": ["tôm"],
    "vannamei shrimp": ["tôm thẻ chân trắng"],
    "black tiger shrimp": ["tôm sú"],
    "pangasius": ["cá tra"],
    "basa fish": ["cá basa"],
    "tuna": ["cá ngừ"],
    "squid": ["mực"],
    "octopus": ["bạch tuộc"],
    "crab": ["cua"],
    "fish fillet": ["phi lê cá"],
    "fish meal": ["bột cá"],

    # --- Dệt may & da giày ---
    "garment": ["may mặc", "hàng may mặc"],
    "apparel": ["quần áo", "hàng may mặc"],
    "textile": ["dệt may"],
    "fabric": ["vải"],
    "cotton": ["cotton", "bông"],
    "yarn": ["sợi"],
    "t-shirt": ["áo thun"],
    "uniform": ["đồng phục"],
    "workwear": ["quần áo bảo hộ"],
    "sportswear": ["đồ thể thao"],
    "underwear": ["đồ lót"],
    "footwear": ["giày dép"],
    "shoes": ["giày"],
    "sneakers": ["giày thể thao"],
    "leather": ["da"],
    "handbag": ["túi xách"],
    "backpack": ["ba lô"],
    "socks": ["tất", "vớ"],

    # --- Gỗ & thủ công mỹ nghệ ---
    "wood": ["gỗ"],
    "timber": ["gỗ"],
    "plywood": ["gỗ dán", "ván ép"],
    "wooden furniture": ["đồ gỗ nội thất"],
    "furniture": ["nội thất", "đồ nội thất"],
    "handicraft": ["thủ công mỹ nghệ"],
    "rattan": ["mây"],
    "bamboo": ["tre"],
    "ceramic": ["gốm sứ"],
    "pottery": ["gốm"],
    "lacquerware": ["sơn mài"],

    # --- Bao bì, nhựa, hoá chất ---
    "packaging": ["bao bì"],
    "carton box": ["thùng carton"],
    "paper": ["giấy"],
    "plastic": ["nhựa"],
    "plastic resin": ["hạt nhựa"],
    "pvc": ["nhựa PVC"],
    "chemical": ["hoá chất"],
    "paint": ["sơn"],
    "adhesive": ["keo dán"],
    "lubricant": ["dầu nhớt", "dầu bôi trơn"],

    # --- Công nghiệp, xây dựng, điện tử ---
    "steel": ["thép"],
    "stainless steel": ["thép không gỉ", "inox"],
    "iron": ["sắt"],
    "aluminium": ["nhôm"],
    "aluminum": ["nhôm"],
    "copper": ["đồng"],
    "cement": ["xi măng"],
    "construction material": ["vật liệu xây dựng"],
    "tiles": ["gạch men"],
    "granite": ["đá granite"],
    "machinery": ["máy móc"],
    "spare parts": ["phụ tùng"],
    "electronics": ["điện tử"],
    "electronic components": ["linh kiện điện tử"],
    "cable": ["dây cáp"],
    "solar panel": ["tấm pin năng lượng mặt trời"],
    "battery": ["pin", "ắc quy"],
    "led light": ["đèn LED"],
    "medical equipment": ["thiết bị y tế"],
    "cosmetics": ["mỹ phẩm"],
    "pharmaceutical": ["dược phẩm"],

    # --- Thuật ngữ giao dịch ---
    "supplier": ["nhà cung cấp"],
    "manufacturer": ["nhà sản xuất"],
    "factory": ["nhà máy", "xưởng"],
    "exporter": ["nhà xuất khẩu"],
    "importer": ["nhà nhập khẩu"],
    "distributor": ["nhà phân phối"],
    "wholesaler": ["nhà bán sỉ"],
    "trading company": ["công ty thương mại"],
    "oem": ["gia công OEM"],
    "odm": ["gia công ODM"],
    "private label": ["nhãn hàng riêng"],
    "moq": ["số lượng đặt hàng tối thiểu"],
    "minimum order quantity": ["số lượng đặt hàng tối thiểu"],
    "rfq": ["yêu cầu báo giá"],
    "request for quotation": ["yêu cầu báo giá"],
    "quotation": ["báo giá"],
    "wholesale": ["bán sỉ", "bán buôn"],
    "bulk": ["số lượng lớn"],
    "export": ["xuất khẩu"],
    "import": ["nhập khẩu"],
    "logistics": ["logistics", "vận chuyển"],
    "freight forwarding": ["giao nhận vận tải"],
    "customs clearance": ["thông quan"],
    "container": ["container"],
    "certification": ["chứng nhận"],
    "organic": ["hữu cơ"],
    "haccp": ["chứng nhận HACCP"],
    "iso": ["chứng nhận ISO"],
}

#: Khớp cụm dài trước để "broken rice" không bị "rice" nuốt mất.
_SORTED_KEYS = sorted(B2B_GLOSSARY, key=len, reverse=True)

#: Regex khớp toàn bộ thuật ngữ trong một lượt quét
_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in _SORTED_KEYS) + r")\b",
    re.IGNORECASE,
)


def find_terms(text: str) -> list[str]:
    """
    Tìm các thuật ngữ B2B tiếng Anh xuất hiện trong văn bản.
    Cụm dài được ưu tiên: "broken rice" chỉ trả về "broken rice", không kèm "rice".
    """
    if not text:
        return []

    found, occupied = [], []
    for match in _PATTERN.finditer(text):
        start, end = match.span()
        # Bỏ qua nếu nằm trong một cụm đã khớp trước đó (cụm dài hơn)
        if any(s <= start and end <= e for s, e in occupied):
            continue
        occupied.append((start, end))
        term = match.group(1).lower()
        if term not in found:
            found.append(term)
    return found


def augment_with_glossary(source_text: str, translated_text: str) -> str:
    """
    Nối thuật ngữ tiếng Việt chuẩn ngành vào cuối bản dịch.

    Chỉ thêm những thuật ngữ CHƯA xuất hiện trong bản dịch, tránh lặp từ làm
    lệch điểm lexical.

    Args:
        source_text: văn bản gốc tiếng Anh
        translated_text: bản dịch tiếng Việt từ model NMT

    Returns:
        Bản dịch đã bổ sung thuật ngữ, hoặc nguyên bản nếu không có gì để thêm.
    """
    terms = find_terms(source_text)
    if not terms:
        return translated_text

    lowered = translated_text.lower()
    additions = []
    for term in terms:
        for vi in B2B_GLOSSARY[term]:
            if vi.lower() not in lowered and vi not in additions:
                additions.append(vi)

    if not additions:
        return translated_text
    return f"{translated_text} {' '.join(additions)}".strip()


def glossary_translate(text: str) -> str:
    """
    Dịch thô bằng cách thay thế từng thuật ngữ (dùng khi không có model NMT).
    Phần văn bản không nằm trong từ điển được giữ nguyên tiếng Anh.
    """
    if not text:
        return text

    def _replace(match):
        return B2B_GLOSSARY[match.group(1).lower()][0]

    return _PATTERN.sub(_replace, text)
