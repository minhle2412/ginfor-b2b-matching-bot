# -*- coding: utf-8 -*-
"""
Kiểm thử module dịch.
======================
Chạy:  python -m translation.tests.test_translation

Không cần model NMT — dùng backend 'glossary' và backend giả lập, nên chạy nhanh
và không phụ thuộc mạng.
"""

import os
import sys
import tempfile

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE_DIR)

from translation.backends import GlossaryBackend, split_into_chunks   # noqa: E402
from translation.detect import detect_language                        # noqa: E402
from translation.glossary import augment_with_glossary, find_terms    # noqa: E402
from translation.preprocess import clean_boilerplate                  # noqa: E402
from translation.service import TranslationCache, Translator          # noqa: E402

_failures = []


def check(name, actual, expected):
    ok = actual == expected
    print(f"  {'✅' if ok else '❌'} {name}")
    if not ok:
        print(f"       mong đợi: {expected!r}")
        print(f"       thực tế : {actual!r}")
        _failures.append(name)


def check_true(name, condition, hint=""):
    print(f"  {'✅' if condition else '❌'} {name}")
    if not condition:
        if hint:
            print(f"       {hint}")
        _failures.append(name)


# ======================================================================
print("\n[1] Phát hiện ngôn ngữ")
check("tiếng Anh", detect_language("WANTED : Rice Like Steam Basmati Rice"), "en")
check("tiếng Việt có dấu", detect_language("Cần tìm xưởng may đồng phục ở HCM"), "vi")
check("tiếng Việt mất dấu", detect_language("can tim nha cung cap gao cho cong ty"), "vi")
check("tên công ty Việt", detect_language("Công Ty TNHH Đầu Tư ADO"), "vi")
check("chuỗi rỗng coi như vi (bỏ qua)", detect_language(""), "vi")

# ======================================================================
print("\n[2] Từ điển B2B")
terms = find_terms("Buyer needs broken rice and cashew kernel for wholesale export")
check_true("ưu tiên cụm dài: 'broken rice' không kèm 'rice'",
           "broken rice" in terms and "rice" not in terms, f"terms={terms}")
check_true("nhận ra 'cashew kernel'", "cashew kernel" in terms, f"terms={terms}")

augmented = augment_with_glossary("cashew kernel W320", "hạt cà phê W320")
check_true("bổ sung thuật ngữ model dịch sai",
           "nhân hạt điều" in augmented, f"kết quả={augmented!r}")

no_dup = augment_with_glossary("white rice", "gạo trắng")
check_true("không lặp thuật ngữ đã có trong bản dịch",
           no_dup.count("gạo trắng") == 1, f"kết quả={no_dup!r}")

# ======================================================================
print("\n[3] Làm sạch boilerplate")
check("xoá tiền tố WANTED",
      clean_boilerplate("WANTED : Rice Like Steam Basmati Rice"),
      "Rice Like Steam Basmati Rice")
check_true("xoá câu khuôn mẫu RFQ",
           "interested to receive quotations" not in clean_boilerplate(
               "Buyer is interested to receive quotations for the following RFQ - Product name - Rice"))
check_true("không bao giờ trả về rỗng",
           clean_boilerplate("WANTED :").strip() != "")

# ======================================================================
print("\n[4] Cắt đoạn văn bản dài")
long_text = ". ".join([f"This is sentence number {i} about rice export" for i in range(60)])
chunks = split_into_chunks(long_text)
check_true("mọi đoạn <= 400 ký tự", all(len(c) <= 400 for c in chunks),
           f"dài nhất={max(len(c) for c in chunks)}")
check_true("không mất nội dung",
           sum(len(c) for c in chunks) >= len(long_text) * 0.9)
check("văn bản ngắn giữ nguyên 1 đoạn", split_into_chunks("Short text"), ["Short text"])
check("văn bản rỗng → không có đoạn nào", split_into_chunks(""), [])

single_long_word = "x" * 1200
check_true("từ đơn quá dài vẫn bị cắt đúng giới hạn",
           all(len(c) <= 400 for c in split_into_chunks(single_long_word)))

# ======================================================================
print("\n[5] Cache")
with tempfile.TemporaryDirectory() as tmp:
    db = os.path.join(tmp, "t.db")

    # Backend giả lập, đếm số lần thực sự được gọi
    class FakeBackend:
        name = "fake"

        def __init__(self, tag, cache_id=None):
            self.tag = tag
            self.calls = 0
            self._cache_id = cache_id or f"fake:{tag}"

        def ensure_ready(self):
            return self._cache_id

        def translate_batch(self, texts):
            self.calls += len(texts)
            return [f"[{self.tag}]{t}" for t in texts]

    b1 = FakeBackend("m1")
    tr1 = Translator(backend=b1, cache=TranslationCache(db), use_glossary=False)
    out1 = tr1.translate_many(["Looking for rice suppliers"])
    calls_after_first = b1.calls
    tr1.translate_many(["Looking for rice suppliers"])
    check_true("lần 2 lấy từ cache, không gọi lại model",
               b1.calls == calls_after_first, f"calls={b1.calls}")

    # Bài tiếng Việt không được đưa vào model
    before = b1.calls
    tr1.translate_many(["Cần tìm nhà cung cấp gạo"])
    check_true("bài tiếng Việt không bị dịch", b1.calls == before)

    # ĐỔI MODEL phải làm cache mất hiệu lực — lỗi thật đã gặp:
    # khoá cache chỉ gồm 'nmt' nên bản dịch của opus-mt bị NLLB dùng lại.
    b2 = FakeBackend("m2")
    tr2 = Translator(backend=b2, cache=TranslationCache(db), use_glossary=False)
    out2 = tr2.translate_many(["Looking for rice suppliers"])
    check_true("đổi model → dịch lại, không dùng cache của model cũ",
               b2.calls > 0 and out2[0] != out1[0], f"out1={out1[0]!r} out2={out2[0]!r}")

    # Model hỏng phải lưu dưới khoá 'glossary', không phải khoá model
    class BrokenBackend(FakeBackend):
        def ensure_ready(self):
            return GlossaryBackend.name

        def translate_batch(self, texts):
            return GlossaryBackend().translate_batch(texts)

    broken = BrokenBackend("broken")
    tr3 = Translator(backend=broken, cache=TranslationCache(db), use_glossary=False)
    tr3.translate_many(["Looking for rice suppliers"])

    import sqlite3
    conn = sqlite3.connect(db)
    backends = {r[0] for r in conn.execute("SELECT DISTINCT backend FROM translations")}
    conn.close()
    check_true("bản dịch dự phòng lưu dưới khoá 'glossary'",
               "glossary" in backends, f"backends={backends}")
    check_true("mỗi model có khoá cache riêng",
               "fake:m1" in backends and "fake:m2" in backends, f"backends={backends}")

# ======================================================================
print("\n[6] Backend từ điển đầu-cuối")
tr = Translator(backend=GlossaryBackend(), cache=TranslationCache(":memory:"))
result = tr.translate("WANTED : Buyer needs broken rice 5% for wholesale export")
check_true("boilerplate đã bị xoá", "WANTED" not in result, f"kết quả={result!r}")
check_true("thuật ngữ đã dịch", "tấm" in result, f"kết quả={result!r}")

# ======================================================================
print("\n" + "=" * 60)
if _failures:
    print(f"❌ {len(_failures)} kiểm thử THẤT BẠI: {', '.join(_failures)}")
    sys.exit(1)
print("✅ Toàn bộ kiểm thử PASS")
