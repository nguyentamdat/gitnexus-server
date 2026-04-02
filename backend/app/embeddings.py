"""Embeddings generation and management."""

from typing import List
import numpy as np
from sentence_transformers import SentenceTransformer
import structlog

from app.config import settings

logger = structlog.get_logger()


class EmbeddingsManager:
    """Manages text embeddings for semantic search."""
    
    def __init__(self):
        self.model = None
        self._load_model()
    
    def _load_model(self):
        """Load embedding model."""
        try:
            if settings.embedding_provider == "local":
                logger.info("loading_local_embedding_model", model=settings.embedding_model)
                self.model = SentenceTransformer(settings.embedding_model)
            elif settings.embedding_provider == "openai":
                # Would use OpenAI API
                logger.info("using_openai_embeddings")
                self.model = None
            else:
                raise ValueError(f"Unknown embedding provider: {settings.embedding_provider}")
        except Exception as e:
            logger.error("embedding_model_load_failed", error=str(e))
            raise
    
    def embed_text(self, text: str) -> List[float]:
        """Generate embedding for single text."""
        if settings.embedding_provider == "openai":
            # Would call OpenAI API
            raise NotImplementedError("OpenAI embeddings not yet implemented")
        
        if self.model is None:
            raise RuntimeError("Embedding model not loaded")
        
        embedding = self.model.encode(text, convert_to_numpy=True)
        return embedding.tolist()
    
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts."""
        if settings.embedding_provider == "openai":
            raise NotImplementedError("OpenAI embeddings not yet implemented")
        
        if self.model is None:
            raise RuntimeError("Embedding model not loaded")
        
        embeddings = self.model.encode(texts, convert_to_numpy=True, batch_size=32)
        return [emb.tolist() for emb in embeddings]
    
    def embed_query(self, query: str) -> List[float]:
        """Generate embedding for search query."""
        return self.embed_text(query)
    
    def similarity(self, emb1: List[float], emb2: List[float]) -> float:
        """Calculate cosine similarity between two embeddings."""
        v1 = np.array(emb1)
        v2 = np.array(emb2)
        
        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return float(np.dot(v1, v2) / (norm1 * norm2))


# Singleton instance
_embeddings_manager: EmbeddingsManager = None


def get_embeddings() -> EmbeddingsManager:
    """Get embeddings manager instance."""
    global _embeddings_manager
    if _embeddings_manager is None:
        _embeddings_manager = EmbeddingsManager()
    return _embeddings_manager
