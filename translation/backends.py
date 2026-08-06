# -*- coding: utf-8 -*-
"""
Các bộ dịch (backend) Anh → Việt.
===================================
Tất cả backend dùng chung giao diện `translate_batch(list[str]) -> list[str]`,
nên đổi backend chỉ cần đổi biến môi trường TRANSLATION_BACKEND.

  nmt       Model NMT chạy offline qua transformers (mặc định).
            Mặc định dùng Helsinki-NLP/opus-mt-en-vi (~300MB, tải 1 lần).
  glossary  Thay thế thuật ngữ theo từ điển, không cần model. Luôn khả dụng,
            dùng làm dự phòng khi không tải được model.
"""

import logging
import os
import re

from .glossary import glossary_translate

logger = logging.getLogger("translation.backends")

#: Độ dài tối đa mỗi đoạn đưa vào model (ký tự). opus-mt giới hạn 512 token,
#: ~400 ký tự là ngưỡng an toàn cho văn bản tiếng Anh.
MAX_CHUNK_CHARS = 400


def split_into_chunks(text: str, max_chars: int = MAX_CHUNK_CHARS) -> list[str]:
    """
    Cắt văn bản dài thành các đoạn ngắn để model dịch không bị cắt cụt.

    Cắt ưu tiên theo ranh giới tự nhiên: xuống dòng → câu → cụm dấu phẩy.
    Câu đơn lẻ dài quá vẫn bị cắt cứng để không vượt giới hạn model.
    """
    if not text or not text.strip():
        return []
    if len(text) <= max_chars:
        return [text.strip()]

    # Tách theo dòng trước, vì bài đăng RFQ có cấu trúc nhiều dòng
    pieces = []
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        if len(line) <= max_chars:
            pieces.append(line)
        else:
            # Tách tiếp theo câu
            pieces.extend(s.strip() for s in re.split(r"(?<=[.!?;])\s+", line) if s.strip())

    # Gom các mẩu nhỏ lại cho đủ dài (giảm số lần gọi model)
    chunks, buffer = [], ""
    for piece in pieces:
        while len(piece) > max_chars:          # mẩu vẫn quá dài → cắt cứng
            if buffer:
                chunks.append(buffer); buffer = ""
            cut = piece.rfind(" ", 0, max_chars)
            cut = cut if cut > max_chars // 2 else max_chars
            chunks.append(piece[:cut].strip())
            piece = piece[cut:].strip()
        if not piece:
            continue
        if len(buffer) + len(piece) + 1 <= max_chars:
            buffer = f"{buffer} {piece}".strip()
        else:
            if buffer:
                chunks.append(buffer)
            buffer = piece
    if buffer:
        chunks.append(buffer)

    return chunks


class GlossaryBackend:
    """Dự phòng: thay thế thuật ngữ theo từ điển, không cần model."""

    name = "glossary"

    def ensure_ready(self) -> str:
        """Không cần chuẩn bị gì; trả về tên backend thực sự sẽ dùng."""
        return self.name

    def translate_batch(self, texts: list[str]) -> list[str]:
        return [glossary_translate(t) for t in texts]


class NMTBackend:
    """
    Model dịch máy chạy offline qua `transformers`.

    Model mặc định: Helsinki-NLP/opus-mt-en-vi (MarianMT, ~300MB).
    Đổi bằng biến môi trường TRANSLATION_MODEL. Model được lazy-load ở lần dịch
    đầu tiên, nên import module này không tốn gì.
    """

    name = "nmt"

    #: Model mặc định. NLLB-200 cho chất lượng Anh→Việt tốt hơn hẳn opus-mt-en-vi
    #: (opus-mt dịch "wants to import" thành "muốn tính tiền" — không dùng được).
    DEFAULT_MODEL = "facebook/nllb-200-distilled-600M"

    def __init__(self, model_name: str | None = None):
        self.model_name = model_name or os.getenv("TRANSLATION_MODEL", self.DEFAULT_MODEL)
        self.batch_size = int(os.getenv("TRANSLATION_BATCH_SIZE", "8"))
        self._model = None
        self._tokenizer = None
        self._load_failed = False
        self._forced_bos_id = None

        lowered = self.model_name.lower()
        # envit5 yêu cầu tiền tố "en: " ở đầu câu và trả về "vi: ..."
        self._needs_prefix = "envit5" in lowered
        # NLLB là model đa ngữ: phải chỉ định ngôn ngữ nguồn khi tokenize và ép
        # token ngôn ngữ đích khi sinh, nếu không nó dịch sang ngôn ngữ tuỳ ý.
        self._is_nllb = "nllb" in lowered

    def ensure_ready(self) -> str:
        """
        Nạp model và trả về ĐỊNH DANH CACHE của bộ dịch thực sự được dùng.

        Định danh phải bao gồm tên model, không chỉ tên backend. Nếu chỉ dùng
        'nmt' thì khi đổi model (opus-mt → NLLB) khoá cache không đổi, và hệ
        thống sẽ đọc lại bản dịch cũ của model cũ — đã gặp đúng lỗi này khi thử.

        Model không nạp được → trả về 'glossary' để bản dịch dự phòng không bị
        lưu nhầm dưới khoá của model.
        """
        return f"{self.name}:{self.model_name}" if self._load() else GlossaryBackend.name

    def _load(self) -> bool:
        """Tải model, trả về False nếu thất bại (gọi nhiều lần vẫn an toàn)."""
        if self._model is not None:
            return True
        if self._load_failed:
            return False

        try:
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

            logger.info(f"🌐 Đang tải model dịch '{self.model_name}' (lần đầu phải tải về, có thể mất vài phút)...")

            tok_kwargs = {"src_lang": "eng_Latn"} if self._is_nllb else {}
            self._tokenizer = AutoTokenizer.from_pretrained(self.model_name, **tok_kwargs)
            self._model = AutoModelForSeq2SeqLM.from_pretrained(self.model_name)
            self._model.eval()

            if self._is_nllb:
                self._forced_bos_id = self._tokenizer.convert_tokens_to_ids("vie_Latn")
                if not self._forced_bos_id:
                    raise ValueError("Không lấy được token ngôn ngữ đích 'vie_Latn' của NLLB")

            logger.info("✅ Model dịch đã sẵn sàng.")
            return True
        except Exception as e:
            logger.error(f"❌ Không tải được model dịch '{self.model_name}': {e}")
            logger.warning("⚠️ Chuyển sang dự phòng: dịch bằng từ điển thuật ngữ B2B.")
            self._load_failed = True
            return False

    def translate_batch(self, texts: list[str]) -> list[str]:
        if not texts:
            return []
        if not self._load():
            return GlossaryBackend().translate_batch(texts)

        import torch

        results = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]
            if self._needs_prefix:
                batch = [f"en: {t}" for t in batch]

            try:
                inputs = self._tokenizer(
                    batch, return_tensors="pt", padding=True, truncation=True, max_length=512
                )
                gen_kwargs = {"max_length": 512, "num_beams": 4}
                if self._forced_bos_id:
                    gen_kwargs["forced_bos_token_id"] = self._forced_bos_id
                with torch.no_grad():
                    outputs = self._model.generate(**inputs, **gen_kwargs)
                decoded = self._tokenizer.batch_decode(outputs, skip_special_tokens=True)
            except Exception as e:
                logger.error(f"❌ Lỗi khi dịch batch: {e}. Dùng từ điển cho batch này.")
                decoded = GlossaryBackend().translate_batch(texts[i:i + self.batch_size])

            if self._needs_prefix:
                decoded = [re.sub(r"^vi:\s*", "", d) for d in decoded]
            results.extend(decoded)

        return results


def get_backend(name: str | None = None):
    """Tạo backend theo tên (mặc định đọc TRANSLATION_BACKEND, fallback 'nmt')."""
    name = (name or os.getenv("TRANSLATION_BACKEND", "nmt")).lower()
    if name == "glossary":
        return GlossaryBackend()
    if name == "nmt":
        return NMTBackend()
    logger.warning(f"⚠️ Backend dịch không hợp lệ: '{name}'. Dùng 'nmt'.")
    return NMTBackend()
