import logging

import torch
from sentence_transformers import SentenceTransformer

from config.settings import settings

logger = logging.getLogger("Embedder")

class Embedder:
    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Initializing Embedder with model: {settings.EMBEDDING_MODEL_NAME} on {self.device}")
        try:
            self.model = SentenceTransformer(settings.EMBEDDING_MODEL_NAME, device=self.device)
        except Exception as e:
            logger.error(f"Failed to load model {settings.EMBEDDING_MODEL_NAME}: {e}")
            raise e

    def embed_text(self, text, is_query=False):
        """
        Vector hóa văn bản.
        - Nếu là lưu vào DB (Passage): Thêm tiền tố "passage: "
        - Nếu là Query: Thêm tiền tố "query: "
        Rule: Guide Step 2 & 3.
        """
        if not text:
            return None
        
        prefix = "query: " if is_query else "passage: "
        text_with_prefix = prefix + text
        
        try:
            # Normalize embeddings is usually good for cosine similarity
            embedding = self.model.encode(text_with_prefix, normalize_embeddings=True)
            return embedding.tolist()
        except Exception as e:
            logger.error(f"Error embedding text: {e}")
            return None

    def embed_batch(self, texts, is_query=False):
        """
        Xử lý vector hóa theo batch để tối ưu hiệu suất (Rule 4).
        """
        if not texts:
            return []
            
        prefix = "query: " if is_query else "passage: "
        texts_with_prefix = [prefix + t for t in texts]
        
        try:
            embeddings = self.model.encode(texts_with_prefix, batch_size=settings.BATCH_SIZE, normalize_embeddings=True)
            return embeddings.tolist()
        except Exception as e:
            logger.error(f"Error embedding batch: {e}")
            return []
