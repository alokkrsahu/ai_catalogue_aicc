import aiohttp
import time
import logging
import json
from .base import LLMProvider, LLMResponse
from typing import Dict, Any, Optional, List, AsyncGenerator

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
    
    def format_request_body(
        self, 
        prompt: Optional[str] = None, 
        messages: Optional[List[Dict[str, str]]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Format request body for Gemini API.
        
        Gemini uses "contents" array with "parts" structure.
        Converts standard messages format [{"role": "...", "content": "..."}] 
        to Gemini format [{"role": "...", "parts": [{"text": "..."}]}]
        
        If messages is provided, convert to Gemini format.
        Otherwise, fall back to prompt string (backward compatibility).
        """
        if messages:
            # Validate messages format
            from agent_orchestration.message_converter import validate_messages_format
            is_valid, error_msg = validate_messages_format(messages)
            if not is_valid:
                logger.error(f"❌ GEMINI: Invalid messages format: {error_msg}")
                raise ValueError(f"Invalid messages format: {error_msg}")
            
            # Convert standard messages format to Gemini format
            contents = []
            system_messages = []
            
            # First pass: collect system messages
            for msg in messages:
                role = msg.get("role", "user")
                if role == "system":
                    system_messages.append(msg.get("content", ""))
            
            # Second pass: convert messages, prepending system messages to first user message
            system_prefix = "\n\n".join(system_messages) if system_messages else ""
            first_user_message_processed = False
            
            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                
                # Skip system messages (we'll prepend them)
                if role == "system":
                    continue
                
                # Map standard roles to Gemini roles
                # Gemini uses "user" and "model" (not "assistant")
                gemini_role = "model" if role == "assistant" else role
                
                # Prepend system messages to first user message
                if system_prefix and role == "user" and not first_user_message_processed:
                    content = f"{system_prefix}\n\n{content}" if content else system_prefix
                    first_user_message_processed = True
                
                if content.strip():  # Only add non-empty messages
                    contents.append({
                        "role": gemini_role,
                        "parts": [{"text": content.strip()}]
                    })
            
            # If we only had system messages, create a user message with them
            if not contents and system_prefix:
                contents.append({
                    "role": "user",
                    "parts": [{"text": system_prefix}]
                })
            
            return {
                "contents": contents
            }
        elif prompt:
            # Fallback to prompt string (backward compatibility)
            return {
                "contents": [{
                    "parts": [{"text": prompt}]
                }]
            }
        else:
            raise ValueError("Either 'prompt' or 'messages' must be provided")
    
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
                provider="gemini",
                response_time_ms=0,
                error="Either 'prompt' or 'messages' must be provided"
            )
        
        try:
            url = f"{self.base_url}?key={self.api_key}"
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                async with session.post(
                    url,
                    headers=self.get_headers(),
                    json=self.format_request_body(prompt=prompt, messages=messages, **kwargs)
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
    
    async def generate_response_stream(
        self,
        prompt: Optional[str] = None,
        messages: Optional[List[Dict[str, str]]] = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        Generate streaming response from Gemini API.
        
        Yields text chunks as they arrive from the API.
        """
        # Validate that either prompt or messages is provided
        if not prompt and not messages:
            yield f"Error: Either 'prompt' or 'messages' must be provided"
            return
        
        try:
            url = f"{self.base_url}?key={self.api_key}"
            request_body = self.format_request_body(prompt=prompt, messages=messages, **kwargs)
            
            # Gemini streaming uses streamGenerateContent endpoint
            stream_url = url.replace("generateContent", "streamGenerateContent")
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                async with session.post(
                    stream_url,
                    headers=self.get_headers(),
                    json=request_body
                ) as response:
                    if response.status == 200:
                        buffer = ""
                        async for chunk in response.content.iter_any():
                            if not chunk:
                                continue
                            
                            buffer += chunk.decode('utf-8', errors='ignore')
                            
                            # Process complete lines
                            while '\n' in buffer:
                                line, buffer = buffer.split('\n', 1)
                                line = line.strip()
                                
                                if not line:
                                    continue
                                
                                try:
                                    data = json.loads(line)
                                    candidates = data.get("candidates", [])
                                    if candidates:
                                        content = candidates[0].get("content", {})
                                        parts = content.get("parts", [])
                                        for part in parts:
                                            text = part.get("text")
                                            if text:
                                                yield text
                                except json.JSONDecodeError:
                                    continue
                                except Exception as e:
                                    logger.error(f"❌ GEMINI STREAM: Error parsing chunk: {e}")
                                    continue
                    else:
                        error_data = await response.json()
                        error_msg = error_data.get("error", {}).get("message", "Unknown error")
                        yield f"Error: {error_msg}"
                        
        except Exception as e:
            logger.error(f"❌ GEMINI STREAM: Error in streaming: {e}", exc_info=True)
            yield f"Error: {str(e)}"