# Consolidated Vector Search API - Phase 2 Consolidation
# backend/vector_search/consolidated_api_views.py

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils import timezone
from users.models import IntelliDocProject
from .services_enhanced import EnhancedVectorSearchManager
from .unified_services_fixed import UnifiedVectorSearchManager, fix_existing_documents
from .detailed_logger import DocumentProcessingTracker, doc_logger
import logging
import threading
import time

logger = logging.getLogger(__name__)

# Global processing threads
PROCESSING_THREADS = {}

def run_processing_in_background(project_id: str, processing_mode: str = 'enhanced'):
    """Run enhanced document processing in background thread"""
    try:
        # Create detailed logging for this processing session
        doc_logger.info(f"🚀 CONSOLIDATED PROCESSING STARTED | Project: {project_id} | Mode: {processing_mode}")
        
        logger.info(f"Starting consolidated processing for project {project_id}")
        
        # Use enhanced UnifiedVectorSearchManager
        result = UnifiedVectorSearchManager.process_project_documents(project_id, processing_mode=processing_mode)
        
        doc_logger.info(f"✅ CONSOLIDATED PROCESSING COMPLETED | Project: {project_id} | Result: {result.get('status', 'unknown')}")
        logger.info(f"Consolidated processing completed for project {project_id}: {result.get('status', 'unknown')}")
        
        # Clean up thread reference
        if project_id in PROCESSING_THREADS:
            del PROCESSING_THREADS[project_id]
            
    except Exception as e:
        doc_logger.error(f"❌ CONSOLIDATED PROCESSING FAILED | Project: {project_id} | Error: {str(e)}")
        logger.error(f"Consolidated processing failed for project {project_id}: {e}")
        # Clean up thread reference
        if project_id in PROCESSING_THREADS:
            del PROCESSING_THREADS[project_id]

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def process_unified_consolidated(request, project_id):
    """
    CONSOLIDATED PROCESSING ENDPOINT - Phase 2
    
    Combines all processing capabilities into a single, intelligent endpoint
    that automatically selects the best processing mode based on project configuration
    """
    try:
        # Verify project exists and user has access
        project = get_object_or_404(IntelliDocProject, project_id=project_id)
        
        logger.info(f"🚀 CONSOLIDATED: Processing request for project {project.name} (ID: {project_id})")
        
        # Get project's processing capabilities from cloned template configuration
        processing_capabilities = project.processing_capabilities or {}
        
        # Automatically determine optimal processing mode based on project configuration
        processing_mode = 'enhanced'  # Default to enhanced mode
        
        # Check project template type and capabilities
        if project.template_type == 'aicc-intellidoc' and processing_capabilities.get('supports_hierarchical_processing'):
            processing_mode = 'enhanced_hierarchical'
        elif processing_capabilities.get('supports_enhanced_processing'):
            processing_mode = 'enhanced'
        else:
            processing_mode = 'basic'
        
        # Allow override from request
        requested_mode = request.data.get('processing_mode')
        if requested_mode:
            processing_mode = requested_mode
        
        logger.info(f"🎯 CONSOLIDATED: Selected processing mode: {processing_mode}")
        logger.info(f"📊 CONSOLIDATED: Project capabilities: {list(processing_capabilities.keys())}")
        
        # Check document readiness
        ready_documents = project.documents.filter(upload_status='ready')
        if ready_documents.count() == 0:
            logger.warning(f"⚠️ CONSOLIDATED: No documents ready for processing in project {project_id}")
            return Response({
                'status': 'no_documents',
                'message': 'No documents ready for processing',
                'debug_info': {
                    'total_documents': project.documents.count(),
                    'ready_documents': ready_documents.count(),
                    'project_id': str(project.project_id),
                    'project_name': project.name
                }
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Use the enhanced UnifiedVectorSearchManager for processing
        result = UnifiedVectorSearchManager.process_project_documents(
            project_id=str(project.project_id),
            processing_mode=processing_mode
        )
        
        # Enhanced result metadata
        enhanced_result = {
            **result,
            'project_id': project_id,
            'project_name': project.name,
            'template_type': project.template_type,
            'template_name': project.template_name,
            'processing_mode': processing_mode,
            'processing_capabilities': processing_capabilities,
            'consolidated_features': {
                'intelligent_mode_selection': True,
                'template_aware_processing': True,
                'enhanced_hierarchical_support': processing_mode == 'enhanced_hierarchical',
                'content_preservation': True,
                'category_filtering': processing_capabilities.get('category_filtered_search', False),
                'advanced_search': processing_capabilities.get('multi_filter_search', False)
            },
            'user_email': request.user.email,
            'processed_at': timezone.now().isoformat(),
            'ready_documents': ready_documents.count(),
            'total_documents': project.documents.count()
        }
        
        # Return response with appropriate status
        status_code = status.HTTP_200_OK if result.get('status') == 'completed' else status.HTTP_500_INTERNAL_SERVER_ERROR
        
        return Response(enhanced_result, status=status_code)
        
    except Exception as e:
        logger.error(f"❌ CONSOLIDATED: Processing failed for project {project_id}: {e}")
        return Response({
            'status': 'error',
            'message': str(e),
            'project_id': project_id,
            'processing_mode': 'consolidated',
            'error_type': type(e).__name__
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def search_unified_consolidated(request, project_id):
    """
    CONSOLIDATED SEARCH ENDPOINT - Phase 2
    
    Combines all search capabilities into a single, intelligent endpoint
    """
    try:
        # Verify project exists and user has access
        project = get_object_or_404(IntelliDocProject, project_id=project_id)
        
        # Get search parameters
        query = request.data.get('query', '').strip()
        limit = request.data.get('limit', 5)
        filters = request.data.get('filters', {})
        search_type = request.data.get('search_type', 'basic')
        
        logger.info(f"🔍 CONSOLIDATED: Search request for project {project.name}: '{query}'")
        
        # Get project's search capabilities
        processing_capabilities = project.processing_capabilities or {}
        
        # Automatically determine optimal search mode
        if processing_capabilities.get('hierarchical_search'):
            search_mode = 'hierarchical'
        elif processing_capabilities.get('category_filtered_search'):
            search_mode = 'category_filtered'
        else:
            search_mode = 'basic'
        
        # Allow override from request
        if search_type != 'basic':
            search_mode = search_type
        
        logger.info(f"🎯 CONSOLIDATED: Selected search mode: {search_mode}")
        
        # Use the enhanced search manager
        try:
            # Try enhanced hierarchical search first
            from .enhanced_hierarchical_services import EnhancedHierarchicalSearchAPI
            search_api = EnhancedHierarchicalSearchAPI()
            
            results = search_api.search_documents(
                project_id=str(project.project_id),
                query=query,
                limit=limit,
                filters=filters,
                search_level='chunk',
                group_by_document=True
            )
            
            search_results = {
                'results': results,
                'search_mode': search_mode,
                'query': query,
                'total_results': len(results),
                'project_id': project_id,
                'project_name': project.name,
                'capabilities': processing_capabilities,
                'search_features': {
                    'hierarchical_search': search_mode == 'hierarchical',
                    'category_filtering': processing_capabilities.get('category_filtered_search', False),
                    'content_reconstruction': processing_capabilities.get('full_document_rebuild', False),
                    'advanced_filtering': len(filters) > 0
                }
            }
            
        except Exception as search_error:
            logger.warning(f"⚠️ CONSOLIDATED: Enhanced search failed, falling back to basic: {search_error}")
            
            # Fallback to basic search
            search_results = {
                'results': [],
                'search_mode': 'basic_fallback',
                'query': query,
                'total_results': 0,
                'project_id': project_id,
                'project_name': project.name,
                'error': str(search_error),
                'message': 'Enhanced search failed, basic search not yet implemented'
            }
        
        return Response(search_results, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"❌ CONSOLIDATED: Search failed for project {project_id}: {e}")
        return Response({
            'error': str(e),
            'query': query,
            'project_id': project_id,
            'search_mode': 'error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_project_capabilities_consolidated(request, project_id):
    """
    CONSOLIDATED CAPABILITIES ENDPOINT - Phase 2
    
    Returns comprehensive project capabilities for frontend decision making
    """
    try:
        project = get_object_or_404(IntelliDocProject, project_id=project_id)
        
        # Get processing capabilities from cloned template configuration
        processing_capabilities = project.processing_capabilities or {}
        
        # Build comprehensive capabilities response
        capabilities = {
            'project_id': project_id,
            'project_name': project.name,
            'template_type': project.template_type,
            'template_name': project.template_name,
            'processing': {
                'supports_hierarchical_processing': processing_capabilities.get('supports_hierarchical_processing', False),
                'supports_enhanced_processing': processing_capabilities.get('supports_enhanced_processing', True),
                'supports_chunking': processing_capabilities.get('supports_chunking', True),
                'processing_mode': 'enhanced_hierarchical' if processing_capabilities.get('supports_hierarchical_processing') else 'enhanced',
                'max_chunk_size': processing_capabilities.get('max_chunk_size', 35000),
                'content_preservation': 'complete'
            },
            'search': {
                'hierarchical_search': processing_capabilities.get('hierarchical_search', False),
                'category_filtered_search': processing_capabilities.get('category_filtered_search', False),
                'multi_filter_search': processing_capabilities.get('multi_filter_search', False),
                'full_document_rebuild': processing_capabilities.get('full_document_rebuild', False),
                'advanced_search': processing_capabilities.get('multi_filter_search', False)
            },
            'ui': {
                'has_navigation': project.has_navigation,
                'total_pages': project.total_pages,
                'navigation_pages': project.navigation_pages or [],
                'supports_multi_page': project.has_navigation and project.total_pages > 1
            },
            'metadata': {
                'created_at': project.created_at.isoformat(),
                'created_by': project.created_by.email,
                'last_updated': project.updated_at.isoformat() if hasattr(project, 'updated_at') else None,
                'document_count': project.documents.count(),
                'ready_documents': project.documents.filter(upload_status='ready').count()
            }
        }
        
        return Response(capabilities, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"❌ CONSOLIDATED: Failed to get capabilities for project {project_id}: {e}")
        return Response({
            'error': str(e),
            'project_id': project_id,
            'capabilities': {
                'processing': {'supports_enhanced_processing': True},
                'search': {'hierarchical_search': False}
            }
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_vector_status_consolidated(request, project_id):
    """
    CONSOLIDATED STATUS ENDPOINT - Phase 2
    
    Returns comprehensive project status information
    """
    try:
        project = get_object_or_404(IntelliDocProject, project_id=project_id)
        
        # Get status from enhanced manager
        try:
            status_data = EnhancedVectorSearchManager.get_project_processing_status(project_id)
        except Exception as e:
            logger.warning(f"⚠️ CONSOLIDATED: Could not get enhanced status, using basic: {e}")
            status_data = {
                'collection_status': 'UNKNOWN',
                'processing_progress': {'completed': 0},
                'total_documents': project.documents.count(),
                'is_processing': False
            }
        
        # Format comprehensive status response
        vector_count = status_data.get('processing_progress', {}).get('completed', 0)
        total_documents = status_data.get('total_documents', 0)
        ready_documents = project.documents.filter(upload_status='ready').count()
        
        consolidated_status = {
            'project_id': project_id,
            'project_name': project.name,
            'vector_status': {
                'has_vectors': vector_count > 0,
                'vector_count': vector_count,
                'total_documents': total_documents,
                'ready_documents': ready_documents,
                'collection_status': status_data.get('collection_status', 'NOT_CREATED'),
                'processing_status': status_data.get('collection_status', 'ready'),
                'is_processing': status_data.get('is_processing', False)
            },
            'processing_capabilities': project.processing_capabilities or {},
            'template_info': {
                'template_type': project.template_type,
                'template_name': project.template_name,
                'supports_hierarchical': project.processing_capabilities.get('supports_hierarchical_processing', False)
            },
            'last_updated': status_data.get('last_processed_at'),
            'status_timestamp': timezone.now().isoformat()
        }
        
        return Response(consolidated_status, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"❌ CONSOLIDATED: Failed to get status for project {project_id}: {e}")
        return Response({
            'project_id': project_id,
            'vector_status': {
                'has_vectors': False,
                'vector_count': 0,
                'total_documents': 0,
                'ready_documents': 0,
                'collection_status': 'ERROR',
                'processing_status': 'error',
                'is_processing': False
            },
            'error': str(e)
        }, status=status.HTTP_200_OK)  # Return 200 so frontend doesn't break

# Additional consolidated endpoints...
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def start_processing_consolidated(request, project_id):
    """Start processing with consolidated background processing"""
    try:
        project = get_object_or_404(IntelliDocProject, project_id=project_id)
        
        # Check if processing is already running
        if project_id in PROCESSING_THREADS and PROCESSING_THREADS[project_id].is_alive():
            return Response({
                'success': False,
                'error': 'Processing already in progress',
                'message': 'Processing is already running for this project'
            }, status=status.HTTP_409_CONFLICT)
        
        # Determine processing mode based on project capabilities
        processing_capabilities = project.processing_capabilities or {}
        processing_mode = 'enhanced_hierarchical' if processing_capabilities.get('supports_hierarchical_processing') else 'enhanced'
        
        logger.info(f"🚀 CONSOLIDATED: Starting background processing for project {project_id} with mode {processing_mode}")
        
        # Start processing in background thread
        processing_thread = threading.Thread(
            target=run_processing_in_background,
            args=(project_id, processing_mode),
            daemon=True
        )
        processing_thread.start()
        
        # Store thread reference
        PROCESSING_THREADS[project_id] = processing_thread
        
        # Give a small delay to let processing start
        time.sleep(0.5)
        
        return Response({
            'success': True,
            'data': {
                'project_id': project_id,
                'project_name': project.name,
                'status': 'started',
                'processing_mode': processing_mode,
                'message': f"Consolidated processing started in background with {processing_mode} mode"
            },
            'message': 'Consolidated processing started successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"❌ CONSOLIDATED: Error starting processing for project {project_id}: {e}")
        return Response({
            'success': False,
            'error': str(e),
            'message': 'Failed to start consolidated processing'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def stop_processing_consolidated(request, project_id):
    """Stop processing with consolidated cleanup"""
    try:
        project = get_object_or_404(IntelliDocProject, project_id=project_id)
        
        logger.info(f"🛑 CONSOLIDATED: Stopping processing for project {project_id}")
        
        # Stop processing
        result = EnhancedVectorSearchManager.stop_project_processing(project_id)
        
        # Clean up thread reference if exists
        if project_id in PROCESSING_THREADS:
            thread = PROCESSING_THREADS[project_id]
            if thread.is_alive():
                logger.info(f"🔄 CONSOLIDATED: Background thread for project {project_id} will terminate gracefully")
            del PROCESSING_THREADS[project_id]
        
        return Response({
            'success': result.get('success', True),
            'data': {
                **result,
                'project_id': project_id,
                'project_name': project.name,
                'stopped_at': timezone.now().isoformat()
            },
            'message': result.get('message', 'Consolidated processing stopped'),
            'processing_mode': 'consolidated'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"❌ CONSOLIDATED: Error stopping processing for project {project_id}: {e}")
        return Response({
            'success': False,
            'error': str(e),
            'message': 'Failed to stop consolidated processing'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
