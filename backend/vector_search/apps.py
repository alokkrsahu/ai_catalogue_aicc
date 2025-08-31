# backend/vector_search/apps.py
from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)

class VectorSearchConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'vector_search'
    verbose_name = 'Vector Search'
    
    def ready(self):
        """Initialize vector search components when Django starts"""
        try:
            # Import here to avoid circular imports
            from .startup import initialize_vector_search
            
            logger.info("🎆 AICC IntelliDoc Vector Search App Ready")
            
            # Initialize vector search components
            success = initialize_vector_search()
            
            if success:
                logger.info("✅ Vector Search ready for processing")
            else:
                logger.warning("⚠️  Vector Search in fallback mode")
                
        except Exception as e:
            logger.error(f"❌ Vector Search app initialization failed: {e}")
            logger.warning("🔄 Processing will use fallback mode")
