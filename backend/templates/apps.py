# templates/apps.py

from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)

class TemplatesConfig(AppConfig):
    """Configuration for the templates app"""
    
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'templates'
    verbose_name = 'Project Templates'
    
    def ready(self):
        """Initialize the app when Django starts"""
        # Import any signal handlers here if needed
        
        # Initialize cache warmup on startup (in production)
        try:
            from django.conf import settings
            
            # Only initialize cache warmup if not in testing mode
            if not getattr(settings, 'TESTING', False):
                from .cache import CacheWarmup
                logger.info("Starting template cache warmup on application startup")
                CacheWarmup.warmup_on_startup()
        except Exception as e:
            logger.warning(f"Failed to initialize cache warmup on startup: {str(e)}")
            # Don't fail startup if cache warmup fails
            pass
