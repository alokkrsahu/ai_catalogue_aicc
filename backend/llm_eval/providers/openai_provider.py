import aiohttp
import time
from .base import LLMProvider, LLMResponse
from typing import Dict, Any, Optional

class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = "gpt-3.5-turbo", **kwargs):
        super().__init__(api_key, model, **kwargs)
        self.base_url = "https://api.openai.com/v1/chat/completions"
    
    def get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    def format_request_body(self, prompt: str, **kwargs) -> Dict[str, Any]:
        return {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": self.max_tokens,
            "temperature": kwargs.get("temperature", 0.7)
        }
    
    def parse_response(self, response_data: Dict[str, Any]) -> tuple[str, Optional[int]]:
        text = response_data["choices"][0]["message"]["content"]
        token_count = response_data.get("usage", {}).get("total_tokens")
        return text, token_count
    
    def estimate_cost(self, token_count: Optional[int]) -> Optional[float]:
        if not token_count:
            return None
        # Rough estimates - update with current pricing
        if "gpt-4" in self.model:
            return (token_count / 1000) * 0.03  # $0.03 per 1K tokens
        else:
            return (token_count / 1000) * 0.002  # $0.002 per 1K tokens
    
    async def generate_response(self, prompt: str, **kwargs) -> LLMResponse:
        start_time = time.time()
        
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                async with session.post(
                    self.base_url,
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
                            provider="openai",
                            response_time_ms=response_time_ms,
                            token_count=token_count,
                            cost_estimate=self.estimate_cost(token_count)
                        )
                    else:
                        error_data = await response.json()
                        return LLMResponse(
                            text="",
                            model=self.model,
                            provider="openai",
                            response_time_ms=response_time_ms,
                            error=error_data.get("error", {}).get("message", "Unknown error")
                        )
                        
        except Exception as e:
            response_time_ms = int((time.time() - start_time) * 1000)
            return LLMResponse(
                text="",
                model=self.model,
                provider="openai",
                response_time_ms=response_time_ms,
                error=str(e)
            )
