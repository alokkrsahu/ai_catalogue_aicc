"""
LLM Provider Manager - Project-Specific API Keys Only
=====================================================

Handles LLM provider initialization and configuration for conversation orchestration.
All agents must use project-specific encrypted API keys. Environment variables are not used.
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
    Manages LLM provider initialization and configuration with project-specific API keys only.
    All agents must use project-specific encrypted API keys. Environment variables are not used.
    """
    
    def __init__(self):
        # Initialize project API key service
        self.project_api_service = get_project_api_key_service()
        logger.info("🤖 LLM PROVIDER MANAGER: Initialized with project-specific API keys only (no environment variable fallback)")
        
    async def get_llm_provider(self, agent_config: Dict[str, Any], project: Optional[IntelliDocProject] = None) -> Optional[object]:
        """
        Create LLM provider instance based on agent configuration.
        Requires project-specific API keys. Project context is mandatory.
        
        Args:
            agent_config: Agent configuration with provider type, model, etc.
            project: Project instance for project-specific API keys (REQUIRED)
            
        Returns:
            LLM provider instance or None if no API key available
        """
        provider_type = agent_config.get('llm_provider', 'openai')
        model = agent_config.get('llm_model', 'gpt-4')
        
        logger.info(f"🔧 LLM PROVIDER: Creating {provider_type} provider with model {model}")
        
        # Validate project is provided
        if not project:
            error_msg = f"Project context is required for API key access. All agents must use project-specific API keys. Provider: {provider_type}"
            logger.error(f"❌ LLM PROVIDER: {error_msg}")
            return None
        
        # Get API key from project-specific configuration only
        api_key = await self._get_api_key_for_provider(provider_type, project)
        
        if not api_key:
            error_msg = f"No project-specific {provider_type} API key found for project {project.name}. Please configure API keys in project settings."
            logger.error(f"❌ LLM PROVIDER: {error_msg}")
            return None
        
        # Final validation: ensure the key doesn't look like a placeholder
        api_key_lower = api_key.lower().strip()
        is_placeholder = (
            'your_' in api_key_lower or
            'placeholder' in api_key_lower or
            'replace' in api_key_lower or
            'example' in api_key_lower or
            len(api_key.strip()) < 10
        )
        if is_placeholder:
            error_msg = f"Project-specific API key for {provider_type} in project {project.name} appears to be a placeholder/dummy value. Please configure a valid API key in project settings."
            logger.error(f"❌ LLM PROVIDER: {error_msg}")
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

    async def _get_api_key_for_provider(self, provider_type: str, project: IntelliDocProject) -> Optional[str]:
        """
        Get API key for provider from project-specific configuration only.
        Project context is required. No environment variable fallback.
        
        Args:
            provider_type: Type of provider (openai, google, anthropic)
            project: Project instance for project-specific keys (REQUIRED)
            
        Returns:
            API key string or None if not found
        """
        if not project:
            logger.error(f"❌ PROJECT API KEY: Project context is required for {provider_type} API key access")
            return None
        
        try:
            project_key = await sync_to_async(self.project_api_service.get_project_api_key)(project, provider_type)
            if project_key:
                # Validate project key is not a placeholder
                project_key_lower = project_key.lower().strip()
                is_placeholder = (
                    'your_' in project_key_lower or
                    'placeholder' in project_key_lower or
                    'replace' in project_key_lower or
                    'example' in project_key_lower or
                    'dummy' in project_key_lower or
                    len(project_key.strip()) < 10
                )
                if is_placeholder:
                    logger.error(f"❌ PROJECT API KEY: Project-specific {provider_type} key for project {project.name} appears to be a placeholder/dummy value (length: {len(project_key)})")
                    logger.error(f"❌ PROJECT API KEY: Please configure a valid {provider_type} API key in project settings")
                    return None
                else:
                    logger.info(f"✅ PROJECT API KEY: Using project-specific {provider_type} key for project {project.name} (length: {len(project_key)})")
                    return project_key
            else:
                logger.warning(f"⚠️ PROJECT API KEY: No project-specific {provider_type} key found for project {project.name}")
                return None
        except Exception as e:
            logger.error(f"❌ PROJECT API KEY: Error getting project-specific {provider_type} key for project {project.name}: {e}")
            import traceback
            logger.error(f"❌ PROJECT API KEY: Traceback: {traceback.format_exc()}")
            return None

    def get_llm_provider_sync(self, agent_config: Dict[str, Any], project: Optional[IntelliDocProject] = None) -> Optional[object]:
        """
        Synchronous version for backward compatibility.
        DEPRECATED: This method should not be used. Use async get_llm_provider instead.
        Project context is required - this method will fail if project is not provided.
        
        Args:
            agent_config: Agent configuration with provider type, model, etc.
            project: Project instance for project-specific API keys (REQUIRED)
            
        Returns:
            LLM provider instance or None if no API key available
        """
        if not project:
            logger.error("❌ LLM PROVIDER (SYNC): Project context is required. This sync method is deprecated. Use async get_llm_provider with project parameter instead.")
            return None
        
        logger.warning("⚠️  LLM PROVIDER: Using deprecated sync method. Consider migrating to async get_llm_provider.")
        # Use async method via asyncio.run for sync compatibility
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is already running, we can't use asyncio.run
                logger.error("❌ LLM PROVIDER (SYNC): Cannot use sync method in async context. Use async get_llm_provider instead.")
                return None
        except RuntimeError:
            pass  # No event loop, we can use asyncio.run
        
        return asyncio.run(self.get_llm_provider(agent_config, project))
