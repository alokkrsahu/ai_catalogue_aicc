import aiohttp
import time
import logging
from .base import LLMProvider, LLMResponse
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

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
            "messages": [{"role": "user", "content": prompt}]
        }
    
    def parse_response(self, response_data: Dict[str, Any]) -> tuple[str, Optional[int]]:
        # Safely extract text content with proper error handling
        try:
            choices = response_data.get("choices", [])
            if not choices:
                raise ValueError("No choices in response")
            
            message = choices[0].get("message", {})
            text = message.get("content")
            
            # Handle None or empty content
            if text is None:
                # Check for finish_reason to understand why content is None
                finish_reason = choices[0].get("finish_reason")
                if finish_reason == "length":
                    raise ValueError("Response was truncated due to max_tokens limit")
                elif finish_reason == "content_filter":
                    raise ValueError("Response was filtered by content safety filters")
                elif finish_reason:
                    raise ValueError(f"Response incomplete: finish_reason={finish_reason}")
                else:
                    raise ValueError("Response content is None without finish_reason")
            
            # Ensure text is a string
            text = str(text) if text is not None else ""
            
        except (KeyError, IndexError, ValueError) as e:
            raise ValueError(f"Failed to parse OpenAI response: {e}. Response data: {response_data}")
        
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
                        try:
                            text, token_count = self.parse_response(data)
                            
                            # Double-check that text is not empty after parsing
                            if not text or not text.strip():
                                error_msg = "OpenAI API returned empty response content"
                                logger.warning(f"⚠️ OPENAI: {error_msg}. Response data: {data}")
                                return LLMResponse(
                                    text="",
                                    model=self.model,
                                    provider="openai",
                                    response_time_ms=response_time_ms,
                                    error=error_msg
                                )
                            
                            return LLMResponse(
                                text=text,
                                model=self.model,
                                provider="openai",
                                response_time_ms=response_time_ms,
                                token_count=token_count,
                                cost_estimate=self.estimate_cost(token_count)
                            )
                        except ValueError as parse_error:
                            # parse_response raised an error - return it as error
                            return LLMResponse(
                                text="",
                                model=self.model,
                                provider="openai",
                                response_time_ms=response_time_ms,
                                error=str(parse_error)
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
