import aiohttp
import time
import logging
from .base import LLMProvider, LLMResponse
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

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
            }]
        }
    
    def parse_response(self, response_data: Dict[str, Any]) -> tuple[str, Optional[int]]:
        # Safely extract text content with proper error handling
        try:
            candidates = response_data.get("candidates", [])
            if not candidates:
                raise ValueError("No candidates in response")
            
            first_candidate = candidates[0]
            content = first_candidate.get("content", {})
            parts = content.get("parts", [])
            
            if not parts:
                # Check finish_reason to understand why there's no content
                finish_reason = first_candidate.get("finishReason")
                if finish_reason == "MAX_TOKENS":
                    raise ValueError("Response was truncated due to max_tokens limit")
                elif finish_reason == "SAFETY":
                    raise ValueError("Response was blocked by safety filters")
                elif finish_reason:
                    raise ValueError(f"Response incomplete: finish_reason={finish_reason}")
                else:
                    raise ValueError("No parts in response content")
            
            text = parts[0].get("text")
            
            # Handle None or empty content
            if text is None:
                raise ValueError("Response text is None")
            
            # Ensure text is a string
            text = str(text) if text is not None else ""
            
        except (KeyError, IndexError, ValueError) as e:
            raise ValueError(f"Failed to parse Gemini response: {e}. Response data: {response_data}")
        
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
                        try:
                            text, token_count = self.parse_response(data)
                            
                            # Double-check that text is not empty after parsing
                            if not text or not text.strip():
                                error_msg = "Gemini API returned empty response content"
                                logger.warning(f"⚠️ GEMINI: {error_msg}. Response data: {data}")
                                return LLMResponse(
                                    text="",
                                    model=self.model,
                                    provider="gemini",
                                    response_time_ms=response_time_ms,
                                    error=error_msg
                                )
                            
                            return LLMResponse(
                                text=text,
                                model=self.model,
                                provider="gemini",
                                response_time_ms=response_time_ms,
                                token_count=token_count,
                                cost_estimate=self.estimate_cost(token_count)
                            )
                        except ValueError as parse_error:
                            # parse_response raised an error - return it as error
                            return LLMResponse(
                                text="",
                                model=self.model,
                                provider="gemini",
                                response_time_ms=response_time_ms,
                                error=str(parse_error)
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
