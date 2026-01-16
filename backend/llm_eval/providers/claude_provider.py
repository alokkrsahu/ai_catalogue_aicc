import aiohttp
import time
import logging
import json
from .base import LLMProvider, LLMResponse
from typing import Dict, Any, Optional, List, AsyncGenerator

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
    
    def format_request_body(
        self, 
        prompt: Optional[str] = None, 
        messages: Optional[List[Dict[str, str]]] = None,
        stream: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Format request body for Claude API.
        
        If messages is provided, use it directly (native format).
        Otherwise, fall back to prompt string (backward compatibility).
        """
        if messages:
            # Validate messages format
            from agent_orchestration.message_converter import validate_messages_format
            is_valid, error_msg = validate_messages_format(messages)
            if not is_valid:
                logger.error(f"❌ CLAUDE: Invalid messages format: {error_msg}")
                raise ValueError(f"Invalid messages format: {error_msg}")
            
            # Extract system message if present
            system_message_content = None
            claude_messages = []
            for msg in messages:
                if msg.get("role") == "system":
                    system_message_content = msg.get("content")
                else:
                    claude_messages.append(msg)
            
            if not claude_messages:
                raise ValueError("No user or assistant messages provided for Claude API")
            
            body = {
                "model": self.model,
                "max_tokens": self.max_tokens,
                "messages": claude_messages
            }
            if system_message_content:
                body["system"] = system_message_content
            if stream:
                body["stream"] = True
            return body
        elif prompt:
            # Fallback to prompt string (backward compatibility)
            body = {
            "model": self.model,
            "max_tokens": self.max_tokens,
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
            content = response_data.get("content", [])
            stop_reason = response_data.get("stop_reason")
            usage = response_data.get("usage", {})
            output_tokens = usage.get("output_tokens", 0)
            
            # Log detailed response info for debugging
            logger.debug(f"🔍 CLAUDE PARSE: content length={len(content)}, stop_reason={stop_reason}, output_tokens={output_tokens}")
            
            if not content:
                # Content is empty - check if this is expected based on stop_reason
                if stop_reason == "content_filtered":
                    raise ValueError("Response was filtered by content safety filters")
                elif stop_reason == "max_tokens":
                    raise ValueError("Response was truncated due to max_tokens limit")
                elif output_tokens > 0:
                    # This is unusual: we have output tokens but no content
                    # This can happen if Claude generated content but it was filtered or not included
                    # Log this as a warning and return a default message to allow workflow to continue
                    logger.warning(f"⚠️ CLAUDE PARSE: Empty content but output_tokens={output_tokens}, stop_reason={stop_reason}")
                    logger.warning(f"⚠️ CLAUDE PARSE: This may indicate content filtering or API issue. Returning default message.")
                    # Return a default message instead of empty string to allow workflow to continue
                    default_message = "I apologize, but I was unable to generate a response. This may be due to content filtering or an API issue."
                    return default_message, output_tokens
                else:
                    raise ValueError(f"No content in response. Stop reason: {stop_reason}")
            
            # Extract text from first content block
            first_content = content[0]
            if not isinstance(first_content, dict):
                raise ValueError(f"Expected content block to be a dict, got {type(first_content)}")
            
            # Check content block type
            content_type = first_content.get("type")
            if content_type != "text":
                raise ValueError(f"Unsupported content type: {content_type}. Expected 'text'")
            
            text = first_content.get("text")
            
            # Handle None or empty content
            if text is None:
                # Check for stop_reason to understand why content is None
                if stop_reason == "max_tokens":
                    raise ValueError("Response was truncated due to max_tokens limit")
                elif stop_reason == "stop_sequence":
                    raise ValueError("Response stopped at stop sequence")
                elif stop_reason == "content_filtered":
                    raise ValueError("Response was filtered by content safety filters")
                elif stop_reason:
                    raise ValueError(f"Response text is None. Stop reason: {stop_reason}")
                else:
                    raise ValueError("Response text is None without stop_reason")
            
            # Ensure text is a string
            text = str(text) if text is not None else ""
            
            if not text.strip():
                # Empty text after stripping whitespace
                if output_tokens > 0:
                    logger.warning(f"⚠️ CLAUDE PARSE: Empty text but output_tokens={output_tokens}")
                raise ValueError(f"Response text is empty or whitespace only. Stop reason: {stop_reason}")
            
        except (KeyError, IndexError, ValueError) as e:
            # Log full response for debugging
            logger.error(f"❌ CLAUDE PARSE: Error parsing response: {e}")
            logger.error(f"❌ CLAUDE PARSE: Full response data: {response_data}")
            raise ValueError(f"Failed to parse Claude response: {e}. Response data: {response_data}")
        
        token_count = response_data.get("usage", {}).get("output_tokens")
        return text, token_count
    
    def estimate_cost(self, token_count: Optional[int]) -> Optional[float]:
        if not token_count:
            return None
        return (token_count / 1000) * 0.015  # Rough estimate
    
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
                provider="claude",
                response_time_ms=0,
                error="Either 'prompt' or 'messages' must be provided"
            )
        
        try:
            request_body = self.format_request_body(prompt=prompt, messages=messages, **kwargs)
            logger.info(f"🔍 CLAUDE REQUEST: Model={self.model}, Body keys={list(request_body.keys())}")
            if messages:
                logger.info(f"🔍 CLAUDE REQUEST: Input messages count={len(messages)}")
                for i, msg in enumerate(messages[:5]):  # Log first 5 messages
                    role = msg.get('role', 'unknown')
                    content = str(msg.get('content', ''))
                    content_preview = content[:150] + "..." if len(content) > 150 else content
                    logger.info(f"🔍 CLAUDE REQUEST: Message {i}: role={role}, content_length={len(content)}, preview={content_preview}")
            
            # Log the actual request body structure (without full content to avoid spam)
            request_summary = {
                "model": request_body.get("model"),
                "max_tokens": request_body.get("max_tokens"),
                "has_system": "system" in request_body,
                "messages_count": len(request_body.get("messages", [])),
                "messages_sample": [
                    {"role": msg.get("role"), "content_length": len(str(msg.get("content", ""))), "content_preview": (str(msg.get("content", ""))[:100] + "..." if len(str(msg.get("content", ""))) > 100 else str(msg.get("content", "")))}
                    for msg in request_body.get("messages", [])[:3]
                ]
            }
            logger.info(f"🔍 CLAUDE REQUEST SUMMARY: {json.dumps(request_summary, indent=2)}")
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                async with session.post(
                    self.base_url,
                    headers=self.get_headers(),
                    json=request_body
                ) as response:
                    response_time_ms = int((time.time() - start_time) * 1000)
                    
                    if response.status == 200:
                        data = await response.json()
                        logger.info(f"🔍 CLAUDE RESPONSE: Status=200, content_length={len(data.get('content', []))}, stop_reason={data.get('stop_reason')}, usage={data.get('usage', {})}")
                        # Log full response when content is empty for debugging
                        if not data.get('content') or len(data.get('content', [])) == 0:
                            logger.warning(f"⚠️ CLAUDE RESPONSE: Empty content! Full response: {json.dumps(data, indent=2)}")
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
                        # Handle non-200 responses
                        try:
                            error_data = await response.json()
                            # Anthropic error format: {"error": {"type": "...", "message": "..."}}
                            error_message = "Unknown error"
                            if isinstance(error_data, dict):
                                error_obj = error_data.get("error", {})
                                if isinstance(error_obj, dict):
                                    error_message = error_obj.get("message", error_obj.get("type", "Unknown error"))
                                elif isinstance(error_obj, str):
                                    error_message = error_obj
                                else:
                                    # Fallback: try to extract any error message
                                    error_message = str(error_data.get("error", error_data))
                            
                            logger.error(f"❌ CLAUDE: API error response: {error_data}")
                            logger.error(f"❌ CLAUDE: Request model: {self.model}, Status: {response.status}")
                            return LLMResponse(
                                text="",
                                model=self.model,
                                provider="claude",
                                response_time_ms=response_time_ms,
                                error=f"Claude API error: {error_message}"
                            )
                        except Exception as parse_error:
                            # If we can't parse the error response, return a generic error
                            error_text = await response.text()
                            logger.error(f"❌ CLAUDE: Failed to parse error response: {parse_error}. Response text: {error_text[:200]}")
                            logger.error(f"❌ CLAUDE: Request model: {self.model}, Status: {response.status}")
                        return LLMResponse(
                            text="",
                            model=self.model,
                            provider="claude",
                            response_time_ms=response_time_ms,
                                error=f"Claude API error (HTTP {response.status}): {error_text[:200]}"
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

    async def generate_response_stream(
        self,
        prompt: Optional[str] = None,
        messages: Optional[List[Dict[str, str]]] = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        Generate streaming response from Claude API.
        
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
                        buffer = ""
                        async for chunk in response.content.iter_any():
                            if not chunk:
                                continue
                            
                            buffer += chunk.decode('utf-8', errors='ignore')
                            
                            # Process complete SSE events
                            while '\n' in buffer:
                                line, buffer = buffer.split('\n', 1)
                                line = line.strip()
                                
                                if not line or line == 'event: completion':
                                    continue
                                
                                if line.startswith('data: '):
                                    try:
                                        data = json.loads(line[6:])  # Remove 'data: ' prefix
                                        if data.get("type") == "content_block_delta":
                                            delta = data.get("delta", {})
                                            text = delta.get("text")
                                            if text:
                                                yield text
                                        elif data.get("type") == "message_stop":
                                            break
                                    except json.JSONDecodeError:
                                        continue
                                    except Exception as e:
                                        logger.error(f"❌ CLAUDE STREAM: Error parsing chunk: {e}")
                                        continue
                    else:
                        error_data = await response.json()
                        error_msg = error_data.get("error", {}).get("message", "Unknown error")
                        yield f"Error: {error_msg}"
                        
        except Exception as e:
            logger.error(f"❌ CLAUDE STREAM: Error in streaming: {e}", exc_info=True)
            yield f"Error: {str(e)}"