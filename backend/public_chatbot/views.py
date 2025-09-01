"""
Public Chatbot API Views - Completely Isolated Implementation
ZERO impact on existing AI Catalogue system
Uses ChromaDB + existing LLM infrastructure safely
"""
from django.http import JsonResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.core.cache import cache
import json
import logging
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

# Rate limiting (install: pip install django-ratelimit)
try:
    from django_ratelimit.decorators import ratelimit
    RATELIMIT_AVAILABLE = True
except ImportError:
    RATELIMIT_AVAILABLE = False
    # Fallback decorator that does nothing
    def ratelimit(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

# Import isolated services
from .services import PublicKnowledgeService, ChatbotSecurityService
from .models import PublicChatRequest, IPUsageLimit, ChatbotConfiguration
from .llm_integration import PublicLLMService

logger = logging.getLogger('public_chatbot')


def _add_cors_headers(response, request):
    """
    Add CORS headers to response for public chatbot API
    """
    origin = request.META.get('HTTP_ORIGIN')
    
    # Allowed origins for public chatbot
    allowed_origins = [
        'https://oxfordcompetencycenters.github.io',
        'https://aicc.uksouth.cloudapp.azure.com',
        'http://localhost:3000',
        'http://localhost:5173',
        'http://localhost:8080',
        'http://127.0.0.1:3000',
        'http://127.0.0.1:5173',
        'http://127.0.0.1:8080',
    ]
    
    if origin in allowed_origins:
        response['Access-Control-Allow-Origin'] = origin
    else:
        response['Access-Control-Allow-Origin'] = '*'  # Fallback for public API
    
    response['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response['Access-Control-Allow-Headers'] = 'Origin, Content-Type, Accept, Authorization, X-Requested-With, Cache-Control'
    response['Access-Control-Allow-Credentials'] = 'true'
    response['Access-Control-Max-Age'] = '86400'
    
    return response


def _rate_limit_decorator():
    """Apply rate limiting if django-ratelimit is available"""
    if RATELIMIT_AVAILABLE:
        return ratelimit(key='ip', rate='10/m', method='POST', block=True)
    else:
        # Custom rate limiting fallback
        def decorator(func):
            def wrapper(request, *args, **kwargs):
                client_ip = _get_client_ip(request)
                
                # Check custom rate limiting
                if _is_rate_limited(client_ip):
                    return JsonResponse({
                        'status': 'error',
                        'error': 'Rate limit exceeded. Please try again later.',
                        'retry_after': 60
                    }, status=429)
                
                return func(request, *args, **kwargs)
            return wrapper
        return decorator


def _get_client_ip(request) -> str:
    """
    Extract real client IP address handling proxies and load balancers
    Checks proxy headers in order of preference
    """
    # Check proxy headers in order of preference
    ip_headers = [
        'HTTP_X_FORWARDED_FOR',      # Standard proxy header
        'HTTP_X_REAL_IP',            # Nginx real IP
        'HTTP_CF_CONNECTING_IP',     # Cloudflare
        'HTTP_X_FORWARDED',          # Alternative forwarded header
        'HTTP_X_CLUSTER_CLIENT_IP',  # Load balancer
        'HTTP_FORWARDED_FOR',        # RFC 7239
        'HTTP_FORWARDED',            # RFC 7239
        'REMOTE_ADDR'                # Direct connection (fallback)
    ]
    
    for header in ip_headers:
        ip_list = request.META.get(header, '').strip()
        if ip_list:
            # Handle comma-separated IPs (X-Forwarded-For can have multiple)
            # First IP is usually the original client
            ip = ip_list.split(',')[0].strip()
            
            # Validate IP format
            import ipaddress
            try:
                ipaddress.ip_address(ip)
                # Skip private/local IPs if we have proxy headers
                if header != 'REMOTE_ADDR' or not _is_private_ip(ip):
                    return ip
            except ValueError:
                continue
    
    return 'unknown'


def _is_private_ip(ip: str) -> bool:
    """Check if IP is private/local"""
    import ipaddress
    try:
        ip_obj = ipaddress.ip_address(ip)
        return ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local
    except ValueError:
        return False


def _is_rate_limited(ip_address: str) -> bool:
    """Custom rate limiting implementation"""
    try:
        # Use cache for simple rate limiting
        cache_key = f"rate_limit_{ip_address}"
        current_count = cache.get(cache_key, 0)
        
        if current_count >= 10:  # 10 requests per minute
            return True
        
        # Increment counter
        cache.set(cache_key, current_count + 1, 60)  # 60 seconds
        return False
        
    except Exception as e:
        logger.error(f"Rate limiting error for {ip_address}: {e}")
        return False  # Allow on error


@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
@never_cache
@_rate_limit_decorator()
def public_chat_api(request):
    """
    Public Chatbot API Endpoint - Completely Isolated
    
    POST /api/public-chatbot/
    
    Integrates with ChromaDB (isolated) + existing LLM infrastructure
    Zero impact on main AI Catalogue system
    """
    # Handle CORS preflight
    if request.method == 'OPTIONS':
        response = JsonResponse({'status': 'ok'})
        _add_cors_headers(response, request)
        return response
    
    # Generate unique request ID for tracking
    client_ip = _get_client_ip(request)
    timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
    request_id = f"pub_{timestamp}_{client_ip.replace('.', '')[-4:]}_{hash(request.body) % 10000:04d}"
    
    # Initialize request tracking
    chat_request = None
    start_time = timezone.now()
    
    try:
        # Check if chatbot is enabled
        config = ChatbotConfiguration.get_config()
        if not config.is_enabled or config.maintenance_mode:
            response = JsonResponse({
                'status': 'error',
                'error': 'Service temporarily unavailable' if config.maintenance_mode else 'Service disabled',
                'message': config.maintenance_message if config.maintenance_mode else 'Chatbot service is currently disabled',
                'request_id': request_id
            }, status=503)
            _add_cors_headers(response, request)
            return response
        
        # Parse request body
        try:
            data = json.loads(request.body) if request.body else {}
        except json.JSONDecodeError:
            response = JsonResponse({
                'status': 'error',
                'error': 'Invalid JSON format',
                'request_id': request_id
            }, status=400)
            _add_cors_headers(response, request)
            return response
        
        # Extract and validate parameters
        message = data.get('message', '').strip()
        session_id = data.get('session_id', '')  # Optional conversation tracking
        context_limit = min(data.get('context_limit', config.max_search_results), config.max_search_results)  # Use config setting
        conversation_context = data.get('conversation', [])  # Full conversation history
        
        # Get client metadata
        user_agent = request.META.get('HTTP_USER_AGENT', '')[:300]
        origin_domain = request.META.get('HTTP_ORIGIN', '')
        
        # Create request tracking record
        try:
            chat_request = PublicChatRequest(
                request_id=request_id,
                session_id=session_id[:100],  # Truncate for safety
                ip_address=client_ip,
                user_agent=user_agent,
                origin_domain=origin_domain[:200],  # Truncate for safety
                message_preview=message[:100],  # Privacy-safe truncation
                message_length=len(message),
                message_hash=hashlib.sha256(message.encode()).hexdigest(),
                created_at=start_time
            )
        except Exception as e:
            logger.error(f"Failed to create request record [{request_id}]: {e}")
            # Continue without tracking if DB fails
        
        # Security validation
        security_result = ChatbotSecurityService.validate_input(message, client_ip)
        if not security_result['valid']:
            logger.warning(f"🚨 SECURITY: Invalid input from {client_ip}: {security_result['reason']}")
            
            # Update request record
            if chat_request:
                chat_request.status = 'security_violation'
                chat_request.error_type = security_result['reason']
                chat_request.error_message = security_result['error']
                chat_request.completed_at = timezone.now()
                try:
                    chat_request.save()
                except:
                    pass
            
            # Update IP tracking
            _update_ip_security_violation(client_ip)
            
            response = JsonResponse({
                'status': 'error',
                'error': security_result['error'],
                'request_id': request_id
            }, status=400)
            _add_cors_headers(response, request)
            return response
        
        # Check IP-based rate limiting
        if ChatbotSecurityService.check_rate_limit_exceeded(client_ip):
            logger.warning(f"🚨 RATE LIMIT: IP {client_ip} exceeded limits")
            
            if chat_request:
                chat_request.status = 'rate_limited'
                chat_request.error_message = 'IP rate limit exceeded'
                chat_request.completed_at = timezone.now()
                try:
                    chat_request.save()
                except:
                    pass
            
            response = JsonResponse({
                'status': 'error',
                'error': 'Rate limit exceeded. Please try again later.',
                'retry_after': 3600,  # 1 hour
                'request_id': request_id
            }, status=429)
            _add_cors_headers(response, request)
            return response
        
        logger.info(f"📨 PUBLIC API: Processing request [{request_id}] from {client_ip}: '{message[:50]}...'")
        
        # Search ChromaDB for relevant context (completely isolated from Milvus)
        context_results = []
        chroma_search_time = 0
        
        # Check if vector search is enabled
        if config.enable_vector_search:
            try:
                chroma_start = timezone.now()
                knowledge_service = PublicKnowledgeService.get_instance()
                
                if knowledge_service.is_ready:
                    context_results = knowledge_service.search_knowledge(
                        query=message, 
                        limit=context_limit, 
                        conversation_context=conversation_context
                    )
                    chroma_end = timezone.now()
                    chroma_search_time = int((chroma_end - chroma_start).total_seconds() * 1000)
                    
                    logger.info(f"🔍 CHROMA: Found {len(context_results)} results in {chroma_search_time}ms")
                else:
                    logger.warning("⚠️ CHROMA: Knowledge service not ready, proceeding without context")
                    
            except Exception as e:
                logger.error(f"❌ CHROMA: Search failed [{request_id}]: {e}")
                # Continue without context rather than failing the request
        else:
            logger.info(f"🔍 VECTOR SEARCH: Disabled by configuration, proceeding without context")
        
        # Generate AI response using existing LLM infrastructure (safely isolated)
        response_data = _generate_llm_response(
            message=message,
            context_results=context_results,
            conversation_context=conversation_context,
            config=config,
            request_id=request_id
        )
        
        # Calculate total response time
        end_time = timezone.now()
        total_time_ms = int((end_time - start_time).total_seconds() * 1000)
        
        # Update request tracking
        if chat_request:
            chat_request.response_generated = True
            chat_request.response_length = len(response_data.get('response', ''))
            chat_request.response_time_ms = total_time_ms
            chat_request.chroma_search_time_ms = chroma_search_time
            chat_request.chroma_results_found = len(context_results)
            chat_request.chroma_context_used = len(context_results) > 0
            chat_request.llm_provider_used = response_data.get('provider', 'unknown')
            chat_request.llm_model_used = response_data.get('model', 'unknown')
            chat_request.llm_tokens_used = response_data.get('tokens_used', 0)
            chat_request.status = 'success' if response_data.get('success') else 'error'
            chat_request.completed_at = end_time
            
            if not response_data.get('success'):
                chat_request.error_type = response_data.get('error_type', 'llm_error')
                chat_request.error_message = response_data.get('error', 'Unknown LLM error')
            
            try:
                chat_request.save()
            except Exception as e:
                logger.error(f"Failed to save request record [{request_id}]: {e}")
        
        # Update IP usage tracking
        _update_ip_usage(client_ip, response_data.get('tokens_used', 0), response_data.get('success', False))
        
        # Format successful response
        if response_data.get('success'):
            response_json = {
                'status': 'success',
                'response': response_data['response'],
                'metadata': {
                    'request_id': request_id,
                    'timestamp': end_time.isoformat(),
                    'response_time_ms': total_time_ms,
                    'provider_used': response_data.get('provider', 'unknown'),
                    'model_used': response_data.get('model', 'unknown'),
                    'context_sources': len(context_results),
                    'vector_search_enabled': config.enable_vector_search,
                    'vector_search_used': config.enable_vector_search and len(context_results) > 0,
                    'chromadb_search_time_ms': chroma_search_time,
                    'tokens_used': response_data.get('tokens_used', 0)
                }
            }
            
            # Add sources if context was used
            if context_results:
                response_json['sources'] = _format_sources(context_results)
                
            logger.info(f"✅ SUCCESS: Request [{request_id}] completed in {total_time_ms}ms")
            response = JsonResponse(response_json)
            _add_cors_headers(response, request)
            return response
        
        else:
            # LLM error response
            logger.error(f"❌ LLM ERROR: Request [{request_id}] failed: {response_data.get('error')}")
            response = JsonResponse({
                'status': 'error',
                'error': 'Unable to generate response. Please try again.',
                'request_id': request_id,
                'metadata': {
                    'timestamp': end_time.isoformat(),
                    'response_time_ms': total_time_ms
                }
            }, status=500)
            _add_cors_headers(response, request)
            return response
            
    except Exception as e:
        # Handle unexpected errors
        error_time = timezone.now()
        total_time_ms = int((error_time - start_time).total_seconds() * 1000)
        
        logger.error(f"❌ UNEXPECTED ERROR: Request [{request_id}] failed: {str(e)}")
        
        # Update request tracking if possible
        if chat_request:
            chat_request.status = 'error'
            chat_request.error_type = 'unexpected_error'
            chat_request.error_message = str(e)[:200]
            chat_request.completed_at = error_time
            chat_request.response_time_ms = total_time_ms
            try:
                chat_request.save()
            except:
                pass
        
        response = JsonResponse({
            'status': 'error',
            'error': 'An unexpected error occurred. Please try again.',
            'request_id': request_id,
            'metadata': {
                'timestamp': error_time.isoformat(),
                'response_time_ms': total_time_ms
            }
        }, status=500)
        _add_cors_headers(response, request)
        return response


def _generate_llm_response(message: str, context_results: List[Dict], conversation_context: List[Dict], config: ChatbotConfiguration, request_id: str) -> Dict[str, Any]:
    """
    Generate LLM response using existing infrastructure (safely isolated)
    
    Args:
        message: User's latest message
        context_results: ChromaDB search results (top 10)
        conversation_context: Full conversation history
        config: Chatbot configuration
        request_id: Request tracking ID
        
    Returns:
        Dict with response data and metadata
    """
    try:
        # Build ChromaDB context from top 10 results
        chromadb_content = ""
        if context_results:
            content_sections = []
            for i, result in enumerate(context_results[:10]):  # Use all top 10 results
                title = result.get('title', f'Knowledge Entry {i+1}')
                content = result.get('content', '')
                similarity = result.get('similarity_score', 0)
                content_sections.append(f"[{i+1}] {title} (Score: {similarity:.3f})\n{content}\n")
            
            chromadb_content = "\n".join(content_sections)
        
        # Build conversation history for prompt
        conversation_history = ""
        if conversation_context and len(conversation_context) > 0:
            for msg in conversation_context:
                role = msg.get('role', '').capitalize()
                content = msg.get('content', '')
                if role and content:
                    conversation_history += f"{role}: {content}\n"
        
        # Create the new structured format prompt
        if chromadb_content:
            enhanced_prompt = f"""System: {config.system_prompt}

Knowledge Base: {chromadb_content}

{conversation_history}User: {message}

Please provide a helpful response based on the available information and conversation context."""
        else:
            # Fallback when no ChromaDB results
            enhanced_prompt = f"""System: {config.system_prompt}

{conversation_history}User: {message}

Please provide a helpful response."""
        
        # Use existing LLM infrastructure through isolated service
        # Note: Using minimal system prompt since the full prompt is in the structured format
        llm_service = PublicLLMService()
        result = llm_service.generate_response(
            prompt=enhanced_prompt,
            provider=config.default_llm_provider,
            model=config.default_model,
            max_tokens=config.max_response_tokens,
            system_prompt="You are a helpful assistant.",  # Minimal system prompt since full prompt is in structured format
            request_id=request_id
        )
        
        return result
        
    except Exception as e:
        logger.error(f"❌ LLM Generation failed [{request_id}]: {e}")
        return {
            'success': False,
            'error': str(e),
            'error_type': 'llm_generation_error',
            'response': 'I apologize, but I encountered an error while generating a response. Please try again.',
            'provider': 'error',
            'model': 'none',
            'tokens_used': 0
        }


def _format_sources(context_results: List[Dict]) -> List[Dict]:
    """Format source information for API response"""
    sources = []
    for result in context_results[:3]:  # Show top 3 sources
        metadata = result.get('metadata', {})
        sources.append({
            'title': metadata.get('title', 'Knowledge Entry'),
            'source': metadata.get('source', 'Public Knowledge Base'),
            'category': metadata.get('category', 'General'),
            'relevance_score': result.get('similarity_score', 0),
            'excerpt': result.get('content', '')[:150] + '...' if len(result.get('content', '')) > 150 else result.get('content', '')
        })
    return sources


def _update_ip_usage(ip_address: str, tokens_used: int, success: bool):
    """Update IP usage tracking (isolated from main system)"""
    try:
        usage_limit, created = IPUsageLimit.objects.get_or_create(
            ip_address=ip_address,
            defaults={
                'daily_request_count': 0,
                'daily_token_usage': 0,
                'total_requests': 0,
                'successful_requests': 0
            }
        )
        
        usage_limit.increment_usage(tokens_used, success)
        
    except Exception as e:
        logger.error(f"Failed to update IP usage for {ip_address}: {e}")


def _update_ip_security_violation(ip_address: str):
    """Track security violations per IP"""
    try:
        usage_limit, created = IPUsageLimit.objects.get_or_create(
            ip_address=ip_address,
            defaults={'security_violations': 0}
        )
        
        usage_limit.security_violations += 1
        usage_limit.last_seen = timezone.now()
        
        # Auto-block after 5 security violations
        if usage_limit.security_violations >= 5:
            usage_limit.is_blocked = True
            usage_limit.blocked_until = timezone.now() + timedelta(hours=24)
            usage_limit.block_reason = 'Multiple security violations'
        
        usage_limit.save()
        
    except Exception as e:
        logger.error(f"Failed to update security violations for {ip_address}: {e}")


@require_http_methods(["GET", "OPTIONS"])
def health_check(request):
    """
    Health check endpoint for monitoring
    GET /api/public-chatbot/health/
    """
    # Handle CORS preflight
    if request.method == 'OPTIONS':
        response = JsonResponse({'status': 'ok'})
        _add_cors_headers(response, request)
        return response
    
    try:
        # Check ChromaDB service
        knowledge_service = PublicKnowledgeService.get_instance()
        chroma_health = knowledge_service.health_check()
        
        # Check configuration
        config = ChatbotConfiguration.get_config()
        
        # Check recent performance
        recent_requests = PublicChatRequest.objects.filter(
            created_at__gte=timezone.now() - timedelta(minutes=5)
        ).count()
        
        # System is healthy if enabled and either vector search is disabled OR ChromaDB is healthy
        overall_healthy = (
            config.is_enabled and 
            (not config.enable_vector_search or chroma_health['status'] == 'healthy')
        )
        
        health_data = {
            'status': 'healthy' if overall_healthy else 'unhealthy',
            'timestamp': timezone.now().isoformat(),
            'components': {
                'chromadb': chroma_health,
                'configuration': {
                    'enabled': config.is_enabled,
                    'maintenance_mode': config.maintenance_mode,
                    'vector_search_enabled': config.enable_vector_search,
                    'daily_limit': config.daily_requests_per_ip,
                    'hourly_limit': config.hourly_requests_per_ip
                },
                'performance': {
                    'requests_last_5min': recent_requests,
                }
            }
        }
        
        status_code = 200 if health_data['status'] == 'healthy' else 503
        response = JsonResponse(health_data, status=status_code)
        _add_cors_headers(response, request)
        return response
        
    except Exception as e:
        response = JsonResponse({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }, status=503)
        _add_cors_headers(response, request)
        return response


@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
@never_cache
@_rate_limit_decorator()
def public_chat_stream_api(request):
    """
    Public Chatbot Streaming API Endpoint
    
    POST /api/public-chatbot/stream/
    
    Returns real-time streaming responses using Server-Sent Events (SSE)
    Currently supports OpenAI streaming only
    """
    # Handle CORS preflight
    if request.method == 'OPTIONS':
        response = JsonResponse({'status': 'ok'})
        _add_cors_headers(response, request)
        return response
    
    # Generate unique request ID for tracking
    client_ip = _get_client_ip(request)
    timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
    request_id = f"stream_{timestamp}_{client_ip.replace('.', '')[-4:]}_{hash(request.body) % 10000:04d}"
    
    start_time = timezone.now()
    
    try:
        # Check if chatbot is enabled
        config = ChatbotConfiguration.get_config()
        if not config.is_enabled or config.maintenance_mode:
            response = JsonResponse({
                'status': 'error',
                'error': 'Service temporarily unavailable' if config.maintenance_mode else 'Service disabled',
                'request_id': request_id
            }, status=503)
            _add_cors_headers(response, request)
            return response
        
        # Parse request body
        try:
            data = json.loads(request.body) if request.body else {}
        except json.JSONDecodeError:
            response = JsonResponse({
                'status': 'error',
                'error': 'Invalid JSON format',
                'request_id': request_id
            }, status=400)
            _add_cors_headers(response, request)
            return response
        
        # Extract and validate parameters
        message = data.get('message', '').strip()
        conversation_context = data.get('conversation', [])
        context_limit = min(data.get('context_limit', config.max_search_results), config.max_search_results)
        
        if not message:
            response = JsonResponse({
                'status': 'error',
                'error': 'Message is required',
                'request_id': request_id
            }, status=400)
            _add_cors_headers(response, request)
            return response
        
        # Security validation
        security_result = ChatbotSecurityService.validate_input(message, client_ip)
        if not security_result['valid']:
            logger.warning(f"🚨 SECURITY: Invalid input from {client_ip}: {security_result['reason']}")
            response = JsonResponse({
                'status': 'error',
                'error': security_result['error'],
                'request_id': request_id
            }, status=400)
            _add_cors_headers(response, request)
            return response
        
        # Check IP-based rate limiting
        if ChatbotSecurityService.check_rate_limit_exceeded(client_ip):
            logger.warning(f"🚨 RATE LIMIT: IP {client_ip} exceeded limits")
            response = JsonResponse({
                'status': 'error',
                'error': 'Rate limit exceeded. Please try again later.',
                'retry_after': 3600,
                'request_id': request_id
            }, status=429)
            _add_cors_headers(response, request)
            return response
        
        # Only allow streaming for OpenAI provider
        if config.default_llm_provider != 'openai':
            response = JsonResponse({
                'status': 'error',
                'error': 'Streaming is currently only supported with OpenAI provider',
                'request_id': request_id
            }, status=400)
            _add_cors_headers(response, request)
            return response
        
        logger.info(f"📨 STREAM API: Processing request [{request_id}] from {client_ip}: '{message[:50]}...'")
        
        # Search ChromaDB for context (same as regular endpoint)
        context_results = []
        if config.enable_vector_search:
            try:
                knowledge_service = PublicKnowledgeService.get_instance()
                if knowledge_service.is_ready:
                    context_results = knowledge_service.search_knowledge(
                        query=message, 
                        limit=context_limit, 
                        conversation_context=conversation_context
                    )
            except Exception as e:
                logger.error(f"❌ CHROMA: Search failed [{request_id}]: {e}")
        
        # Generate streaming response
        response_data = _generate_streaming_llm_response(
            message=message,
            context_results=context_results,
            conversation_context=conversation_context,
            config=config,
            request_id=request_id
        )
        
        if response_data.get('streaming'):
            # Get origin for CORS
            origin = request.META.get('HTTP_ORIGIN')
            allowed_origins = [
                'https://oxfordcompetencycenters.github.io',
                'https://aicc.uksouth.cloudapp.azure.com',
                'http://localhost:3000',
                'http://localhost:5173',
                'http://localhost:8080',
                'http://127.0.0.1:3000',
                'http://127.0.0.1:5173',
                'http://127.0.0.1:8080',
            ]
            
            cors_origin = origin if origin in allowed_origins else '*'
            
            # Return streaming response with proper SSE headers
            return StreamingHttpResponse(
                response_data['generator'],
                content_type='text/event-stream; charset=utf-8',
                headers={
                    'Cache-Control': 'no-cache',
                    'X-Accel-Buffering': 'no',  # Disable nginx buffering
                    'Access-Control-Allow-Origin': cors_origin,
                    'Access-Control-Allow-Methods': 'POST, OPTIONS',
                    'Access-Control-Allow-Headers': 'Origin, Content-Type, Accept, Authorization, X-Requested-With, Cache-Control',
                    'Access-Control-Allow-Credentials': 'true',
                }
            )
        else:
            # Fallback to regular response if streaming failed
            response = JsonResponse({
                'status': 'error',
                'error': response_data.get('error', 'Streaming failed'),
                'request_id': request_id
            }, status=500)
            _add_cors_headers(response, request)
            return response
            
    except Exception as e:
        logger.error(f"❌ STREAM ERROR: Request [{request_id}] failed: {str(e)}")
        import traceback
        logger.error(f"❌ STREAM ERROR: Traceback [{request_id}]: {traceback.format_exc()}")
        
        # Return JSON error with CORS headers
        response = JsonResponse({
            'status': 'error',
            'error': 'An unexpected error occurred',
            'request_id': request_id,
            'details': str(e)
        }, status=500)
        
        # Add CORS headers to error response
        _add_cors_headers(response, request)
        return response


def _generate_streaming_llm_response(message: str, context_results: list, conversation_context: list, config, request_id: str) -> Dict[str, Any]:
    """Generate streaming LLM response"""
    try:
        logger.info(f"🌊 STREAM: Starting streaming response generation [{request_id}]")
        
        # Build context and prompt (same logic as regular endpoint)
        chromadb_content = ""
        if context_results:
            content_sections = []
            for i, result in enumerate(context_results[:10]):
                title = result.get('title', f'Knowledge Entry {i+1}')
                content = result.get('content', '')
                similarity = result.get('similarity_score', 0)
                content_sections.append(f"[{i+1}] {title} (Score: {similarity:.3f})\n{content}\n")
            chromadb_content = "\n".join(content_sections)
        
        # Build conversation history
        conversation_history = ""
        if conversation_context:
            for msg in conversation_context:
                role = msg.get('role', '').capitalize()
                content = msg.get('content', '')
                if role and content:
                    conversation_history += f"{role}: {content}\n"
        
        # Validate config and system prompt
        if not config or not hasattr(config, 'system_prompt'):
            logger.error(f"❌ STREAM: Config or system_prompt missing [{request_id}]")
            return {
                'success': False,
                'streaming': False,
                'error': 'Configuration error: system_prompt not found'
            }
        
        # Create enhanced prompt with structured format
        if chromadb_content:
            enhanced_prompt = f"""System: {config.system_prompt}

Knowledge Base: {chromadb_content}

{conversation_history}User: {message}

Please provide a helpful response based on the available information and conversation context."""
        else:
            enhanced_prompt = f"""System: {config.system_prompt}

{conversation_history}User: {message}

Please provide a helpful response."""
        
        logger.info(f"🌊 STREAM: Enhanced prompt created, length: {len(enhanced_prompt)} [{request_id}]")
        
        # Use LLM service with streaming enabled
        # Note: Using minimal system prompt since the full prompt is in the structured format
        llm_service = PublicLLMService()
        
        logger.info(f"🌊 STREAM: Calling LLM service with provider: {config.default_llm_provider} [{request_id}]")
        
        result = llm_service.generate_response(
            prompt=enhanced_prompt,
            provider=config.default_llm_provider,
            model=config.default_model,
            max_tokens=config.max_response_tokens,
            system_prompt="You are a helpful assistant.",  # Minimal system prompt since full prompt is in structured format
            request_id=request_id,
            stream=True
        )
        
        logger.info(f"🌊 STREAM: LLM service returned: {result.get('success', False)} [{request_id}]")
        return result
        
    except Exception as e:
        logger.error(f"❌ STREAM LLM: Generation failed [{request_id}]: {e}")
        import traceback
        logger.error(f"❌ STREAM LLM: Traceback [{request_id}]: {traceback.format_exc()}")
        return {
            'success': False,
            'streaming': False,
            'error': str(e)
        }