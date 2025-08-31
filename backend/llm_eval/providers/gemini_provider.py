import aiohttp
import time
from .base import LLMProvider, LLMResponse
from typing import Dict, Any, Optional

class GeminiProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = "gemini-1.5-flash", **kwargs):
        super().__init__(api_key, model, **kwargs)
        # Map old model names to new ones for backward compatibility
        model_mapping = {
            "gemini-pro": "gemini-1.5-flash",
            "gemini-pro-vision": "gemini-1.5-flash",
            "gemini-1.5-pro": "gemini-1.5-pro",
            "gemini-1.5-flash": "gemini-1.5-flash",
            "gemini-2.5-flash": "gemini-1.5-flash",  # Use available model
            "gemini-2.0-flash-exp": "gemini-1.5-flash"  # Fallback to stable version
        }
        # Use mapped model name if available
        self.model = model_mapping.get(model, model)
        self.base_url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
    
    def get_headers(self) -> Dict[str, str]:
        return {
            "Content-Type": "application/json"
        }
    
    def format_request_body(self, prompt: str, **kwargs) -> Dict[str, Any]:
        return {
            "contents": [{
                "parts": [{"text": prompt}]
            }],
            "generationConfig": {
                "maxOutputTokens": self.max_tokens,
                "temperature": kwargs.get("temperature", 0.7)
            }
        }
    
    def parse_response(self, response_data: Dict[str, Any]) -> tuple[str, Optional[int]]:
        text = response_data["candidates"][0]["content"]["parts"][0]["text"]
        # Gemini doesn't return token count in the same way
        token_count = None
        return text, token_count
    
    def estimate_cost(self, token_count: Optional[int]) -> Optional[float]:
        if not token_count:
            return None
        return (token_count / 1000) * 0.0005  # Rough estimate
    
    async def generate_response(self, prompt: str, **kwargs) -> LLMResponse:
        start_time = time.time()
        
        try:
            url = f"{self.base_url}?key={self.api_key}"
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                async with session.post(
                    url,
                    headers=self.get_headers(),
                    json=self.format_request_body(prompt, **kwargs)
                ) as response:
                    response_time_ms = int((time.time() - start_time) * 1000)
                    
                    if response.status == 200:
                        data = await response.json()
                        text, token_count = self.parse_response(data)
                        
                        return LLMResponse(
                            text=text,
                            model=self.model,
                            provider="gemini",
                            response_time_ms=response_time_ms,
                            token_count=token_count,
                            cost_estimate=self.estimate_cost(token_count)
                        )
                    else:
                        error_data = await response.json()
                        return LLMResponse(
                            text="",
                            model=self.model,
                            provider="gemini",
                            response_time_ms=response_time_ms,
                            error=error_data.get("error", {}).get("message", "Unknown error")
                        )
                        
        except Exception as e:
            response_time_ms = int((time.time() - start_time) * 1000)
            return LLMResponse(
                text="",
                model=self.model,
                provider="gemini",
                response_time_ms=response_time_ms,
                error=str(e)
            )
