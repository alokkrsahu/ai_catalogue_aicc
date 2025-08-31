import requests
import os
from typing import List, Dict, Any
from .encryption import decrypt_api_key

class ModelService:
    """Service to fetch available models from different LLM providers"""
    
    @staticmethod
    def get_openai_models(api_key: str) -> List[Dict[str, Any]]:
        """Fetch available OpenAI models."""
        try:
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            }
            response = requests.get('https://api.openai.com/v1/models', headers=headers, timeout=10)
            response.raise_for_status()
            models = response.json()['data']
            
            # Filter to commonly used chat models and format consistently
            chat_models = [
                {
                    'id': model['id'],
                    'name': model['id'],
                    'displayName': model['id'].replace('-', ' ').title(),
                    'object': model.get('object', 'model')
                }
                for model in models 
                if any(name in model['id'] for name in ['gpt-3.5', 'gpt-4', 'gpt-4o']) and 'turbo' in model['id']
            ]
            
            return sorted(chat_models, key=lambda x: x['id'])
        except Exception as e:
            print(f"Error fetching OpenAI models: {e}")
            # Return default models if API call fails
            return [
                {'id': 'gpt-3.5-turbo', 'name': 'gpt-3.5-turbo', 'displayName': 'GPT-3.5 Turbo', 'object': 'model'},
                {'id': 'gpt-4', 'name': 'gpt-4', 'displayName': 'GPT-4', 'object': 'model'},
                {'id': 'gpt-4o', 'name': 'gpt-4o', 'displayName': 'GPT-4 Omni', 'object': 'model'},
                {'id': 'gpt-4-turbo', 'name': 'gpt-4-turbo', 'displayName': 'GPT-4 Turbo', 'object': 'model'},
            ]
    
    @staticmethod
    def get_claude_models() -> List[Dict[str, str]]:
        """List known Claude models (Anthropic doesn't provide a public models endpoint)."""
        return [
            {'id': 'claude-3-5-sonnet-20241022', 'name': 'claude-3-5-sonnet-20241022', 'displayName': 'Claude 3.5 Sonnet (Latest)'},
            {'id': 'claude-3-5-haiku-20241022', 'name': 'claude-3-5-haiku-20241022', 'displayName': 'Claude 3.5 Haiku (Latest)'},
            {'id': 'claude-3-opus-20240229', 'name': 'claude-3-opus-20240229', 'displayName': 'Claude 3 Opus'},
            {'id': 'claude-3-sonnet-20240229', 'name': 'claude-3-sonnet-20240229', 'displayName': 'Claude 3 Sonnet'},
            {'id': 'claude-3-haiku-20240307', 'name': 'claude-3-haiku-20240307', 'displayName': 'Claude 3 Haiku'},
            {'id': 'claude-sonnet-4-20250514', 'name': 'claude-sonnet-4-20250514', 'displayName': 'Claude Sonnet 4'},
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
