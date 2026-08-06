# backend/vector_search/startup.py
"""
Startup initialization for vector search components.

Only the embedding model is warmed here. It is a local SentenceTransformer that
is expensive to load and shared by every project, so loading it once at startup
is worthwhile and costs nothing external.

The Gemini PDF extractor is deliberately NOT initialised here. API keys in this
platform are per project (`ProjectAPIKey`), and
`EnhancedHierarchicalProcessor._initialize_extractors()` already constructs the
extractor with the correct project's key — or with None, so PDF extraction falls
back to pdfplumber/PyPDF2 — every time a project's documents are processed. A
startup-time initialisation from the global GOOGLE_API_KEY was therefore
redundant (its result was overwritten before any extraction ran), used the wrong
key source, and issued a real billed API call on every boot and every autoreload.
"""

import logging
from django.conf import settings
from .embeddings import get_embedder_instance

logger = logging.getLogger(__name__)

def initialize_vector_search():
    """Warm the shared embedding model at startup."""
    try:
        logger.info("🚀 Initializing AICC IntelliDoc Vector Search components...")

        # Create singleton embedder instance
        embedder = get_embedder_instance()

        logger.info(f"✅ Vector Search initialization complete!")
        logger.info(f"📊 Embedder dimension: {embedder.vector_dim}")
        
        if embedder.model is None:
            logger.warning("⚠️  Using fallback random embeddings - Consider downloading the model")
            logger.info("💡 Run: python backend/download_model.py to download the embedding model")
        else:
            logger.info("🎯 Ready for high-quality document processing!")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Vector Search initialization failed: {e}")
        logger.warning("🔄 Will use fallback mode during processing")
        return False

def check_system_health():
    """Check system health for vector search components"""
    try:
        embedder = get_embedder_instance()
        
        health_status = {
            "embedder_available": embedder is not None,
            "model_loaded": embedder.model is not None if embedder else False,
            "vector_dimension": embedder.vector_dim if embedder else 0,
            "status": "healthy" if (embedder and embedder.model) else "degraded"
        }
        
        return health_status
        
    except Exception as e:
        return {
            "embedder_available": False,
            "model_loaded": False,
            "vector_dimension": 0,
            "status": "error",
            "error": str(e)
        }
