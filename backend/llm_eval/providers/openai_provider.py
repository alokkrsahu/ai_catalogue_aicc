import aiohttp
import time
import logging
import json
from .base import LLMProvider, LLMResponse
from typing import Dict, Any, Optional, List, AsyncGenerator

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
    
    def format_request_body(
        self, 
        prompt: Optional[str] = None, 
        messages: Optional[List[Dict[str, str]]] = None,
        stream: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Format request body for OpenAI API.
        
        If messages is provided, use it directly (native format).
        Otherwise, fall back to prompt string (backward compatibility).
        """
        if messages:
            # Validate messages format
            from agent_orchestration.message_converter import validate_messages_format
            is_valid, error_msg = validate_messages_format(messages)
            if not is_valid:
                logger.error(f"❌ OPENAI: Invalid messages format: {error_msg}")
                raise ValueError(f"Invalid messages format: {error_msg}")
            
            # Use structured messages array (preferred)
            body = {
                "model": self.model,
                "messages": messages
            }
            if stream:
                body["stream"] = True
            return body
        elif prompt:
            # Fallback to prompt string (backward compatibility)
            body = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}]
            }
            if stream:
                body["stream"] = True
            return body
        else:
            raise ValueError("Either 'prompt' or 'messages' must be provided")
    
    def parse_response(self, response_data: Dict[str, Any]) -> tuple[str, Optional[int]]:
        # Safely extract text content with proper error handling
        try:
            choices = response_data.get("choices", [])
            if not choices:
                logger.error(f"❌ OPENAI: No choices in response data: {response_data}")
                raise ValueError("No choices in response")
            
            message = choices[0].get("message", {})
            text = message.get("content")
            
            logger.info(f"🔍 OPENAI: Extracted content from response - type: {type(text)}, value: {repr(text)[:100] if text else 'None'}")
            
            # Handle None or empty content
            if text is None:
                # Check for finish_reason to understand why content is None
                finish_reason = choices[0].get("finish_reason")
                error_msg = f"Response content is None (finish_reason: {finish_reason})"
                logger.error(f"❌ OPENAI: {error_msg}")
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
            
            logger.info(f"🔍 OPENAI: After string conversion - text length: {len(text)}, text: {repr(text)[:100]}")
            
            # Explicitly handle empty string content (not just None)
            if text == "":
                finish_reason = choices[0].get("finish_reason")
                error_msg = f"Response content is empty string (finish_reason: {finish_reason})"
                logger.error(f"❌ OPENAI: {error_msg}")
                if finish_reason == "length":
                    raise ValueError("Response was truncated due to max_tokens limit")
                elif finish_reason == "content_filter":
                    raise ValueError("Response was filtered by content safety filters")
                elif finish_reason:
                    raise ValueError(f"Response incomplete: finish_reason={finish_reason}")
                else:
                    raise ValueError("Response content is empty string without finish_reason")
            
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
    
    async def generate_response(
        self, 
        prompt: Optional[str] = None, 
        messages: Optional[List[Dict[str, str]]] = None,
        **kwargs
    ) -> LLMResponse:
        start_time = time.time()
        
        # Validate that either prompt or messages is provided
        if not prompt and not messages:
            return LLMResponse(
                text="",
                model=self.model,
                provider="openai",
                response_time_ms=0,
                error="Either 'prompt' or 'messages' must be provided"
            )
        
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                async with session.post(
                    self.base_url,
                    headers=self.get_headers(),
                    json=self.format_request_body(prompt=prompt, messages=messages, **kwargs)
                ) as response:
                    response_time_ms = int((time.time() - start_time) * 1000)
                    
                    if response.status == 200:
                        data = await response.json()
                        logger.debug(f"🔍 OPENAI: Raw API response for model {self.model}: {data}")
                        
                        try:
                            logger.info(f"🔍 OPENAI: About to parse response for model {self.model}")
                            text, token_count = self.parse_response(data)
                            logger.info(f"🔍 OPENAI: Parsed response - text length: {len(text) if text else 0}, token_count: {token_count}, text type: {type(text)}")
                            
                            # Double-check that text is not empty after parsing
                            if not text or not text.strip():
                                # Log detailed response structure for debugging
                                choices = data.get("choices", [])
                                finish_reason = choices[0].get("finish_reason") if choices else None
                                usage = data.get("usage", {})
                                
                                error_msg = f"OpenAI API returned empty response content (finish_reason: {finish_reason}, tokens: {usage})"
                                logger.error(f"❌ OPENAI: {error_msg}")
                                logger.error(f"❌ OPENAI: Full response data: {data}")
                                return LLMResponse(
                                    text="",
                                    model=self.model,
                                    provider="openai",
                                    response_time_ms=response_time_ms,
                                    error=error_msg
                                )
                            
                            # Additional safety check: if text is empty after strip, treat as error
                            if not text.strip():
                                error_msg = "OpenAI API returned whitespace-only response content"
                                logger.error(f"❌ OPENAI: {error_msg}")
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
                            error_msg = str(parse_error)
                            logger.error(f"❌ OPENAI: parse_response raised ValueError: {error_msg}")
                            logger.error(f"❌ OPENAI: Response data that caused error: {data}")
                            return LLMResponse(
                                text="",
                                model=self.model,
                                provider="openai",
                                response_time_ms=response_time_ms,
                                error=error_msg
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
    
    async def generate_response_stream(
        self,
        prompt: Optional[str] = None,
        messages: Optional[List[Dict[str, str]]] = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        Generate streaming response from OpenAI API.
        
        Yields text chunks as they arrive from the API.
        """
        # Validate that either prompt or messages is provided
        if not prompt and not messages:
            yield f"Error: Either 'prompt' or 'messages' must be provided"
            return
        
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                async with session.post(
                    self.base_url,
                    headers=self.get_headers(),
                    json=self.format_request_body(prompt=prompt, messages=messages, stream=True, **kwargs)
                ) as response:
                    if response.status == 200:
                        async for line in response.content:
                            if not line:
                                continue
                            
                            # Parse SSE format
                            line_text = line.decode('utf-8').strip()
                            if not line_text or line_text == 'data: [DONE]':
                                continue
                            
                            if line_text.startswith('data: '):
                                try:
                                    data = json.loads(line_text[6:])  # Remove 'data: ' prefix
                                    choices = data.get("choices", [])
                                    if choices:
                                        delta = choices[0].get("delta", {})
                                        content = delta.get("content")
                                        if content:
                                            yield content
                                except json.JSONDecodeError:
                                    continue
                                except Exception as e:
                                    logger.error(f"❌ OPENAI STREAM: Error parsing chunk: {e}")
                                    continue
                    else:
                        error_data = await response.json()
                        error_msg = error_data.get("error", {}).get("message", "Unknown error")
                        yield f"Error: {error_msg}"
                        
        except Exception as e:
            logger.error(f"❌ OPENAI STREAM: Error in streaming: {e}", exc_info=True)
            yield f"Error: {str(e)}"