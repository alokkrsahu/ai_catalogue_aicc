"""
LLM Provider Manager - Fixed Version with Project-Specific API Keys
==================================================================

Handles LLM provider initialization and configuration for conversation orchestration.
Now integrated with project-specific encrypted API keys instead of just environment variables.
"""

import os
import logging
from typing import Dict, List, Any, Optional, Tuple
from asgiref.sync import sync_to_async

# Import existing LLM infrastructure
from llm_eval.providers.openai_provider import OpenAIProvider
from llm_eval.providers.claude_provider import ClaudeProvider  
from llm_eval.providers.gemini_provider import GeminiProvider
from llm_eval.providers.base import LLMResponse

# Import project API key integration
from project_api_keys.services import get_project_api_key_service
from users.models import IntelliDocProject

logger = logging.getLogger('conversation_orchestrator')


class LLMProviderManager:
    """
    Manages LLM provider initialization and configuration with project-specific API keys
    """
    
    def __init__(self):
        # Keep environment variables as fallback
        self.fallback_api_keys = {
            'openai': os.getenv('OPENAI_API_KEY'),
            'anthropic': os.getenv('ANTHROPIC_API_KEY'), 
            'google': os.getenv('GOOGLE_API_KEY')  # Standardized to GOOGLE_API_KEY
        }
        
        # Initialize project API key service
        self.project_api_service = get_project_api_key_service()
        
        # Debug fallback API key availability
        for provider, key in self.fallback_api_keys.items():
            if key and key != 'Dummy-Key':
                logger.info(f"✅ ORCHESTRATOR: {provider.upper()} fallback API key loaded (length: {len(key)})")
            else:
                logger.info(f"⚠️ ORCHESTRATOR: {provider.upper()} fallback API key not available (will use project-specific keys)")
                
        logger.info("🤖 LLM PROVIDER MANAGER: Initialized with project API key integration")
        
    async def get_llm_provider(self, agent_config: Dict[str, Any], project: Optional[IntelliDocProject] = None) -> Optional[object]:
        """
        Create LLM provider instance based on agent configuration
        Now supports project-specific API keys
        
        Args:
            agent_config: Agent configuration with provider type, model, etc.
            project: Project instance for project-specific API keys (NEW)
            
        Returns:
            LLM provider instance or None if no API key available
        """
        provider_type = agent_config.get('llm_provider', 'openai')
        model = agent_config.get('llm_model', 'gpt-4')
        
        logger.info(f"🔧 LLM PROVIDER: Creating {provider_type} provider with model {model}")
        
        # Get API key with project-specific priority
        api_key = await self._get_api_key_for_provider(provider_type, project)
        
        if not api_key:
            logger.error(f"❌ LLM PROVIDER: No API key available for {provider_type} (checked project-specific and fallback)")
            return None
        
        try:
            if provider_type == 'openai':
                logger.info(f"✅ LLM PROVIDER: Creating OpenAI provider with project key, model {model}")
                try:
                    provider = OpenAIProvider(api_key=api_key, model=model)
                    logger.info(f"✅ LLM PROVIDER: Successfully created OpenAI provider with project API key")
                    return provider
                except Exception as openai_error:
                    logger.error(f"❌ LLM PROVIDER: Failed to create OpenAI provider: {openai_error}")
                    return None
                
            elif provider_type in ['anthropic', 'claude']:
                # Claude requires max_tokens, use a reasonable default
                max_tokens = 4096
                logger.info(f"✅ LLM PROVIDER: Creating Anthropic provider with project key, model {model}, max_tokens: {max_tokens}")
                return ClaudeProvider(api_key=api_key, model=model, max_tokens=max_tokens)
                
            elif provider_type in ['google', 'gemini']:
                logger.info(f"✅ LLM PROVIDER: Creating Google provider with project key, model {model}")
                return GeminiProvider(api_key=api_key, model=model)
                
            else:
                logger.error(f"❌ LLM PROVIDER: Unknown provider type: {provider_type}")
                return None
                
        except Exception as e:
            logger.error(f"❌ LLM PROVIDER: Failed to create LLM provider: {e}")
            logger.error(f"❌ LLM PROVIDER: Exception type: {type(e).__name__}")
            import traceback
            logger.error(f"❌ LLM PROVIDER: Traceback: {traceback.format_exc()}")
            return None

    async def _get_api_key_for_provider(self, provider_type: str, project: Optional[IntelliDocProject] = None) -> Optional[str]:
        """
        Get API key for provider with project-specific priority
        
        Priority order:
        1. Project-specific encrypted API key (if project provided)
        2. Environment variable fallback (if not dummy)
        3. None (will cause provider creation to fail)
        
        Args:
            provider_type: Type of provider (openai, google, anthropic)
            project: Project instance for project-specific keys
            
        Returns:
            API key string or None
        """
        # First try project-specific API key
        if project:
            try:
                project_key = await sync_to_async(self.project_api_service.get_project_api_key)(project, provider_type)
                if project_key:
                    logger.info(f"✅ PROJECT API KEY: Using project-specific {provider_type} key for project {project.name}")
                    return project_key
                else:
                    logger.info(f"ℹ️  PROJECT API KEY: No project-specific {provider_type} key found for project {project.name}")
            except Exception as e:
                logger.error(f"❌ PROJECT API KEY: Error getting project-specific {provider_type} key: {e}")
        
        # Fallback to environment variable (but not if it's a dummy value)
        fallback_key = self.fallback_api_keys.get(provider_type)
        if fallback_key and fallback_key != 'Dummy-Key':
            logger.info(f"🔄 FALLBACK API KEY: Using environment variable {provider_type} key")
            return fallback_key
        
        # No key available
        if project:
            logger.warning(f"⚠️  NO API KEY: Neither project-specific nor valid fallback key available for {provider_type} in project {project.name}")
        else:
            logger.warning(f"⚠️  NO API KEY: No valid API key available for {provider_type} (no project context, fallback is dummy)")
        
        return None

    def get_llm_provider_sync(self, agent_config: Dict[str, Any]) -> Optional[object]:
        """
        Synchronous version for backward compatibility (uses fallback keys only)
        This method should be deprecated in favor of the async version with project support
        """
        logger.warning("⚠️  LLM PROVIDER: Using deprecated sync method without project context")
        return self._create_provider_with_fallback_keys(agent_config)
    
    def _create_provider_with_fallback_keys(self, agent_config: Dict[str, Any]) -> Optional[object]:
        """
        Create provider using fallback environment keys only (legacy support)
        """
        provider_type = agent_config.get('llm_provider', 'openai')
        model = agent_config.get('llm_model', 'gpt-4')
        
        api_key = self.fallback_api_keys.get(provider_type)
        if not api_key or api_key == 'Dummy-Key':
            logger.error(f"❌ LLM PROVIDER (LEGACY): No valid fallback API key for {provider_type}")
            return None
        
        try:
            if provider_type == 'openai':
                return OpenAIProvider(api_key=api_key, model=model)
            elif provider_type in ['anthropic', 'claude']:
                # Claude requires max_tokens, use a reasonable default
                max_tokens = 4096
                return ClaudeProvider(api_key=api_key, model=model, max_tokens=max_tokens)
            elif provider_type in ['google', 'gemini']:
                return GeminiProvider(api_key=api_key, model=model)
            else:
                logger.error(f"❌ LLM PROVIDER (LEGACY): Unknown provider type: {provider_type}")
                return None
        except Exception as e:
            logger.error(f"❌ LLM PROVIDER (LEGACY): Failed to create provider: {e}")
            return None
