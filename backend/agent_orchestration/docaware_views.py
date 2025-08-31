"""
DocAware API Views
=================

API endpoints for DocAware agent configuration and search methods.
"""

import logging
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404

from users.models import IntelliDocProject
from .docaware import DocAwareSearchMethods, SearchMethod, EnhancedDocAwareAgentService

logger = logging.getLogger(__name__)

class DocAwareConfigViewSet(viewsets.ViewSet):
    """
    ViewSet for DocAware agent configuration
    """
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def search_methods(self, request):
        """
        Get available search methods and their configurations
        """
        try:
            logger.info("📚 DOCAWARE API: search_methods endpoint called")
            print("🔍 DEBUG: DocAware search_methods endpoint hit!")  # Console debug
            print(f"🔍 DEBUG: Request method: {request.method}")
            print(f"🔍 DEBUG: Request path: {request.path}")
            print(f"🔍 DEBUG: Request user: {request.user}")
            
            print("🔍 DEBUG: Importing DocAwareSearchMethods...")
            methods = DocAwareSearchMethods.get_all_methods()
            print(f"🔍 DEBUG: Raw methods from backend: {list(methods.keys())}")
            
            # Format for frontend consumption
            formatted_methods = []
            for method, config in methods.items():
                print(f"🔍 DEBUG: Processing method {method} -> {config.name}")
                formatted_methods.append({
                    'id': method.value,
                    'name': config.name,
                    'description': config.description,
                    'parameters': config.parameters,
                    'default_values': config.default_values,
                    'requires_embedding': config.requires_embedding
                })
            
            logger.info(f"📚 DOCAWARE API: Returning {len(formatted_methods)} search methods")
            print(f"🔍 DEBUG: Returning {len(formatted_methods)} methods: {[m['name'] for m in formatted_methods]}")
            print(f"🔍 DEBUG: First method details: {formatted_methods[0] if formatted_methods else 'None'}")
            
            response_data = {
                'methods': formatted_methods,
                'count': len(formatted_methods)
            }
            print(f"🔍 DEBUG: Final response data: {response_data}")
            
            return Response(response_data)
            
        except Exception as e:
            logger.error(f"❌ DOCAWARE API: Failed to get search methods: {e}")
            print(f"🔍 DEBUG ERROR: {e}")
            return Response(
                {'error': 'Failed to retrieve search methods'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def validate_parameters(self, request):
        """
        Validate search method parameters
        """
        try:
            method_id = request.data.get('method')
            parameters = request.data.get('parameters', {})
            
            if not method_id:
                return Response(
                    {'error': 'Search method is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Validate method exists
            try:
                search_method = SearchMethod(method_id)
            except ValueError:
                return Response(
                    {'error': f'Invalid search method: {method_id}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Validate parameters
            validated_params = DocAwareSearchMethods.validate_parameters(
                search_method, parameters
            )
            
            return Response({
                'valid': True,
                'validated_parameters': validated_params,
                'method': method_id
            })
            
        except Exception as e:
            logger.error(f"❌ DOCAWARE API: Parameter validation failed: {e}")
            return Response(
                {'error': f'Parameter validation failed: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['post'])
    def test_search(self, request):
        """
        Test search functionality with given parameters
        """
        try:
            logger.info("📚 DOCAWARE API: test_search endpoint called")
            print("🔍 DEBUG: DocAware test_search endpoint hit!")  # Console debug
            print(f"🔍 DEBUG: Request method: {request.method}")
            print(f"🔍 DEBUG: Request path: {request.path}")
            print(f"🔍 DEBUG: Request user: {request.user}")
            print(f"🔍 DEBUG: Request data: {request.data}")
            
            project_id = request.data.get('project_id')
            method_id = request.data.get('method')
            parameters = request.data.get('parameters', {})
            query = request.data.get('query')  # REMOVED HARDCODED FALLBACK
            content_filter = request.data.get('content_filter')  # Extract content filter
            
            print(f"🔍 DEBUG: Extracted - project_id: {project_id}, method: {method_id}")
            print(f"🔍 DEBUG: Extracted - query: {query}, parameters: {parameters}")
            print(f"🔍 DEBUG: Extracted - content_filter: {content_filter}")
            
            # CRITICAL: Require actual query input
            if not query or query.strip() == "":
                print("🔍 DEBUG ERROR: Empty query provided")
                return Response(
                    {'error': 'Query is required and cannot be empty. This endpoint no longer accepts hardcoded test queries.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Reject generic test queries to force real input
            rejected_queries = [
                'test query', 
                'test query for document search',
                'sample query',
                'example query',
                'test'
            ]
            
            if query.lower().strip() in rejected_queries:
                print(f"🔍 DEBUG ERROR: Rejected generic test query: {query}")
                return Response(
                    {
                        'error': f'Generic test query "{query}" not allowed. Please provide a meaningful query from agent execution.',
                        'suggestion': 'Use queries like: "quarterly sales analysis", "project risk assessment", "customer feedback insights"'
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            logger.info(f"🔍 DOCAWARE: Processing real query: '{query[:100]}...'")
            print(f"🔍 DEBUG: Validated real query: {query[:50]}...")
            
            if not project_id:
                print("🔍 DEBUG ERROR: Missing project_id")
                return Response(
                    {'error': 'Project ID is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if not method_id:
                print("🔍 DEBUG ERROR: Missing method_id")
                return Response(
                    {'error': 'Search method is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            print(f"🔍 DEBUG: Looking up project {project_id}...")
            # Verify project access
            project = get_object_or_404(IntelliDocProject, project_id=project_id)
            print(f"🔍 DEBUG: Found project: {project.name} (owner: {project.created_by})")
            
            if project.created_by != request.user:
                print(f"🔍 DEBUG ERROR: Access denied - project owner: {project.created_by}, request user: {request.user}")
                return Response(
                    {'error': 'You do not have access to this project'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            print(f"🔍 DEBUG: Validating search method {method_id}...")
            # Validate method
            try:
                search_method = SearchMethod(method_id)
                print(f"🔍 DEBUG: Valid search method: {search_method}")
            except ValueError as ve:
                print(f"🔍 DEBUG ERROR: Invalid search method {method_id}: {ve}")
                return Response(
                    {'error': f'Invalid search method: {method_id}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            print(f"🔍 DEBUG: Initializing DocAware service for project {project_id}...")
            # Initialize DocAware service
            try:
                docaware_service = EnhancedDocAwareAgentService(project_id)
                print(f"🔍 DEBUG: DocAware service initialized successfully")
            except Exception as init_error:
                print(f"🔍 DEBUG ERROR: Failed to initialize DocAware service: {init_error}")
                raise init_error
            
            print(f"🔍 DEBUG: Performing search with method {search_method}, query: '{query}'")
            print(f"🔍 DEBUG: Search parameters: {parameters}")
            
            # Perform test search
            try:
                search_results = docaware_service.search_documents(
                    query=query,
                    search_method=search_method,
                    method_parameters=parameters,
                    content_filter=content_filter
                )
                print(f"🔍 DEBUG: Search completed! Found {len(search_results)} results")
            except Exception as search_error:
                print(f"🔍 DEBUG ERROR: Search failed: {search_error}")
                import traceback
                print(f"🔍 DEBUG ERROR: Search traceback: {traceback.format_exc()}")
                raise search_error
            
            # Format results for response
            formatted_results = []
            for i, result in enumerate(search_results[:3]):  # Limit to top 3 for testing
                print(f"🔍 DEBUG: Processing result {i+1}: {type(result)}")
                try:
                    formatted_results.append({
                        'content_preview': result['content'][:200] + "..." if len(result['content']) > 200 else result['content'],
                        'score': result['metadata'].get('score', 0),
                        'source': result['metadata'].get('source', 'Unknown'),
                        'page': result['metadata'].get('page'),
                        'search_method': result['metadata'].get('search_method', method_id)
                    })
                except Exception as format_error:
                    print(f"🔍 DEBUG ERROR: Failed to format result {i+1}: {format_error}")
                    print(f"🔍 DEBUG: Raw result data: {result}")
            
            response_data = {
                'success': True,
                'query': query,
                'method': method_id,
                'results_count': len(search_results),
                'sample_results': formatted_results,
                'parameters_used': parameters,
                'note': 'Results from real query execution (hardcoded queries disabled)'
            }
            
            print(f"🔍 DEBUG: Final response: success={response_data['success']}, count={response_data['results_count']}")
            logger.info(f"📚 DOCAWARE API: Test search completed successfully - {len(search_results)} results")
            
            return Response(response_data)
            
        except Exception as e:
            logger.error(f"❌ DOCAWARE API: Test search failed: {e}")
            return Response(
                {'error': f'Search test failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def collections(self, request):
        """
        Get available collections for a project
        """
        try:
            project_id = request.query_params.get('project_id')
            
            if not project_id:
                return Response(
                    {'error': 'Project ID is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Verify project access
            project = get_object_or_404(IntelliDocProject, project_id=project_id)
            if project.created_by != request.user:
                return Response(
                    {'error': 'You do not have access to this project'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Initialize DocAware service
            docaware_service = EnhancedDocAwareAgentService(project_id)
            
            # Get available collections
            collections = docaware_service.get_available_collections()
            
            return Response({
                'project_id': project_id,
                'collections': collections,
                'count': len(collections)
            })
            
        except Exception as e:
            logger.error(f"❌ DOCAWARE API: Failed to get collections: {e}")
            return Response(
                {'error': 'Failed to retrieve collections'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def hierarchical_paths(self, request):
        """
        Get hierarchical paths for content filtering
        Returns folder tree structure with files and folders
        """
        try:
            project_id = request.query_params.get('project_id')
            
            print(f"🔍 DEBUG HIERARCHICAL PATHS: Called with project_id={project_id}")
            print(f"🔍 DEBUG HIERARCHICAL PATHS: Request method: {request.method}")
            print(f"🔍 DEBUG HIERARCHICAL PATHS: Query params: {dict(request.query_params)}")
            
            if not project_id:
                print("❌ DEBUG HIERARCHICAL PATHS: No project_id provided")
                return Response(
                    {'error': 'Project ID is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            logger.info(f"📚 DOCAWARE API: Getting hierarchical paths for project {project_id}")
            
            # Verify project access
            try:
                project = get_object_or_404(IntelliDocProject, project_id=project_id)
                print(f"✅ DEBUG HIERARCHICAL PATHS: Found project: {project.name} (owner: {project.created_by})")
            except Exception as proj_error:
                print(f"❌ DEBUG HIERARCHICAL PATHS: Project lookup failed: {proj_error}")
                raise proj_error
            
            if project.created_by != request.user:
                print(f"❌ DEBUG HIERARCHICAL PATHS: Access denied - project owner: {project.created_by}, request user: {request.user}")
                return Response(
                    {'error': 'You do not have access to this project'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Initialize DocAware service to get collection data
            try:
                print(f"🔧 DEBUG HIERARCHICAL PATHS: Initializing DocAware service for project {project_id}")
                docaware_service = EnhancedDocAwareAgentService(project_id)
                print(f"✅ DEBUG HIERARCHICAL PATHS: DocAware service initialized")
            except Exception as init_error:
                print(f"❌ DEBUG HIERARCHICAL PATHS: DocAware service initialization failed: {init_error}")
                raise init_error
            
            # Get hierarchical paths from the vector database
            try:
                print(f"📊 DEBUG HIERARCHICAL PATHS: Calling get_hierarchical_paths()")
                hierarchical_data = docaware_service.get_hierarchical_paths()
                print(f"📊 DEBUG HIERARCHICAL PATHS: Raw data from service: {len(hierarchical_data)} items")
                print(f"📊 DEBUG HIERARCHICAL PATHS: First few items: {hierarchical_data[:2] if hierarchical_data else 'None'}")
            except Exception as data_error:
                print(f"❌ DEBUG HIERARCHICAL PATHS: get_hierarchical_paths() failed: {data_error}")
                import traceback
                print(f"❌ DEBUG HIERARCHICAL PATHS: Traceback: {traceback.format_exc()}")
                raise data_error
            
            logger.info(f"📚 DOCAWARE API: Found {len(hierarchical_data)} hierarchical entries")
            
            response_data = {
                'project_id': project_id,
                'hierarchical_paths': hierarchical_data,
                'count': len(hierarchical_data)
            }
            
            print(f"✅ DEBUG HIERARCHICAL PATHS: Returning response with {len(hierarchical_data)} items")
            print(f"✅ DEBUG HIERARCHICAL PATHS: Response keys: {list(response_data.keys())}")
            
            return Response(response_data)
            
        except Exception as e:
            print(f"❌ DEBUG HIERARCHICAL PATHS: Outer exception: {e}")
            import traceback
            print(f"❌ DEBUG HIERARCHICAL PATHS: Full traceback: {traceback.format_exc()}")
            logger.error(f"❌ DOCAWARE API: Failed to get hierarchical paths: {e}")
            return Response(
                {'error': f'Failed to retrieve hierarchical paths: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
