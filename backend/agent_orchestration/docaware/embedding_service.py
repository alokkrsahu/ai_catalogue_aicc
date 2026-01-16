"""
Embedding Service for DocAware Agents
====================================

Handles text-to-vector conversion for DocAware agents using the project's
existing embedding infrastructure.
"""

import logging
import os
from pathlib import Path
from typing import List, Optional, Dict, Any
from sentence_transformers import SentenceTransformer
from django.conf import settings
import numpy as np

logger = logging.getLogger('agent_orchestration')

class DocAwareEmbeddingService:
    """Service for generating embeddings for DocAware agent queries"""
    
    def __init__(self, model_name: Optional[str] = None):
        """
        Initialize embedding service
        
        Args:
            model_name: Name of the embedding model to use
        """
        self.model_name = model_name or getattr(settings, 'VECTOR_EMBEDDING_MODEL', 'all-MiniLM-L6-v2')
        self.model = None
        self._load_model()
    
    def _load_model(self):
        """Load the embedding model with cache checking and timeout handling"""
        try:
            # CRITICAL: Set HuggingFace timeout before initialization to prevent timeout errors
            os.environ.setdefault('HF_HUB_DOWNLOAD_TIMEOUT', '300')  # 5 minutes
            
            logger.info(f"📊 EMBEDDING: Loading model {self.model_name}")
            
            # Check if model is cached first (similar to main system approach)
            cache_dir = Path.home() / '.cache' / 'torch' / 'sentence_transformers'
            model_cache_path = cache_dir / self.model_name.replace('/', '_')
            
            if model_cache_path.exists() and any(model_cache_path.iterdir()):
                logger.info(f"✅ EMBEDDING: Found cached model at {model_cache_path}, using cached version")
                # Load from cache explicitly
                self.model = SentenceTransformer(self.model_name, cache_folder=str(cache_dir))
            else:
                logger.info(f"📥 EMBEDDING: Model not in cache, will download (this may take a few minutes)")
                logger.info(f"💡 TIP: Pre-download model using: python manage.py download_embedder_model")
                # Download with timeout
                self.model = SentenceTransformer(self.model_name, cache_folder=str(cache_dir))
            
            logger.info(f"✅ EMBEDDING: Model loaded successfully")
        except Exception as e:
            logger.error(f"❌ EMBEDDING: Failed to load model {self.model_name}: {e}")
            logger.error(f"❌ EMBEDDING: Error details: {type(e).__name__}: {str(e)}")
            raise
    
    def encode_query(self, query: str, normalize: bool = True) -> List[float]:
        """
        Convert text query to embedding vector
        
        Args:
            query: Text query to embed
            normalize: Whether to normalize the vector
            
        Returns:
            List of float values representing the embedding
        """
        if not self.model:
            raise RuntimeError("Embedding model not initialized")
        
        try:
            logger.debug(f"📊 EMBEDDING: Encoding query: {query[:100]}...")
            
            # Generate embedding
            embedding = self.model.encode([query], normalize_embeddings=normalize)[0]
            
            # Convert to list for JSON serialization
            embedding_list = embedding.tolist()
            
            logger.debug(f"✅ EMBEDDING: Generated {len(embedding_list)}-dimensional vector")
            return embedding_list
            
        except Exception as e:
            logger.error(f"❌ EMBEDDING: Failed to encode query: {e}")
            raise
    
    def encode_with_context(self, query: str, context: List[str], context_weight: float = 0.3) -> List[float]:
        """
        Encode query with conversation context
        
        Args:
            query: Main query text
            context: List of context strings (previous conversation turns)
            context_weight: Weight for context influence
            
        Returns:
            Contextualized embedding vector
        """
        if not context or context_weight == 0:
            return self.encode_query(query)
        
        try:
            # Encode query and context separately
            query_embedding = self.model.encode([query], normalize_embeddings=True)[0]
            
            # Combine and encode context
            context_text = " ".join(context[-3:])  # Use last 3 context items
            context_embedding = self.model.encode([context_text], normalize_embeddings=True)[0]
            
            # Weighted combination
            combined_embedding = (1 - context_weight) * query_embedding + context_weight * context_embedding
            
            # Normalize the result
            combined_embedding = combined_embedding / np.linalg.norm(combined_embedding)
            
            logger.debug(f"📊 EMBEDDING: Generated contextualized embedding (context_weight={context_weight})")
            return combined_embedding.tolist()
            
        except Exception as e:
            logger.error(f"❌ EMBEDDING: Failed to encode with context: {e}")
            # Fallback to query-only embedding
            return self.encode_query(query)
    
    def get_embedding_dimension(self) -> int:
        """Get the dimension of embeddings produced by this model"""
        if not self.model:
            return getattr(settings, 'VECTOR_DIMENSION', 384)
        
        # Generate a test embedding to get dimension
        test_embedding = self.model.encode(["test"], normalize_embeddings=True)[0]
        return len(test_embedding)
    
    def batch_encode(self, texts: List[str], normalize: bool = True) -> List[List[float]]:
        """
        Encode multiple texts in batch for efficiency
        
        Args:
            texts: List of texts to encode
            normalize: Whether to normalize vectors
            
        Returns:
            List of embedding vectors
        """
        if not self.model:
            raise RuntimeError("Embedding model not initialized")
        
        try:
            logger.debug(f"📊 EMBEDDING: Batch encoding {len(texts)} texts")
            
            embeddings = self.model.encode(texts, normalize_embeddings=normalize)
            embedding_lists = [emb.tolist() for emb in embeddings]
            
            logger.debug(f"✅ EMBEDDING: Generated {len(embedding_lists)} embeddings")
            return embedding_lists
            
        except Exception as e:
            logger.error(f"❌ EMBEDDING: Batch encoding failed: {e}")
            raise
