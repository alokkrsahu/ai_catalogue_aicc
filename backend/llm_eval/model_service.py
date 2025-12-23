import requests
import os
from typing import List, Dict, Any
from .encryption import decrypt_api_key

class ModelService:
    """Service to fetch available models from different LLM providers"""
    
    @staticmethod
    def get_openai_models(api_key: str) -> List[Dict[str, Any]]:
        """
        Fetch available OpenAI models.

        Behaviour notes:
        - We call the OpenAI `/v1/models` endpoint directly and **do not** silently
          fall back to a hard‑coded subset of models.
        - This ensures the frontend can see the **full list of GPT models** that
          your account is allowed to use (e.g. `gpt-4.1`, `gpt-4o-mini`, future GPT‑5
          variants), instead of always being limited to a small default set.
        - If the API call fails (network issue, invalid key, permissions), we now
          return an empty list so upstream callers can surface a clear error and
          treat the key as invalid rather than pretending a partial list is “ok”.
        """
        try:
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            }
            response = requests.get('https://api.openai.com/v1/models', headers=headers, timeout=10)
            response.raise_for_status()
            models = response.json()['data']
            
            # Filter to GPT chat/completion models - INCLUSIVE filter for all GPT models
            # Includes: gpt-3.5-*, gpt-4-*, gpt-4o-*, gpt-5-*, and any future GPT models
            chat_models = []
            for model in models:
                model_id = model['id'].lower()
                
                # Include all GPT models (gpt-3, gpt-3.5, gpt-4, gpt-4o, gpt-5, etc.)
                # Exclude: embeddings, audio, image, fine-tune base models, and deprecated models
                is_gpt_model = model_id.startswith('gpt-')
                
                # Exclude non-chat models (embeddings, audio, image generation, etc.)
                excluded_patterns = [
                    'embedding', 'audio', 'whisper', 'tts', 'dall-e', 'davinci', 
                    'curie', 'babbage', 'ada', 'instruct', 'deprecated'
                ]
                is_excluded = any(excluded in model_id for excluded in excluded_patterns)
                
                # Include all GPT models except excluded ones
                if is_gpt_model and not is_excluded:
                    chat_models.append({
                        'id': model['id'],
                        'name': model['id'],
                        'displayName': model['id'].replace('-', ' ').title(),
                        'object': model.get('object', 'model')
                    })
            
            return sorted(chat_models, key=lambda x: x['id'])
        except Exception as e:
            # IMPORTANT: do not hide failures behind a tiny hard‑coded list.
            # Returning [] allows DynamicModelsService.test_api_key(...) to
            # accurately detect that something is wrong with this API key or
            # network environment, so the UI can show a clear warning instead
            # of only exposing four fallback models.
            print(f"Error fetching OpenAI models: {e}")
            return []
    
    @staticmethod
    def get_claude_models() -> List[Dict[str, str]]:
        """List known Claude models (Anthropic doesn't provide a public models endpoint).
        
        Note: This list is manually maintained. When new Claude models are released,
        they should be added here. The models are ordered by release date (newest first).
        """
        return [
            # Claude 4 and future models (add new models at the top)
            {'id': 'claude-sonnet-4-20250514', 'name': 'claude-sonnet-4-20250514', 'displayName': 'Claude Sonnet 4 (Latest)'},
            # Claude 3.5 models
            {'id': 'claude-3-5-sonnet-20241022', 'name': 'claude-3-5-sonnet-20241022', 'displayName': 'Claude 3.5 Sonnet'},
            {'id': 'claude-3-5-haiku-20241022', 'name': 'claude-3-5-haiku-20241022', 'displayName': 'Claude 3.5 Haiku'},
            # Claude 3 models
            {'id': 'claude-3-opus-20240229', 'name': 'claude-3-opus-20240229', 'displayName': 'Claude 3 Opus'},
            {'id': 'claude-3-sonnet-20240229', 'name': 'claude-3-sonnet-20240229', 'displayName': 'Claude 3 Sonnet'},
            {'id': 'claude-3-haiku-20240307', 'name': 'claude-3-haiku-20240307', 'displayName': 'Claude 3 Haiku'},
            # Claude 2 models (legacy)
            {'id': 'claude-2.1', 'name': 'claude-2.1', 'displayName': 'Claude 2.1'},
            {'id': 'claude-2.0', 'name': 'claude-2.0', 'displayName': 'Claude 2.0'},
            # Claude Instant models (legacy)
            {'id': 'claude-instant-1.2', 'name': 'claude-instant-1.2', 'displayName': 'Claude Instant 1.2'},
        ]
    
    @staticmethod
    def get_gemini_models(api_key: str) -> List[Dict[str, Any]]:
        """Fetch available Google Gemini models."""
        try:
            print(f"🔍 Fetching Gemini models with API key: {api_key[:10]}...")
            url = f'https://generativelanguage.googleapis.com/v1beta/models?key={api_key}'
            
            response = requests.get(url, timeout=10)
            print(f"📡 Gemini API response status: {response.status_code}")
            
            if response.status_code != 200:
                print(f"❌ Gemini API error response: {response.text}")
                response.raise_for_status()
            
            data = response.json()
            models = data.get('models', [])
            print(f"📋 Raw models count: {len(models)}")
            
            # Filter to generation models only and format consistently
            generation_models = []
            for model in models:
                if 'generateContent' in model.get('supportedGenerationMethods', []):
                    model_name = model['name'].replace('models/', '')  # Remove 'models/' prefix
                    generation_models.append({
                        'id': model_name,
                        'name': model_name,
                        'displayName': model.get('displayName', model_name),
                    })
                    print(f"✅ Added model: {model_name}")
            
            print(f"🎉 Found {len(generation_models)} generation models")
            return generation_models
            
        except requests.exceptions.RequestException as e:
            print(f"🌐 Network error fetching Gemini models: {e}")
            # Return default models if API call fails
            return [
                {'id': 'gemini-pro', 'name': 'gemini-pro', 'displayName': 'Gemini Pro'},
                {'id': 'gemini-pro-vision', 'name': 'gemini-pro-vision', 'displayName': 'Gemini Pro Vision'},
                {'id': 'gemini-1.5-pro', 'name': 'gemini-1.5-pro', 'displayName': 'Gemini 1.5 Pro'},
                {'id': 'gemini-1.5-flash', 'name': 'gemini-1.5-flash', 'displayName': 'Gemini 1.5 Flash'},
            ]
        except Exception as e:
            print(f"❌ Error fetching Gemini models: {e}")
            print(f"🔍 Error type: {type(e).__name__}")
            # Return default models if API call fails
            return [
                {'id': 'gemini-pro', 'name': 'gemini-pro', 'displayName': 'Gemini Pro'},
                {'id': 'gemini-pro-vision', 'name': 'gemini-pro-vision', 'displayName': 'Gemini Pro Vision'},
                {'id': 'gemini-1.5-pro', 'name': 'gemini-1.5-pro', 'displayName': 'Gemini 1.5 Pro'},
                {'id': 'gemini-1.5-flash', 'name': 'gemini-1.5-flash', 'displayName': 'Gemini 1.5 Flash'},
            ]
    
    @staticmethod
    def get_models_for_provider(provider_type: str, api_key: str = None) -> List[Dict[str, Any]]:
        """Get available models for a specific provider"""
        if provider_type == 'openai' and api_key:
            return ModelService.get_openai_models(api_key)
        elif provider_type == 'claude':
            return ModelService.get_claude_models()
        elif provider_type == 'gemini' and api_key:
            return ModelService.get_gemini_models(api_key)
        else:
            return []
