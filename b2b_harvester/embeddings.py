"""
SBERT Vector Embedding Generator
Uses 'keepitreal/vietnamese-sbert' to encode text descriptions into 768-dim dense vectors.
Gracefully lazy-loads model only when required.
"""

import logging
from config import EMBEDDING_MODEL_NAME

logger = logging.getLogger("b2b_harvester.embeddings")

class VectorEmbedder:
    def __init__(self, model_name=EMBEDDING_MODEL_NAME):
        self.model_name = model_name
        self.model = None

    def load_model(self):
        if self.model is None:
            try:
                from sentence_transformers import SentenceTransformer
                logger.info(f"Loading SBERT embedding model '{self.model_name}'...")
                self.model = SentenceTransformer(self.model_name)
                logger.info("SBERT model loaded successfully.")
            except Exception as e:
                logger.warning(f"Failed to load SBERT model: {e}. Vector embeddings will be disabled.")
                self.model = False

    def embed_text(self, text):
        """
        Encodes a given text string into a list of floats (vector).
        Returns list[float] or None if unavailable.
        """
        if not text or not text.strip():
            return None
        
        self.load_model()
        if not self.model:
            return None

        try:
            vector = self.model.encode(text.strip())
            return vector.tolist()
        except Exception as e:
            logger.error(f"Error generating embedding for text snippet: {e}")
            return None
