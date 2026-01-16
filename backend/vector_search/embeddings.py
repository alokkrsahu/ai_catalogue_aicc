# backend/vector_search/embeddings.py
from sentence_transformers import SentenceTransformer
from typing import List, Optional
import numpy as np
import logging
import os
from pathlib import Path
import threading

logger = logging.getLogger(__name__)

# Global singleton instance
_embedder_instance: Optional['DocumentEmbedder'] = None
_embedder_lock = threading.Lock()

def get_embedder_instance(model_name: str = 'all-MiniLM-L6-v2') -> 'DocumentEmbedder':
    """Get or create singleton DocumentEmbedder instance"""
    global _embedder_instance
    
    if _embedder_instance is None:
        with _embedder_lock:
            if _embedder_instance is None:
                logger.info(f"🔧 Creating singleton DocumentEmbedder instance...")
                _embedder_instance = DocumentEmbedder(model_name)
                logger.info(f"✅ Singleton DocumentEmbedder created successfully")
    
    return _embedder_instance

class DocumentEmbedder:
    """Creates semantic embeddings for document text using Sentence Transformers"""
    
    def __init__(self, model_name: str = 'sentence-transformers/all-MiniLM-L6-v2'):
        try:
            import torch
            
            torch.cuda.empty_cache() if torch.cuda.is_available() else None
            
            logger.info(f"Initializing DocumentEmbedder with model {model_name}...")
            
            # Set timeout environment variables for HuggingFace
            os.environ.setdefault('HF_HUB_DOWNLOAD_TIMEOUT', '300')
            os.environ.setdefault('HF_HUB_DOWNLOAD_TIMEOUT_S', '300')
            os.environ.setdefault('REQUESTS_TIMEOUT', '300')
            
            # Attempt to load the model from a local cache first
            # HuggingFace uses different cache formats:
            # - Old format: model_name.replace('/', '_')
            # - New format: models--{org}--{model_name}
            cache_dir = Path.home() / '.cache' / 'torch' / 'sentence_transformers'
            old_format_path = cache_dir / model_name.replace('/', '_')
            new_format_path = cache_dir / f"models--{model_name.replace('/', '--')}"
            
            model_cached = False
            if old_format_path.exists() and any(old_format_path.iterdir()):
                logger.info(f"Found model in cache (old format). Loading from {old_format_path}")
                # Set offline mode to skip network checks
                os.environ['HF_HUB_OFFLINE'] = '1'
                self.model = SentenceTransformer(str(old_format_path))
                model_cached = True
            elif new_format_path.exists() and any(new_format_path.iterdir()):
                logger.info(f"Found model in cache (new format). Loading from {new_format_path}")
                # Set offline mode to skip network checks
                os.environ['HF_HUB_OFFLINE'] = '1'
                # For new format, use model name directly - SentenceTransformer will find it
                self.model = SentenceTransformer(model_name, cache_folder=str(cache_dir))
                model_cached = True
            
            if not model_cached:
                # Ensure offline mode is not set when downloading
                os.environ.pop('HF_HUB_OFFLINE', None)
                logger.warning(f"Model not found in cache. Attempting to download with {os.environ.get('HF_HUB_DOWNLOAD_TIMEOUT', 'default')}s timeout.")
                # This will raise an error if it fails, which is the desired behavior
                self.model = SentenceTransformer(model_name, cache_folder=str(cache_dir))

            self.vector_dim = self.model.get_sentence_embedding_dimension()
            
            # Test the model to ensure it's working
            self.model.encode("test", convert_to_numpy=True)
            
            logger.info(f"✅ Successfully initialized DocumentEmbedder with model {model_name}, dimension: {self.vector_dim}")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize DocumentEmbedder: {e}")
            # Re-raise the exception to halt the application if the model can't be loaded
            raise RuntimeError(f"Could not initialize the SentenceTransformer model '{model_name}'. "
                               f"Ensure the model is available or that you have an internet connection. "
                               f"Original error: {e}") from e
    
    def create_embeddings(self, text: str) -> np.ndarray:
        """Create embeddings for document text"""
        if not text or not text.strip():
            logger.warning("Empty text provided for embedding. Returning zero vector.")
            return np.zeros(self.vector_dim, dtype=np.float32)
        
        try:
            embedding = self.model.encode(text, convert_to_numpy=True, normalize_embeddings=True)
            return embedding.astype(np.float32)
        except Exception as e:
            logger.error(f"Failed to create embeddings: {e}")
            # Re-raise to ensure failures are not silent
            raise
    
    def batch_create_embeddings(self, texts: List[str]) -> np.ndarray:
        """Create embeddings for multiple texts in batch"""
        if not texts:
            return np.array([])
        
        # Filter out empty texts, replacing them with a space to avoid errors
        processed_texts = [text if text and text.strip() else " " for text in texts]
        
        try:
            embeddings = self.model.encode(
                processed_texts, 
                batch_size=32, 
                show_progress_bar=True,
                convert_to_numpy=True,
                normalize_embeddings=True
            )
            return embeddings.astype(np.float32)
        except Exception as e:
            logger.error(f"Failed to create batch embeddings: {e}")
            # Re-raise to ensure failures are not silent
            raise
