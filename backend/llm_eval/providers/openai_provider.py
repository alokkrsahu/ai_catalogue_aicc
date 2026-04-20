import aiohttp
import time
import logging
import json
from .base import LLMProvider, LLMResponse
from typing import Dict, Any, Optional, List, AsyncGenerator

logger = logging.getLogger(__name__)

RESPONSES_API_BASE_URL = "https://api.openai.com/v1/responses"


class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = "gpt-3.5-turbo", **kwargs):
        super().__init__(api_key, model, **kwargs)
        self.base_url = "https://api.openai.com/v1/chat/completions"
    
    @staticmethod
    def _messages_contain_file_refs(messages: Optional[List[Dict[str, Any]]]) -> bool:
        """Return True if any message has content as list with a part of type 'file' (file attachment)."""
        if not messages:
            return False
        for msg in messages:
            content = msg.get("content")
            if not isinstance(content, list):
                continue
            for part in content:
                if isinstance(part, dict) and part.get("type") == "file":
                    return True
        return False
    
    @staticmethod
    def _build_responses_api_input(messages: List[Dict[str, Any]]) -> tuple[Optional[str], List[Dict[str, Any]]]:
        """
        Build (instructions, input_items) for OpenAI Responses API from Chat-style messages.
        instructions = system message content; input_items = list of { role, content } with input_text / input_file parts.
        Also handles assistant (with tool_calls) and tool result messages for tool-calling loops.
        File refs are included only in the last user message to avoid duplicate file refs and empty responses.
        """
        instructions = None
        input_items = []
        for msg in messages:
            role = (msg.get("role") or "").strip().lower()
            content = msg.get("content")

            if role == "system":
                if isinstance(content, str):
                    instructions = content
                elif isinstance(content, list):
                    text_parts = [p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text"]
                    instructions = " ".join(str(t) for t in text_parts) if text_parts else None
                else:
                    instructions = str(content) if content else None
                continue

            if role == "user":
                parts = []
                if isinstance(content, str):
                    if content.strip():
                        parts.append({"type": "input_text", "text": content})
                elif isinstance(content, list):
                    for p in content:
                        if not isinstance(p, dict):
                            continue
                        t = p.get("type")
                        if t == "text":
                            text_val = p.get("text")
                            if text_val is not None:
                                parts.append({"type": "input_text", "text": str(text_val)})
                        elif t == "file":
                            file_id = (p.get("file") or {}).get("file_id") or p.get("file_id")
                            if file_id:
                                parts.append({"type": "input_file", "file_id": str(file_id)})
                if parts:
                    input_items.append({"role": "user", "content": parts})

            elif role == "assistant":
                # Assistant message — may have tool_calls or plain text
                tool_calls = msg.get("tool_calls")
                if tool_calls:
                    # Convert Chat Completions tool_calls format to Responses API function_call items
                    for tc in tool_calls:
                        fn = tc.get("function", {})
                        input_items.append({
                            "type": "function_call",
                            "id": tc.get("id", ""),
                            "name": fn.get("name", ""),
                            "arguments": fn.get("arguments", "{}"),
                        })
                elif content and isinstance(content, str) and content.strip():
                    input_items.append({"role": "assistant", "content": [{"type": "output_text", "text": content}]})

            elif role == "tool":
                # Tool result message — convert to Responses API function_call_output
                input_items.append({
                    "type": "function_call_output",
                    "call_id": msg.get("tool_call_id", ""),
                    "output": str(content) if content else "",
                })

        # Include file refs only in the last user message to avoid API empty responses
        user_items = [item for item in input_items if isinstance(item, dict) and item.get("role") == "user"]
        if len(user_items) > 1:
            last_user = user_items[-1]
            has_file = any(
                isinstance(p, dict) and p.get("type") == "input_file"
                for p in (last_user.get("content") or [])
            )
            if has_file:
                for item in user_items[:-1]:
                    content = item.get("content") or []
                    content_no_file = [p for p in content if not (isinstance(p, dict) and p.get("type") == "input_file")]
                    if len(content_no_file) != len(content):
                        item["content"] = content_no_file
                        logger.info(f"🔍 OPENAI RESPONSES API: Removed file refs from non-last user message to avoid duplicate file refs")
        return instructions, input_items
    
    def _parse_responses_api_response(self, data: Dict[str, Any]) -> tuple[str, Optional[int]]:
        """Extract aggregated text, tool_calls, and total_tokens from Responses API response."""
        usage = data.get("usage") or {}
        token_count = usage.get("total_tokens")
        output = data.get("output") or []
        logger.info(f"🔍 OPENAI RESPONSES API: status={data.get('status')!r}, output_len={len(output)}, usage={token_count}")
        text_parts = []
        tool_calls = []
        for item in output:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "message":
                for part in (item.get("content") or []):
                    if isinstance(part, dict) and part.get("type") == "output_text":
                        t = part.get("text")
                        if t is not None:
                            text_parts.append(str(t))
            elif item.get("type") == "function_call":
                # Convert Responses API function_call to Chat Completions tool_calls format
                tool_calls.append({
                    "id": item.get("id", item.get("call_id", "")),
                    "type": "function",
                    "function": {
                        "name": item.get("name", ""),
                        "arguments": item.get("arguments", "{}"),
                    }
                })
        text = "".join(text_parts)
        if tool_calls:
            self._last_tool_calls = tool_calls
            self._last_finish_reason = "tool_calls"
            logger.info(f"🔍 OPENAI RESPONSES API: Found {len(tool_calls)} tool calls")
        else:
            self._last_tool_calls = None
            self._last_finish_reason = "stop"
        if not text and not tool_calls and output:
            logger.warning(f"🔍 OPENAI RESPONSES API: No output_text or tool_calls in output; output length={len(output)}")
        if not text and not tool_calls:
            logger.warning(f"🔍 OPENAI RESPONSES API: Empty response; full output sample: {output[:2] if output else []}")
        return text, token_count
    
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
            
            body = {
                "model": self.model,
                "messages": messages
            }
            if stream:
                body["stream"] = True
            tools = kwargs.get("tools")
            if tools:
                body["tools"] = tools
                tool_choice = kwargs.get("tool_choice")
                if tool_choice:
                    body["tool_choice"] = tool_choice
            # Sampling parameters — must be passed explicitly or OpenAI defaults
            # to temperature=1.0 which causes cross-language token drift (e.g.
            # a single Hindi word sampled in the middle of an English response).
            # Fallback order: explicit kwarg → self.temperature (set by
            # llm_provider_manager from agent_config) → omit (API default).
            temperature = kwargs.get("temperature", getattr(self, "temperature", None))
            if temperature is not None:
                body["temperature"] = float(temperature)
            top_p = kwargs.get("top_p")
            if top_p is not None:
                body["top_p"] = float(top_p)
            max_tokens = kwargs.get("max_tokens")
            if max_tokens is not None:
                body["max_tokens"] = int(max_tokens)
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
        try:
            choices = response_data.get("choices", [])
            if not choices:
                logger.error(f"❌ OPENAI: No choices in response data: {response_data}")
                raise ValueError("No choices in response")
            
            message = choices[0].get("message", {})
            finish_reason = choices[0].get("finish_reason")
            raw_content = message.get("content")
            
            # Tool calls: LLM wants to invoke tools — content may be None
            raw_tool_calls = message.get("tool_calls")
            if raw_tool_calls and finish_reason in ("tool_calls", "stop"):
                normalized = []
                for tc in raw_tool_calls:
                    fn = tc.get("function", {})
                    try:
                        args = json.loads(fn.get("arguments", "{}"))
                    except (json.JSONDecodeError, TypeError):
                        args = {"raw": fn.get("arguments", "")}
                    normalized.append({
                        "id": tc.get("id", ""),
                        "name": fn.get("name", ""),
                        "arguments": args,
                    })
                self._last_tool_calls = normalized
                self._last_finish_reason = finish_reason
                token_count = response_data.get("usage", {}).get("total_tokens")
                return raw_content or "", token_count
            
            self._last_tool_calls = None
            self._last_finish_reason = finish_reason
            
            logger.info(f"🔍 OPENAI: Extracted content from response - type: {type(raw_content)}, value: {repr(raw_content)[:100] if raw_content else 'None'}")
            
            if raw_content is None:
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
            
            # Content as list (e.g. reasoning/multimodal response parts)
            if isinstance(raw_content, list):
                logger.info(f"🔍 OPENAI: Content is list with {len(raw_content)} parts; extracting text from output_text/text parts")
                text_parts = []
                for part in raw_content:
                    if not isinstance(part, dict):
                        continue
                    part_type = part.get("type")
                    text_val = part.get("text")
                    if part_type in ("output_text", "text") and text_val is not None:
                        text_parts.append(str(text_val))
                text = "".join(text_parts) if text_parts else ""
                if not text and raw_content:
                    logger.warning(f"🔍 OPENAI: Content list had no output_text/text parts; raw content shape: {[type(p).__name__ for p in raw_content[:5]]}")
            else:
                # Content as string
                text = str(raw_content) if raw_content else ""
            
            logger.info(f"🔍 OPENAI: After extraction - text length: {len(text)}, text: {repr(text)[:100]}")
            
            # Explicitly handle empty string content
            if text == "" or (text is not None and not text.strip()):
                finish_reason = choices[0].get("finish_reason")
                error_msg = f"Response content is empty (finish_reason: {finish_reason})"
                logger.error(f"❌ OPENAI: {error_msg}")
                if finish_reason == "length":
                    raise ValueError("Response was truncated due to max_tokens limit")
                elif finish_reason == "content_filter":
                    raise ValueError("Response was filtered by content safety filters")
                elif finish_reason:
                    raise ValueError(f"Response incomplete: finish_reason={finish_reason}")
                else:
                    raise ValueError("Response content is empty without finish_reason")
            
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
            # Use Responses API when messages contain file refs (required for PDF attachments).
            # Responses API supports both file attachments and tool calling.
            has_files = bool(messages and self._messages_contain_file_refs(messages))
            has_tools = bool(kwargs.get("tools"))
            use_responses_api = has_files
            if use_responses_api:
                instructions, input_items = self._build_responses_api_input(messages)
                if not instructions and not input_items:
                    response_time_ms = int((time.time() - start_time) * 1000)
                    return LLMResponse(
                        text="",
                        model=self.model,
                        provider="openai",
                        response_time_ms=response_time_ms,
                        error="Responses API requires at least one non-empty input (instructions or user input items)"
                    )
                body = {
                    "model": self.model,
                    "input": input_items,
                    "store": False,
                }
                # Ensure long-form outputs (like document summaries) can fit.
                # Responses API uses `max_output_tokens` for output length.
                if self.max_tokens:
                    body["max_output_tokens"] = int(self.max_tokens)
                if instructions:
                    body["instructions"] = instructions
                # Respect per-agent temperature on the Responses API path too
                # (file-attachment requests). Without this the API defaults
                # to 1.0 and cross-language drift can appear in doc summaries.
                responses_temperature = kwargs.get("temperature", getattr(self, "temperature", None))
                if responses_temperature is not None:
                    body["temperature"] = float(responses_temperature)
                # Include tools in Responses API format when present
                if has_tools:
                    tools_list = kwargs.get("tools", [])
                    responses_tools = []
                    for tool in tools_list:
                        if tool.get("type") == "function":
                            responses_tools.append({
                                "type": "function",
                                "name": tool["function"]["name"],
                                "description": tool["function"].get("description", ""),
                                "parameters": tool["function"].get("parameters", {}),
                            })
                    if responses_tools:
                        body["tools"] = responses_tools
                        logger.info(f"🔍 OPENAI: Responses API with {len(responses_tools)} tools + file attachments")
                url = RESPONSES_API_BASE_URL
                logger.info(f"🔍 OPENAI: Using Responses API for file attachments; model: {self.model!r}")
            else:
                body = self.format_request_body(prompt=prompt, messages=messages, **kwargs)
                url = self.base_url
            # Diagnostic: log model and sanitized request when file refs (array content) are present
            logger.info(f"🔍 OPENAI: Sending request to model: {self.model!r}")
            if messages:
                for i, msg in enumerate(messages):
                    content = msg.get("content")
                    if isinstance(content, list):
                        part_types = [p.get("type", "?") for p in content if isinstance(p, dict)]
                        logger.info(f"🔍 OPENAI: Message[{i}] role={msg.get('role')!r} content_parts={part_types} (file refs present)")
            timeout_sec = max(self.timeout, 300) if (use_responses_api or has_tools) else self.timeout
            logger.info(f"🔍 OPENAI: Request timeout={timeout_sec}s, use_responses_api={use_responses_api}, self.timeout={self.timeout}")
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout_sec, sock_read=timeout_sec, sock_connect=60)) as session:
                async with session.post(url, headers=self.get_headers(), json=body) as response:
                    response_time_ms = int((time.time() - start_time) * 1000)
                    try:
                        response_body = await response.json()
                    except aiohttp.ContentTypeError as e:
                        logger.error(f"❌ OPENAI: API response was not JSON (ContentTypeError): {e}")
                        return LLMResponse(
                            text="",
                            model=self.model,
                            provider="openai",
                            response_time_ms=response_time_ms,
                            error="API response was not valid JSON (wrong Content-Type or empty body)"
                        )
                    except (ValueError, json.JSONDecodeError) as e:
                        logger.error(f"❌ OPENAI: API response JSON decode error: {e}")
                        return LLMResponse(
                            text="",
                            model=self.model,
                            provider="openai",
                            response_time_ms=response_time_ms,
                            error="API response was not valid JSON"
                        )
                    
                    if response.status != 200:
                        error_msg = (
                            response_body.get("error", {}).get("message")
                            if isinstance(response_body.get("error"), dict)
                            else (response_body.get("error") or str(response_body))
                        )
                        if not isinstance(error_msg, str):
                            error_msg = str(error_msg) if error_msg is not None else "Unknown error"
                        logger.error(f"❌ OPENAI: API error (status={response.status}), model={self.model!r}: {error_msg}")
                        return LLMResponse(
                            text="",
                            model=self.model,
                            provider="openai",
                            response_time_ms=response_time_ms,
                            error=error_msg or f"API error (status {response.status})"
                        )
                    
                    data = response_body
                    logger.debug(f"🔍 OPENAI: Raw API response for model {self.model}: {data}")
                    
                    if use_responses_api:
                        status = data.get("status")
                        err_obj = data.get("error")
                        output_len = len(data.get("output") or [])
                        err_keys = list(err_obj.keys()) if isinstance(err_obj, dict) else None
                        logger.info(f"🔍 OPENAI RESPONSES API: status={status!r}, has_error={err_obj is not None}, error_keys={err_keys}, output_len={output_len}")
                        if status == "failed" or data.get("error"):
                            err = data.get("error")
                            error_msg = err.get("message", str(err)) if isinstance(err, dict) else str(err or "Unknown error")
                            error_msg = (error_msg or "Responses API returned an error with no message").strip() or "Unknown error"
                            logger.error(f"❌ OPENAI: Responses API failed: {error_msg}")
                            logger.error(f"❌ OPENAI: Responses API failed response: status={status!r}, error={data.get('error')!r}, output_len={len(data.get('output') or [])}")
                            return LLMResponse(
                                text="",
                                model=self.model,
                                provider="openai",
                                response_time_ms=response_time_ms,
                                error=error_msg
                            )
                        if status not in ("completed", None):
                            error_msg = (f"Responses API status not completed: {status!r}").strip() or "Unknown error"
                            logger.error(f"❌ OPENAI: {error_msg}")
                            return LLMResponse(
                                text="",
                                model=self.model,
                                provider="openai",
                                response_time_ms=response_time_ms,
                                error=error_msg
                            )
                        text, token_count = self._parse_responses_api_response(data)
                    else:
                        try:
                            self._last_tool_calls = None
                            self._last_finish_reason = None
                            logger.info(f"🔍 OPENAI: About to parse response for model {self.model}")
                            text, token_count = self.parse_response(data)
                            logger.info(f"🔍 OPENAI: Parsed response - text length: {len(text) if text else 0}, token_count: {token_count}, text type: {type(text)}")
                        except ValueError as parse_error:
                            error_msg = (str(parse_error) or "Unknown error").strip() or "Unknown error"
                            logger.error(f"❌ OPENAI: parse_response raised ValueError: {error_msg}")
                            logger.error(f"❌ OPENAI: Response data that caused error: {data}")
                            return LLMResponse(
                                text="",
                                model=self.model,
                                provider="openai",
                                response_time_ms=response_time_ms,
                                error=error_msg
                            )
                    
                    # If tool_calls were returned, that's a valid response even with empty text
                    parsed_tool_calls = getattr(self, '_last_tool_calls', None)
                    parsed_finish_reason = getattr(self, '_last_finish_reason', None)
                    
                    if parsed_tool_calls:
                        return LLMResponse(
                            text=text or "",
                            model=self.model,
                            provider="openai",
                            response_time_ms=response_time_ms,
                            token_count=token_count,
                            cost_estimate=self.estimate_cost(token_count),
                            tool_calls=parsed_tool_calls,
                            finish_reason=parsed_finish_reason,
                        )
                    
                    if not text or not text.strip():
                        usage = data.get("usage", {})
                        error_msg = (f"OpenAI API returned empty response content (tokens: {usage})").strip() or "Unknown error"
                        logger.error(f"❌ OPENAI: {error_msg}")
                        if not use_responses_api:
                            choices = data.get("choices", [])
                            first_choice = choices[0] if choices else {}
                            logger.error(f"❌ OPENAI: choices[0] message={first_choice.get('message')!r}, finish_reason={first_choice.get('finish_reason')!r}, usage={usage!r}")
                        else:
                            logger.error(f"❌ OPENAI: Responses API response status={data.get('status')!r}, output_len={len(data.get('output') or [])}")
                        logger.error(f"❌ OPENAI: Full response data: {data}")
                        return LLMResponse(
                            text="",
                            model=self.model,
                            provider="openai",
                            response_time_ms=response_time_ms,
                            error=error_msg
                        )
                    
                    if not (text and text.strip()):
                        error_msg = "OpenAI API returned empty response content"
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
                        cost_estimate=self.estimate_cost(token_count),
                        finish_reason=parsed_finish_reason,
                    )
                        
        except Exception as e:
            response_time_ms = int((time.time() - start_time) * 1000)
            err_str = (str(e) or "Unknown error").strip() or "Unknown error"
            logger.error(f"❌ OPENAI: Unhandled exception ({type(e).__name__}): {err_str}", exc_info=True)
            return LLMResponse(
                text="",
                model=self.model,
                provider="openai",
                response_time_ms=response_time_ms,
                error=err_str
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