
import os
import logging
from typing import Dict, Any, Optional

from llm_eval.providers.openai_provider import OpenAIProvider
from llm_eval.providers.claude_provider import ClaudeProvider
from llm_eval.providers.gemini_provider import GeminiProvider

logger = logging.getLogger(__name__)

def get_llm_provider(api_keys: Dict[str, str], agent_config: Dict[str, Any]) -> Optional[object]:
    """
    Create LLM provider instance based on agent configuration
    """
    provider_type = agent_config.get('llm_provider', 'openai')
    model = agent_config.get('llm_model', 'gpt-4')
    max_tokens = agent_config.get('max_tokens', 2048)

    # Apply model-specific token limits
    if 'gpt-4' in model.lower():
        max_tokens = min(max_tokens, 4096)  # GPT-4 limit
    elif 'gpt-3.5' in model.lower():
        max_tokens = min(max_tokens, 4096)  # GPT-3.5-turbo limit
    else:
        max_tokens = min(max_tokens, 2048)  # Safe default

    logger.info(f"🔧 LLM PROVIDER: Creating {provider_type} provider with model {model}, max_tokens: {max_tokens}")
    logger.info(f"🔧 LLM PROVIDER: Available API keys: {list(k for k, v in api_keys.items() if v)}")

    try:
        if provider_type == 'openai':
            api_key = api_keys.get('openai')
            if not api_key:
                logger.error("❌ LLM PROVIDER: OpenAI API key not found")
                logger.error(f"❌ LLM PROVIDER: Available keys: {list(api_keys.keys())}")
                return None
            logger.info(f"✅ LLM PROVIDER: Creating OpenAI provider with model {model}, max_tokens: {max_tokens}, key length: {len(api_key)}")
            try:
                provider = OpenAIProvider(api_key=api_key, model=model, max_tokens=max_tokens)
                logger.info(f"✅ LLM PROVIDER: Successfully created OpenAI provider")
                return provider
            except Exception as openai_error:
                logger.error(f"❌ LLM PROVIDER: Failed to create OpenAI provider: {openai_error}")
                return None

        elif provider_type in ['anthropic', 'claude']:
            api_key = api_keys.get('anthropic')
            if not api_key:
                logger.error("❌ LLM PROVIDER: Anthropic API key not found")
                return None
            logger.info(f"✅ LLM PROVIDER: Creating Anthropic provider with model {model}, max_tokens: {max_tokens}")
            return ClaudeProvider(api_key=api_key, model=model, max_tokens=max_tokens)

        elif provider_type in ['google', 'gemini']:
            api_key = api_keys.get('google')
            if not api_key:
                logger.error("❌ LLM PROVIDER: Google API key not found")
                return None
            logger.info(f"✅ LLM PROVIDER: Creating Google provider with model {model}, max_tokens: {max_tokens}")
            return GeminiProvider(api_key=api_key, model=model, max_tokens=max_tokens)

        else:
            logger.error(f"❌ LLM PROVIDER: Unknown provider type: {provider_type}")
            return None

    except Exception as e:
        logger.error(f"❌ LLM PROVIDER: Failed to create LLM provider: {e}")
        logger.error(f"❌ LLM PROVIDER: Exception type: {type(e).__name__}")
        import traceback
        logger.error(f"❌ LLM PROVIDER: Traceback: {traceback.format_exc()}")
        return None
