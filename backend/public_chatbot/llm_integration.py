"""
LLM Integration Service for Public Chatbot
Safely uses existing LLM infrastructure without impacting main system
"""
import logging
import os
from typing import Dict, Any, Optional, Generator
from datetime import datetime
import json

# Safely import existing LLM infrastructure
try:
    # Import existing LLM providers (your sophisticated system)
    import openai
    from django.conf import settings
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

logger = logging.getLogger('public_chatbot')


class PublicLLMService:
    """
    LLM service for public chatbot - safely integrates with existing infrastructure
    Uses system-level API keys, completely isolated from project-specific keys
    """
    
    def __init__(self):
        """Initialize with system-level API keys only (no project access)"""
        self.openai_client = None
        self.gemini_client = None
        self.anthropic_client = None
        
        # Initialize available providers using system settings
        self._initialize_providers()
    
    def _initialize_providers(self):
        """Initialize LLM providers using system-level keys"""
        try:
            # OpenAI initialization (using dedicated public chatbot key)
            if OPENAI_AVAILABLE:
                chatbot_openai_key = getattr(settings, 'AICC_CHATBOT_OPENAI_API_KEY', None) or os.getenv('AICC_CHATBOT_OPENAI_API_KEY')
                if chatbot_openai_key:
                    openai.api_key = chatbot_openai_key
                    self.openai_client = openai
                    logger.info("✅ OPENAI: Public chatbot client initialized with AICC_CHATBOT_OPENAI_API_KEY")
                else:
                    logger.warning("⚠️ OPENAI: No AICC_CHATBOT_OPENAI_API_KEY found")
            
            # Gemini initialization (using system key)
            if GEMINI_AVAILABLE:
                system_gemini_key = getattr(settings, 'GOOGLE_API_KEY', None) or os.getenv('GOOGLE_API_KEY')
                if system_gemini_key:
                    genai.configure(api_key=system_gemini_key)
                    self.gemini_client = genai
                    logger.info("✅ GEMINI: System-level client initialized")
                else:
                    logger.warning("⚠️ GEMINI: No system API key found")
            
            # Anthropic initialization (using system key)
            if ANTHROPIC_AVAILABLE:
                system_anthropic_key = getattr(settings, 'ANTHROPIC_API_KEY', None) or os.getenv('ANTHROPIC_API_KEY')
                if system_anthropic_key:
                    self.anthropic_client = anthropic.Anthropic(api_key=system_anthropic_key)
                    logger.info("✅ ANTHROPIC: System-level client initialized")
                else:
                    logger.warning("⚠️ ANTHROPIC: No system API key found")
                    
        except Exception as e:
            logger.error(f"❌ LLM: Provider initialization error: {e}")
    
    def generate_response(
        self, 
        prompt: str, 
        provider: str = 'openai', 
        model: str = 'gpt-3.5-turbo',
        max_tokens: int = 300,
        temperature: float = 0.7,
        system_prompt: str = None,
        request_id: str = None,
        stream: bool = False
    ) -> Dict[str, Any]:
        """
        Generate response using specified LLM provider
        
        Args:
            prompt: Enhanced prompt with context
            provider: LLM provider to use (openai, gemini, anthropic)
            model: Specific model to use
            max_tokens: Maximum response tokens
            temperature: Response creativity (0-1)
            system_prompt: Custom system prompt (if None, uses default)
            request_id: Request tracking ID
            stream: Whether to return streaming response (OpenAI only)
            
        Returns:
            Dict with response and metadata or streaming generator
        """
        start_time = datetime.now()
        
        try:
            # Route to appropriate provider
            if provider == 'openai':
                return self._generate_openai_response(prompt, model, max_tokens, temperature, system_prompt, request_id, stream)
            elif provider == 'gemini':
                if stream:
                    logger.warning(f"Streaming not supported for Gemini, falling back to non-streaming")
                return self._generate_gemini_response(prompt, model, max_tokens, temperature, system_prompt, request_id)
            elif provider == 'anthropic':
                if stream:
                    logger.warning(f"Streaming not supported for Anthropic, falling back to non-streaming")
                return self._generate_anthropic_response(prompt, model, max_tokens, temperature, system_prompt, request_id)
            else:
                # Fallback to OpenAI
                logger.warning(f"Unknown provider '{provider}', falling back to OpenAI")
                return self._generate_openai_response(prompt, 'gpt-3.5-turbo', max_tokens, temperature, system_prompt, request_id, stream)
                
        except Exception as e:
            end_time = datetime.now()
            response_time = int((end_time - start_time).total_seconds() * 1000)
            
            logger.error(f"❌ LLM: Response generation failed [{request_id}]: {e}")
            
            return {
                'success': False,
                'error': str(e),
                'error_type': 'llm_api_error',
                'response': self._get_fallback_response(),
                'provider': provider,
                'model': model,
                'tokens_used': 0,
                'response_time_ms': response_time
            }
    
    def _generate_openai_response(self, prompt: str, model: str, max_tokens: int, temperature: float, system_prompt: str, request_id: str, stream: bool = False) -> Dict[str, Any]:
        """Generate response using OpenAI API"""
        if not self.openai_client:
            raise Exception("OpenAI client not available")
        
        start_time = datetime.now()
        
        # System prompt must be provided - no fallbacks for public chatbot
        if not system_prompt:
            raise Exception("System prompt is required and must be provided from Django admin configuration")
        
        try:
            # Use max_completion_tokens for newer models, max_tokens for older ones
            completion_params = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                "timeout": 30,  # 30 second timeout
                "stream": stream
            }
            
            # Use appropriate parameter based on model
            # Use max_completion_tokens for all GPT models (GPT-3.5, GPT-4, GPT-5, etc.)
            if "gpt" in model.lower():
                # GPT-5 models need much higher token limits due to reasoning tokens
                if "gpt-5" in model.lower():
                    completion_params["max_completion_tokens"] = max_tokens * 3  # Triple the tokens for GPT-5
                    # GPT-5 models only support default temperature (1.0)
                    # Don't set temperature parameter
                else:
                    completion_params["max_completion_tokens"] = max_tokens
                    completion_params["temperature"] = temperature
            else:
                completion_params["max_tokens"] = max_tokens
                completion_params["temperature"] = temperature
            
            response = self.openai_client.chat.completions.create(**completion_params)
            
            # Handle streaming response
            if stream:
                return self._handle_openai_stream(response, model, request_id, start_time)
            
            # Handle non-streaming response (existing logic)
            
            end_time = datetime.now()
            response_time = int((end_time - start_time).total_seconds() * 1000)
            
            # Extract response data
            response_text = response.choices[0].message.content
            tokens_used = response.usage.total_tokens if hasattr(response, 'usage') else 0
            
            # Debug logging for empty responses
            if not response_text or response_text.strip() == "":
                logger.warning(f"⚠️ OPENAI: Empty response content [{request_id}]")
                logger.warning(f"⚠️ OPENAI: Full response object: {response}")
                logger.warning(f"⚠️ OPENAI: Response choices: {response.choices}")
                logger.warning(f"⚠️ OPENAI: Message object: {response.choices[0].message}")
                logger.warning(f"⚠️ OPENAI: Content field: '{response.choices[0].message.content}'")
                logger.warning(f"⚠️ OPENAI: Content type: {type(response.choices[0].message.content)}")
                logger.warning(f"⚠️ OPENAI: Model used: {model}")
                response_text = "I apologize, but I didn't receive a proper response. Please try again."
            
            logger.info(f"✅ OPENAI: Response generated [{request_id}] in {response_time}ms, {tokens_used} tokens, content_length: {len(response_text) if response_text else 0}")
            
            return {
                'success': True,
                'response': response_text,
                'provider': 'openai',
                'model': model,
                'tokens_used': tokens_used,
                'response_time_ms': response_time
            }
            
        except Exception as e:
            end_time = datetime.now()
            response_time = int((end_time - start_time).total_seconds() * 1000)
            
            logger.error(f"❌ OPENAI: API error [{request_id}]: {e}")
            raise Exception(f"OpenAI API error: {e}")
    
    def _handle_openai_stream(self, stream_response, model: str, request_id: str, start_time) -> Dict[str, Any]:
        """Handle OpenAI streaming response"""
        def stream_generator():
            try:
                collected_content = ""
                total_tokens = 0
                
                for chunk in stream_response:
                    if chunk.choices and chunk.choices[0].delta:
                        delta = chunk.choices[0].delta
                        if hasattr(delta, 'content') and delta.content:
                            content = delta.content
                            collected_content += content
                            
                            # Format as Server-Sent Events
                            chunk_data = {
                                "type": "content",
                                "content": content,
                                "request_id": request_id
                            }
                            yield f"data: {json.dumps(chunk_data)}\n\n"
                
                # Send completion event
                end_time = datetime.now()
                response_time = int((end_time - start_time).total_seconds() * 1000)
                
                completion_data = {
                    "type": "completion",
                    "request_id": request_id,
                    "response_time_ms": response_time,
                    "total_content": collected_content,
                    "model": model,
                    "provider": "openai",
                    "tokens_used": total_tokens
                }
                yield f"data: {json.dumps(completion_data)}\n\n"
                yield "data: [DONE]\n\n"
                
                logger.info(f"✅ OPENAI STREAM: Completed [{request_id}] in {response_time}ms")
                
            except Exception as e:
                logger.error(f"❌ OPENAI STREAM: Error [{request_id}]: {e}")
                error_data = {
                    "type": "error",
                    "error": str(e),
                    "request_id": request_id
                }
                yield f"data: {json.dumps(error_data)}\n\n"
        
        return {
            'success': True,
            'streaming': True,
            'generator': stream_generator(),
            'provider': 'openai',
            'model': model,
            'request_id': request_id
        }
    
    def _generate_gemini_response(self, prompt: str, model: str, max_tokens: int, temperature: float, system_prompt: str, request_id: str) -> Dict[str, Any]:
        """Generate response using Google Gemini API"""
        if not self.gemini_client:
            raise Exception("Gemini client not available")
        
        start_time = datetime.now()
        
        # System prompt must be provided - no fallbacks for public chatbot
        if not system_prompt:
            raise Exception("System prompt is required and must be provided from Django admin configuration")
        
        try:
            # Use gemini-pro model as default
            model_name = 'gemini-pro' if 'gemini' not in model else model
            
            generation_model = self.gemini_client.GenerativeModel(model_name)
            
            # Configure generation
            generation_config = {
                'max_output_tokens': max_tokens,
                'temperature': temperature,
            }
            
            # For Gemini, prepend system prompt to user prompt
            enhanced_prompt = f"{system_prompt}\n\n{prompt}"
            
            response = generation_model.generate_content(
                enhanced_prompt,
                generation_config=generation_config,
            )
            
            end_time = datetime.now()
            response_time = int((end_time - start_time).total_seconds() * 1000)
            
            # Extract response text
            response_text = response.text if hasattr(response, 'text') else str(response)
            
            # Estimate tokens (approximate)
            estimated_tokens = len(response_text.split()) * 1.3  # Rough estimate
            
            logger.info(f"✅ GEMINI: Response generated [{request_id}] in {response_time}ms, ~{estimated_tokens:.0f} tokens")
            
            return {
                'success': True,
                'response': response_text,
                'provider': 'gemini',
                'model': model_name,
                'tokens_used': int(estimated_tokens),
                'response_time_ms': response_time
            }
            
        except Exception as e:
            end_time = datetime.now()
            response_time = int((end_time - start_time).total_seconds() * 1000)
            
            logger.error(f"❌ GEMINI: API error [{request_id}]: {e}")
            raise Exception(f"Gemini API error: {e}")
    
    def _generate_anthropic_response(self, prompt: str, model: str, max_tokens: int, temperature: float, system_prompt: str, request_id: str) -> Dict[str, Any]:
        """Generate response using Anthropic Claude API"""
        if not self.anthropic_client:
            raise Exception("Anthropic client not available")
        
        start_time = datetime.now()
        
        # System prompt must be provided - no fallbacks for public chatbot
        if not system_prompt:
            raise Exception("System prompt is required and must be provided from Django admin configuration")
        
        try:
            # Use claude-3-haiku as default for public API (cost-effective)
            model_name = 'claude-3-haiku-20240307' if 'claude' not in model else model
            
            response = self.anthropic_client.messages.create(
                model=model_name,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt,  # Anthropic supports separate system parameter
                messages=[
                    {"role": "user", "content": prompt}
                ],
                timeout=30
            )
            
            end_time = datetime.now()
            response_time = int((end_time - start_time).total_seconds() * 1000)
            
            # Extract response data
            response_text = response.content[0].text if response.content else "No response generated"
            tokens_used = response.usage.input_tokens + response.usage.output_tokens if hasattr(response, 'usage') else 0
            
            logger.info(f"✅ ANTHROPIC: Response generated [{request_id}] in {response_time}ms, {tokens_used} tokens")
            
            return {
                'success': True,
                'response': response_text,
                'provider': 'anthropic',
                'model': model_name,
                'tokens_used': tokens_used,
                'response_time_ms': response_time
            }
            
        except Exception as e:
            end_time = datetime.now()
            response_time = int((end_time - start_time).total_seconds() * 1000)
            
            logger.error(f"❌ ANTHROPIC: API error [{request_id}]: {e}")
            raise Exception(f"Anthropic API error: {e}")
    
    def _get_fallback_response(self) -> str:
        """Get fallback response when all providers fail"""
        return """I apologize, but I'm currently unable to generate a response due to a technical issue. Please try again in a few moments. 

If the problem persists, you can:
- Check your internet connection
- Try rephrasing your question
- Contact support if needed

Thank you for your patience."""
    
    def get_available_providers(self) -> Dict[str, bool]:
        """Get list of available LLM providers"""
        return {
            'openai': self.openai_client is not None,
            'gemini': self.gemini_client is not None,
            'anthropic': self.anthropic_client is not None,
        }
    
    def health_check(self) -> Dict[str, Any]:
        """Check health of LLM services"""
        providers = self.get_available_providers()
        available_count = sum(providers.values())
        
        return {
            'status': 'healthy' if available_count > 0 else 'unhealthy',
            'available_providers': providers,
            'total_available': available_count,
            'recommended_provider': self._get_recommended_provider(providers),
            'last_check': datetime.now().isoformat()
        }
    
    def _get_recommended_provider(self, providers: Dict[str, bool]) -> str:
        """Get recommended provider based on availability and cost"""
        if providers.get('openai'):
            return 'openai'  # Good balance of cost and quality
        elif providers.get('gemini'):
            return 'gemini'  # Good for general queries
        elif providers.get('anthropic'):
            return 'anthropic'  # High quality but more expensive
        else:
            return 'none'