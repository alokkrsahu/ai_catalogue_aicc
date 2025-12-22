import aiohttp
import time
import logging
from .base import LLMProvider, LLMResponse
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class ClaudeProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = "claude-3-sonnet-20240229", **kwargs):
        super().__init__(api_key, model, **kwargs)
        self.base_url = "https://api.anthropic.com/v1/messages"
    
    def get_headers(self) -> Dict[str, str]:
        return {
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01"
        }
    
    def format_request_body(self, prompt: str, **kwargs) -> Dict[str, Any]:
        return {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": [{"role": "user", "content": prompt}]
        }
    
    def parse_response(self, response_data: Dict[str, Any]) -> tuple[str, Optional[int]]:
        # Safely extract text content with proper error handling
        try:
            content = response_data.get("content", [])
            if not content:
                raise ValueError("No content in response")
            
            first_content = content[0]
            text = first_content.get("text")
            
            # Handle None or empty content
            if text is None:
                # Check for stop_reason to understand why content is None
                stop_reason = response_data.get("stop_reason")
                if stop_reason == "max_tokens":
                    raise ValueError("Response was truncated due to max_tokens limit")
                elif stop_reason == "stop_sequence":
                    raise ValueError("Response stopped at stop sequence")
                elif stop_reason:
                    raise ValueError(f"Response incomplete: stop_reason={stop_reason}")
                else:
                    raise ValueError("Response text is None without stop_reason")
            
            # Ensure text is a string
            text = str(text) if text is not None else ""
            
        except (KeyError, IndexError, ValueError) as e:
            raise ValueError(f"Failed to parse Claude response: {e}. Response data: {response_data}")
        
        token_count = response_data.get("usage", {}).get("output_tokens")
        return text, token_count
    
    def estimate_cost(self, token_count: Optional[int]) -> Optional[float]:
        if not token_count:
            return None
        return (token_count / 1000) * 0.015  # Rough estimate
    
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
                                error_msg = "Claude API returned empty response content"
                                logger.warning(f"⚠️ CLAUDE: {error_msg}. Response data: {data}")
                                return LLMResponse(
                                    text="",
                                    model=self.model,
                                    provider="claude",
                                    response_time_ms=response_time_ms,
                                    error=error_msg
                                )
                            
                            return LLMResponse(
                                text=text,
                                model=self.model,
                                provider="claude",
                                response_time_ms=response_time_ms,
                                token_count=token_count,
                                cost_estimate=self.estimate_cost(token_count)
                            )
                        except ValueError as parse_error:
                            # parse_response raised an error - return it as error
                            return LLMResponse(
                                text="",
                                model=self.model,
                                provider="claude",
                                response_time_ms=response_time_ms,
                                error=str(parse_error)
                            )
                    else:
                        error_data = await response.json()
                        return LLMResponse(
                            text="",
                            model=self.model,
                            provider="claude",
                            response_time_ms=response_time_ms,
                            error=error_data.get("error", {}).get("message", "Unknown error")
                        )
                        
        except Exception as e:
            response_time_ms = int((time.time() - start_time) * 1000)
            return LLMResponse(
                text="",
                model=self.model,
                provider="claude",
                response_time_ms=response_time_ms,
                error=str(e)
            )
