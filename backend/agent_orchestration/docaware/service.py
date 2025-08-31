"""
Enhanced DocAware Agent Service
==============================

Main service class that integrates with Django Milvus Search to provide
comprehensive RAG capabilities for document-aware agents.
"""

import logging
import json
from typing import Dict, List, Any, Optional, Union
from django.conf import settings
from users.models import IntelliDocProject
from django_milvus_search import MilvusSearchService
from django_milvus_search.models import SearchRequest, IndexType, MetricType, SearchParams

from .search_methods import DocAwareSearchMethods, SearchMethod, SearchMethodConfig
from .embedding_service import DocAwareEmbeddingService

logger = logging.getLogger('agent_orchestration')

class EnhancedDocAwareAgentService:
    """Enhanced RAG service with multiple search methods using Django Milvus Search"""
    
    def __init__(self, project_id: str):
        """
        Initialize the enhanced DocAware service
        
        Args:
            project_id: ID of the project containing documents
        """
        self.project_id = project_id
        logger.info(f"📚 ENHANCED RAG: Initializing service for project {project_id}")
        
        # Load project
        try:
            self.project = IntelliDocProject.objects.get(project_id=project_id)
            self.collection_name = self.project.generate_collection_name()
            logger.info(f"📚 ENHANCED RAG: Loaded project {self.project.name}, collection: {self.collection_name}")
        except IntelliDocProject.DoesNotExist:
            logger.error(f"📚 ENHANCED RAG: Project {project_id} not found")
            raise ValueError(f"Project {project_id} not found")
        
        # Initialize services
        self.milvus_service = MilvusSearchService()
        self.embedding_service = DocAwareEmbeddingService()
        
        # Cache conversation context
        self.conversation_context = []
    
    def search_documents(
        self, 
        query: str, 
        search_method: SearchMethod = SearchMethod.SEMANTIC_SEARCH,
        method_parameters: Optional[Dict[str, Any]] = None,
        conversation_context: Optional[List[str]] = None,
        content_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search documents using the specified method
        
        Args:
            query: Search query text
            search_method: Method to use for searching
            method_parameters: Parameters specific to the search method
            conversation_context: Recent conversation context for contextual search
            
        Returns:
            List of search results with content and metadata
        """
        logger.info(f"📚 SEARCH: Starting {search_method.value} search for: '{query[:50]}...'")
        
        # Build content filter if specified
        content_filter_expr = self._build_content_filter_expression(content_filter) if content_filter else None
        if content_filter_expr:
            logger.info(f"📚 SEARCH: Applying content filter: {content_filter_expr}")
        elif content_filter:
            logger.warning(f"📚 SEARCH: Content filter '{content_filter}' provided but could not build expression")
        
        # Get method configuration
        method_config = DocAwareSearchMethods.get_method_config(search_method)
        if not method_config:
            raise ValueError(f"Unknown search method: {search_method}")
        
        # Validate and set parameters
        parameters = method_parameters or {}
        validated_params = DocAwareSearchMethods.validate_parameters(search_method, parameters)
        
        # Update conversation context if provided
        if conversation_context:
            self.conversation_context = conversation_context[-5:]  # Keep last 5 turns
        
        # Route to appropriate search implementation with content filter
        if search_method == SearchMethod.SEMANTIC_SEARCH:
            return self._semantic_search(query, validated_params, content_filter_expr)
        elif search_method == SearchMethod.HYBRID_SEARCH:
            return self._hybrid_search(query, validated_params, content_filter_expr)
        elif search_method == SearchMethod.CONTEXTUAL_SEARCH:
            return self._contextual_search(query, validated_params, content_filter_expr)
        elif search_method == SearchMethod.SIMILARITY_THRESHOLD:
            return self._similarity_threshold_search(query, validated_params, content_filter_expr)
        elif search_method == SearchMethod.MULTI_COLLECTION:
            return self._multi_collection_search(query, validated_params, content_filter_expr)
        elif search_method == SearchMethod.HIERARCHICAL_SEARCH:
            return self._hierarchical_search(query, validated_params, content_filter_expr)
        elif search_method == SearchMethod.KEYWORD_SEARCH:
            return self._keyword_search(query, validated_params, content_filter_expr)
        else:
            raise ValueError(f"Search method {search_method} not implemented")

    
    def _extract_document_fields(self, hit: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract document fields with flexible field name mapping
        
        This method handles cases where documents are stored with different field names
        than expected (e.g., 'text' instead of 'content', 'filename' instead of 'source')
        
        Args:
            hit: Raw search result from Milvus
            
        Returns:
            Standardized document fields
        """
        # Try multiple possible field names for content
        content = (
            hit.get("content") or 
            hit.get("text") or 
            hit.get("document_text") or 
            hit.get("body") or 
            hit.get("chunk_text") or
            hit.get("passage") or
            hit.get("paragraph") or
            ""
        )
        
        # Try multiple possible field names for source/filename
        source = (
            hit.get("source") or
            hit.get("filename") or
            hit.get("file_name") or
            hit.get("document_name") or
            hit.get("title") or
            hit.get("doc_name") or
            hit.get("file") or
            "Unknown"
        )
        
        # Try multiple possible field names for page number
        page = (
            hit.get("page") or
            hit.get("page_number") or
            hit.get("chunk_page") or
            hit.get("page_num") or
            1
        )
        
        # Try multiple possible field names for document ID
        document_id = (
            hit.get("document_id") or
            hit.get("doc_id") or
            hit.get("id") or
            hit.get("_id") or
            ""
        )
        
        # Try multiple possible field names for chunk type
        chunk_type = (
            hit.get("chunk_type") or
            hit.get("type") or
            hit.get("section_type") or
            hit.get("content_type") or
            "text"
        )
        
        # Log field extraction for debugging
        if not content:
            logger.warning(f"📚 FIELD MAPPING: No content found in hit with keys: {list(hit.keys())}")
            # Show first few characters of each field to help debug
            for key, value in hit.items():
                if isinstance(value, str) and len(value) > 10:
                    logger.debug(f"📚 FIELD MAPPING: {key}: {str(value)[:50]}...")
        
        if source == "Unknown":
            logger.debug(f"📚 FIELD MAPPING: No source found in hit with keys: {list(hit.keys())}")
        
        return {
            "content": str(content).strip() if content else "",
            "source": str(source).strip() if source else "Unknown",
            "page": int(page) if isinstance(page, (int, float)) or (isinstance(page, str) and page.isdigit()) else 1,
            "document_id": str(document_id) if document_id else "",
            "chunk_type": str(chunk_type) if chunk_type else "text"
        }
    
    def get_collection_metric_type(self, collection_name: str) -> str:
        """
        Auto-detect the metric type used by a Milvus collection
        
        Args:
            collection_name: Name of the collection to inspect
            
        Returns:
            Metric type string (IP, L2, or COSINE)
        """
        try:
            collection_info = self.milvus_service.get_collection_info(collection_name)
            
            # Look for index information which contains the metric type
            indexes = collection_info.get('indexes', [])
            
            for index in indexes:
                if hasattr(index, 'params') and 'metric_type' in index.params:
                    metric_type = index.params['metric_type']
                    logger.info(f"🔍 METRIC DETECTION: Collection {collection_name} uses {metric_type} metric")
                    return metric_type
            
            # Fallback: based on error logs, collections use IP
            logger.warning(f"⚠️ METRIC DETECTION: Could not detect metric for {collection_name}, defaulting to IP")
            return "IP"  # Based on error logs, collections use IP
            
        except Exception as e:
            logger.error(f"❌ METRIC DETECTION: Failed to detect metric for {collection_name}: {e}")
            return "IP"  # Safe default based on error analysis
    
    def _build_content_filter_expression(self, content_filter: str) -> str:
        """
        Build Milvus filter expression from content filter ID
        
        Args:
            content_filter: Content filter ID (e.g., "folder_Reports/Financial" or "file_doc123")
            
        Returns:
            Milvus filter expression string
        """
        if not content_filter:
            return ""
            
        try:
            logger.info(f"🔍 CONTENT FILTER: Building expression for filter: {content_filter}")
            
            # Parse filter ID to determine type and path/document ID
            if content_filter.startswith('folder_'):
                folder_path = content_filter[7:]  # Remove 'folder_' prefix
                # Escape single quotes in folder path for safety
                escaped_path = folder_path.replace("'", "''")
                # Filter by hierarchical_path starting with the folder path (case-insensitive)
                # Using 'like' operator with wildcard for hierarchical matching
                filter_expr = f"hierarchical_path like '{escaped_path}%'"
                logger.info(f"🔍 CONTENT FILTER: Folder filter - path starts with: {folder_path}")
                
            elif content_filter.startswith('file_'):
                document_id = content_filter[5:]  # Remove 'file_' prefix
                # Escape single quotes in document ID for safety
                escaped_doc_id = document_id.replace("'", "''")
                # Filter by specific document_id (exact match)
                filter_expr = f"document_id == '{escaped_doc_id}'"
                logger.info(f"🔍 CONTENT FILTER: File filter - document_id: {document_id}")
                
            else:
                logger.warning(f"🔍 CONTENT FILTER: Unknown filter format: {content_filter}")
                return ""
            
            logger.info(f"🔍 CONTENT FILTER: Generated expression: {filter_expr}")
            return filter_expr
            
        except Exception as e:
            logger.error(f"❌ CONTENT FILTER: Failed to build filter expression: {e}")
            return ""
    
    def _semantic_search(self, query: str, params: Dict[str, Any], content_filter_expr: str = None) -> List[Dict[str, Any]]:
        """Enhanced semantic search with automatic metric type detection"""
        try:
            # Auto-detect collection metric type
            detected_metric = self.get_collection_metric_type(self.collection_name)
            
            logger.info(f"🔍 SEMANTIC: Starting search with detected metric: {detected_metric}")
            logger.debug(f"🔍 SEMANTIC: Query: '{query[:50]}...', Params: {params}")
            
            # Generate query embedding
            query_vector = self.embedding_service.encode_query(query)
            logger.debug(f"🔍 SEMANTIC: Generated embedding vector of length {len(query_vector)}")
            
            # Create search request with detected metric type and content filter
            search_request = SearchRequest(
                collection_name=self.collection_name,
                query_vectors=[query_vector],
                index_type=IndexType(params["index_type"]),
                metric_type=MetricType(detected_metric),  # Use detected metric
                limit=params["search_limit"],
                filter_expression=content_filter_expr if content_filter_expr else "",
                output_fields=["*"]  # Return all fields
            )
            
            logger.info(f"🔍 SEMANTIC: Search request created - Collection: {self.collection_name}, Metric: {detected_metric}, Limit: {params['search_limit']}")
            
            # Perform search
            search_result = self.milvus_service.search(search_request)
            
            # Filter by relevance threshold and format results
            results = []
            for hit in search_result.hits:
                score = hit.get("score", 0.0)
                if score >= params["relevance_threshold"]:
                    results.append({
                        "content": hit.get("content", ""),
                        "metadata": {
                            "source": hit.get("source", "Unknown"),
                            "page": hit.get("page", 1),
                            "score": score,
                            "chunk_type": hit.get("chunk_type", "text"),
                            "document_id": hit.get("document_id", ""),
                            "collection": self.collection_name,
                            "search_method": "semantic_search",
                                "metric_used": detected_metric,
                                    "vector_dimension": len(query_vector)
                                    }
                                })
                            
            logger.info(f"✅ SEMANTIC: Found {len(results)} results above threshold {params['relevance_threshold']} using {detected_metric} metric")
            return results
            
        except Exception as e:
            logger.error(f"❌ SEMANTIC: Search failed with error: {e}")
            logger.error(f"❌ SEMANTIC: Collection: {self.collection_name}, Attempted metric: {detected_metric if 'detected_metric' in locals() else 'Unknown'}")
            return []
    
    def _hybrid_search(self, query: str, params: Dict[str, Any], content_filter_expr: str = None) -> List[Dict[str, Any]]:
        """Enhanced hybrid search with automatic metric type detection"""
        try:
            # Auto-detect collection metric type
            detected_metric = self.get_collection_metric_type(self.collection_name)
            
            logger.info(f"🔍 HYBRID: Starting search with detected metric: {detected_metric}")
            
            # Generate query embedding
            query_vector = self.embedding_service.encode_query(query)
            
            # Combine existing filter with content filter
            existing_filter = params.get("filter_expression", "")
            if content_filter_expr and existing_filter:
                combined_filter = f"({existing_filter}) && ({content_filter_expr})"
            elif content_filter_expr:
                combined_filter = content_filter_expr
            else:
                combined_filter = existing_filter
            
            # Create search request with detected metric type and combined filter
            search_request = SearchRequest(
                collection_name=self.collection_name,
                query_vectors=[query_vector],
                index_type=IndexType(params["index_type"]),
                metric_type=MetricType(detected_metric),  # Use detected metric
                limit=params["search_limit"],
                filter_expression=combined_filter if combined_filter else "",
                output_fields=["*"]  # Return all fields
            )
            
            # Perform semantic search
            search_result = self.milvus_service.search(search_request)
            
            # Apply keyword weighting
            keyword_weight = params["keyword_weight"]
            results = []
            
            for hit in search_result.hits:
                # Extract fields with flexible field name mapping
                content = (
                    hit.get("content") or 
                    hit.get("text") or 
                    hit.get("document_text") or 
                    hit.get("body") or 
                    hit.get("chunk_text") or
                    ""
                )
                
                source = (
                    hit.get("source") or
                    hit.get("filename") or
                    hit.get("file_name") or
                    hit.get("document_name") or
                    hit.get("title") or
                    "Unknown"
                )
                
                page = (
                    hit.get("page") or
                    hit.get("page_number") or
                    1
                )
                
                # Log for debugging
                if not content:
                    logger.warning(f"📚 HYBRID SEARCH: No content found in document. Available fields: {list(hit.keys())}")
                    # Show sample of each field to help identify the correct one
                    for key, value in hit.items():
                        if isinstance(value, str) and len(value) > 20:
                            logger.info(f"📚 HYBRID SEARCH: Field '{key}' contains: {str(value)[:100]}...")
                
                semantic_score = hit.get("score", 0.0)
                
                # Simple keyword matching score
                content_for_keyword = content.lower() if content else ""
                query_words = query.lower().split()
                keyword_matches = sum(1 for word in query_words if word in content_for_keyword)
                keyword_score = keyword_matches / len(query_words) if query_words else 0
                
                # Combine scores
                final_score = (1 - keyword_weight) * semantic_score + keyword_weight * keyword_score
                
                results.append({
                    "content": content,  # Use extracted content
                    "metadata": {
                        "source": source,  # Use extracted source
                        "page": page,  # Use extracted page
                        "score": final_score,
                        "semantic_score": semantic_score,
                        "keyword_score": keyword_score,
                        "chunk_type": hit.get("chunk_type", "text"),
                        "document_id": hit.get("document_id", ""),
                        "collection": self.collection_name,
                        "search_method": "hybrid_search",
                        "metric_used": detected_metric
                    }
                })
            
            # Sort by final score
            results.sort(key=lambda x: x["metadata"]["score"], reverse=True)
            
            logger.info(f"✅ HYBRID: Found {len(results)} results with hybrid scoring using {detected_metric} metric")
            return results
            
        except Exception as e:
            logger.error(f"❌ HYBRID: Search failed with error: {e}")
            logger.error(f"❌ HYBRID: Collection: {self.collection_name}, Attempted metric: {detected_metric if 'detected_metric' in locals() else 'Unknown'}")
            return []
    
    def _contextual_search(self, query: str, params: Dict[str, Any], content_filter_expr: str = None) -> List[Dict[str, Any]]:
        """Perform contextual search using conversation history"""
        try:
            # Generate contextualized query embedding
            context_window = params["context_window"]
            context_weight = params["context_weight"]
            
            relevant_context = self.conversation_context[-context_window:] if self.conversation_context else []
            
            query_vector = self.embedding_service.encode_with_context(
                query, relevant_context, context_weight
            )
            
            # Auto-detect collection metric type
            detected_metric = self.get_collection_metric_type(self.collection_name)
            
            # Create search request with detected metric and content filter
            search_request = SearchRequest(
                collection_name=self.collection_name,
                query_vectors=[query_vector],
                index_type=IndexType.AUTOINDEX,
                metric_type=MetricType(detected_metric),
                limit=params["search_limit"],
                filter_expression=content_filter_expr if content_filter_expr else "",
                output_fields=["*"]  # Return all fields
            )
            
            # Perform search
            search_result = self.milvus_service.search(search_request)
            
            # Filter and format results
            results = []
            for hit in search_result.hits:
                score = hit.get("score", 0.0)
                if score >= params["relevance_threshold"]:
                    results.append({
                        "content": hit.get("content", ""),
                        "metadata": {
                            "source": hit.get("source", "Unknown"),
                            "page": hit.get("page", 1),
                            "score": score,
                            "chunk_type": hit.get("chunk_type", "text"),
                            "document_id": hit.get("document_id", ""),
                            "collection": self.collection_name,
                            "search_method": "contextual_search",
                            "context_used": len(relevant_context),
                            "context_weight": context_weight,
                            "metric_used": detected_metric
                        }
                    })
            
            logger.info(f"✅ CONTEXTUAL: Found {len(results)} results with context from {len(relevant_context)} turns using {detected_metric} metric")
            return results
            
        except Exception as e:
            logger.error(f"❌ CONTEXTUAL: Search failed with error: {e}")
            logger.error(f"❌ CONTEXTUAL: Collection: {self.collection_name}, Attempted metric: {detected_metric if 'detected_metric' in locals() else 'Unknown'}")
            return []
    
    def _similarity_threshold_search(self, query: str, params: Dict[str, Any], content_filter_expr: str = None) -> List[Dict[str, Any]]:
        """Return all results above similarity threshold with auto-detected metric"""
        try:
            # Auto-detect collection metric type
            detected_metric = self.get_collection_metric_type(self.collection_name)
            logger.info(f"🔍 THRESHOLD: Using detected metric: {detected_metric}")
            
            # Generate query embedding
            query_vector = self.embedding_service.encode_query(query)
            
            # Search with high limit to get all potential matches
            search_request = SearchRequest(
                collection_name=self.collection_name,
                query_vectors=[query_vector],
                index_type=IndexType(params["index_type"]),
                metric_type=MetricType(detected_metric),  # Use detected metric
                limit=params["max_results"],
                filter_expression=content_filter_expr if content_filter_expr else "",
                output_fields=["*"]  # Return all fields
            )
            
            # Perform search
            search_result = self.milvus_service.search(search_request)
            
            # Filter by strict threshold
            threshold = params["similarity_threshold"]
            results = []
            
            for hit in search_result.hits:
                score = hit.get("score", 0.0)
                if score >= threshold:
                    results.append({
                        "content": hit.get("content", ""),
                        "metadata": {
                            "source": hit.get("source", "Unknown"),
                            "page": hit.get("page", 1),
                            "score": score,
                            "chunk_type": hit.get("chunk_type", "text"),
                            "document_id": hit.get("document_id", ""),
                            "collection": self.collection_name,
                            "search_method": "similarity_threshold",
                            "threshold_used": threshold,
                            "metric_used": detected_metric
                        }
                    })
            
            logger.info(f"✅ THRESHOLD: Found {len(results)} results above threshold {threshold} using {detected_metric} metric")
            return results
            
        except Exception as e:
            logger.error(f"❌ THRESHOLD: Search failed with error: {e}")
            logger.error(f"❌ THRESHOLD: Collection: {self.collection_name}, Attempted metric: {detected_metric if 'detected_metric' in locals() else 'Unknown'}")
            return []
    
    def _multi_collection_search(self, query: str, params: Dict[str, Any], content_filter_expr: str = None) -> List[Dict[str, Any]]:
        """Search across multiple collections"""
        try:
            collections = params["collections"]
            collection_weights = json.loads(params.get("collection_weights", "{}"))
            search_limit = params["search_limit_per_collection"]
            merge_strategy = params["merge_strategy"]
            
            # Generate query embedding
            query_vector = self.embedding_service.encode_query(query)
            
            all_results = []
            
            # Search each collection
            for collection in collections:
                try:
                    # Use project-specific collection name if it's the main collection
                    actual_collection = self.collection_name if collection == "project_documents" else collection
                    
                    # Auto-detect metric for this collection
                    detected_metric = self.get_collection_metric_type(actual_collection)
                    logger.debug(f"🔍 MULTI: Collection {actual_collection} uses {detected_metric} metric")
                    
                    search_request = SearchRequest(
                        collection_name=actual_collection,
                        query_vectors=[query_vector],
                        index_type=IndexType.AUTOINDEX,
                        metric_type=MetricType(detected_metric),  # Use detected metric
                        limit=search_limit,
                        filter_expression=content_filter_expr if content_filter_expr and collection == "project_documents" else "",
                        output_fields=["*"]  # Return all fields
                    )
                    
                    search_result = self.milvus_service.search(search_request)
                    weight = collection_weights.get(collection, 1.0)
                    
                    # Add weighted results
                    for hit in search_result.hits:
                        weighted_score = hit.get("score", 0.0) * weight
                        all_results.append({
                            "content": hit.get("content", ""),
                            "metadata": {
                                "source": hit.get("source", "Unknown"),
                                "page": hit.get("page", 1),
                                "score": weighted_score,
                                "original_score": hit.get("score", 0.0),
                                "weight": weight,
                                "chunk_type": hit.get("chunk_type", "text"),
                                "document_id": hit.get("document_id", ""),
                                "collection": collection,
                                "search_method": "multi_collection"
                            }
                        })
                        
                except Exception as e:
                    logger.warning(f"❌ MULTI: Failed to search collection {collection}: {e}")
                    continue
            
            # Apply merge strategy
            if merge_strategy == "weighted_merge":
                all_results.sort(key=lambda x: x["metadata"]["score"], reverse=True)
            elif merge_strategy == "top_k_merge":
                # Keep top results from each collection
                all_results.sort(key=lambda x: x["metadata"]["original_score"], reverse=True)
            # round_robin would need more complex logic
            
            logger.info(f"📚 MULTI: Found {len(all_results)} results across {len(collections)} collections")
            return all_results[:search_limit * len(collections)]
            
        except Exception as e:
            logger.error(f"❌ MULTI: Search failed: {e}")
            return []
    
    def _hierarchical_search(self, query: str, params: Dict[str, Any], content_filter_expr: str = None) -> List[Dict[str, Any]]:
        """Search with document hierarchy awareness"""
        try:
            # This would require hierarchy metadata in the vector database
            # For now, implement as enhanced semantic search with structure preservation
            
            query_vector = self.embedding_service.encode_query(query)
            hierarchy_levels = params["hierarchy_levels"]
            level_weights = json.loads(params.get("level_weights", "{}"))
            
            # Create filter for hierarchy levels if available
            level_filter = " || ".join([f'chunk_type == "{level}"' for level in hierarchy_levels])
            
            # Auto-detect collection metric type
            detected_metric = self.get_collection_metric_type(self.collection_name)
            logger.info(f"🔍 HIERARCHICAL: Using detected metric: {detected_metric}")
            
            # Combine level filter with content filter
            combined_filter = ""
            if level_filter and content_filter_expr:
                combined_filter = f"({level_filter}) && ({content_filter_expr})"
            elif level_filter:
                combined_filter = level_filter
            elif content_filter_expr:
                combined_filter = content_filter_expr
            
            search_request = SearchRequest(
                collection_name=self.collection_name,
                query_vectors=[query_vector],
                index_type=IndexType.AUTOINDEX,
                metric_type=MetricType(detected_metric),  # Use detected metric
                limit=params["search_limit"],
                filter_expression=combined_filter if combined_filter else "",
                output_fields=["*"]  # Return all fields
            )
            
            search_result = self.milvus_service.search(search_request)
            
            # Apply hierarchy weights
            results = []
            for hit in search_result.hits:
                chunk_type = hit.get("chunk_type", "text")
                weight = level_weights.get(chunk_type, 1.0)
                weighted_score = hit.get("score", 0.0) * weight
                
                results.append({
                    "content": hit.get("content", ""),
                    "metadata": {
                        "source": hit.get("source", "Unknown"),
                        "page": hit.get("page", 1),
                        "score": weighted_score,
                        "original_score": hit.get("score", 0.0),
                        "hierarchy_weight": weight,
                        "chunk_type": chunk_type,
                        "document_id": hit.get("document_id", ""),
                        "collection": self.collection_name,
                        "search_method": "hierarchical_search",
                        "metric_used": detected_metric
                    }
                })
            
            # Sort by weighted score
            results.sort(key=lambda x: x["metadata"]["score"], reverse=True)
            
            logger.info(f"✅ HIERARCHICAL: Found {len(results)} results with hierarchy weighting using {detected_metric} metric")
            return results
            
        except Exception as e:
            logger.error(f"❌ HIERARCHICAL: Search failed with error: {e}")
            logger.error(f"❌ HIERARCHICAL: Collection: {self.collection_name}, Attempted metric: {detected_metric if 'detected_metric' in locals() else 'Unknown'}")
            return []
    
    def _keyword_search(self, query: str, params: Dict[str, Any], content_filter_expr: str = None) -> List[Dict[str, Any]]:
        """Perform keyword-based search"""
        try:
            # This is a simplified keyword search implementation
            # In a full implementation, you'd use a text search engine like Elasticsearch
            
            search_limit = params["search_limit"]
            boost_exact = params["boost_exact_match"]
            min_length = params["min_keyword_length"]
            
            # Extract keywords
            keywords = [word.lower().strip() for word in query.split() 
                       if len(word.strip()) >= min_length]
            
            if not keywords:
                logger.warning("📚 KEYWORD: No valid keywords found")
                return []
            
            # Auto-detect collection metric type
            detected_metric = self.get_collection_metric_type(self.collection_name)
            logger.info(f"🔍 KEYWORD: Using detected metric: {detected_metric}")
            
            # For now, use semantic search as fallback and simulate keyword scoring
            query_vector = self.embedding_service.encode_query(query)
            
            search_request = SearchRequest(
                collection_name=self.collection_name,
                query_vectors=[query_vector],
                index_type=IndexType.FLAT,  # Use FLAT for exact matching
                metric_type=MetricType(detected_metric),  # Use detected metric
                limit=search_limit * 2,  # Get more to filter
                filter_expression=content_filter_expr if content_filter_expr else "",
                output_fields=["*"]  # Return all fields
            )
            
            search_result = self.milvus_service.search(search_request)
            
            # Score based on keyword matches
            results = []
            for hit in search_result.hits:
                content = hit.get("content", "").lower()
                
                # Count keyword matches
                exact_matches = sum(1 for keyword in keywords if keyword in content)
                partial_matches = sum(1 for keyword in keywords 
                                    if any(keyword in word for word in content.split()))
                
                if exact_matches > 0 or partial_matches > 0:
                    # Calculate keyword score
                    keyword_score = (exact_matches * 2 + partial_matches) / len(keywords)
                    if boost_exact and exact_matches > 0:
                        keyword_score *= 1.5
                    
                    results.append({
                        "content": hit.get("content", ""),
                        "metadata": {
                            "source": hit.get("source", "Unknown"),
                            "page": hit.get("page", 1),
                            "score": keyword_score,
                            "exact_matches": exact_matches,
                            "partial_matches": partial_matches,
                            "chunk_type": hit.get("chunk_type", "text"),
                            "document_id": hit.get("document_id", ""),
                            "collection": self.collection_name,
                            "search_method": "keyword_search",
                            "keywords_used": keywords,
                            "metric_used": detected_metric
                        }
                    })
            
            # Sort by keyword score
            results.sort(key=lambda x: x["metadata"]["score"], reverse=True)
            results = results[:search_limit]
            
            logger.info(f"✅ KEYWORD: Found {len(results)} results for keywords: {keywords} using {detected_metric} metric")
            return results
            
        except Exception as e:
            logger.error(f"❌ KEYWORD: Search failed with error: {e}")
            logger.error(f"❌ KEYWORD: Collection: {self.collection_name}, Attempted metric: {detected_metric if 'detected_metric' in locals() else 'Unknown'}")
            return []
    
    def create_rag_function_for_agent(self, agent_config: Dict[str, Any]):
        """
        Create a RAG retrieval function for AutoGen agents
        
        Args:
            agent_config: Agent configuration with DocAware settings
            
        Returns:
            Function that can be used by agents for document retrieval
        """
        search_method = SearchMethod(agent_config.get('search_method', SearchMethod.SEMANTIC_SEARCH))
        method_parameters = agent_config.get('search_parameters', {})
        
        logger.info(f"📚 RAG FUNCTION: Creating function with {search_method.value} method")
        
        def retrieve_documents(query: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
            """
            Retrieve relevant documents for agent query
            
            Args:
                query: Search query string
                limit: Override search limit
                
            Returns:
                List of relevant document chunks with metadata
            """
            try:
                # Override limit if provided
                params = method_parameters.copy()
                if limit:
                    if 'search_limit' in params:
                        params['search_limit'] = limit
                    elif 'max_results' in params:
                        params['max_results'] = limit
                
                # Perform search
                results = self.search_documents(
                    query=query,
                    search_method=search_method,
                    method_parameters=params,
                    conversation_context=self.conversation_context
                )
                
                logger.info(f"📚 RAG RETRIEVAL: Found {len(results)} documents for query: '{query[:50]}...'")
                return results
                
            except Exception as e:
                logger.error(f"📚 RAG RETRIEVAL: Failed: {e}")
                return []
        
        return retrieve_documents
    
    def update_conversation_context(self, new_context: List[str]):
        """Update conversation context for future searches"""
        self.conversation_context = new_context[-10:]  # Keep last 10 turns
        logger.debug(f"📚 CONTEXT: Updated with {len(self.conversation_context)} turns")
    
    def get_available_collections(self) -> List[str]:
        """Get list of available collections for multi-collection search"""
        try:
            collections = self.milvus_service.list_collections()
            # Filter for project-related collections
            project_collections = [col for col in collections if self.project_id in col]
            
            # Add standard collection types
            standard_collections = ["project_documents", "knowledge_base", "chat_history", "external_docs"]
            return standard_collections + project_collections
            
        except Exception as e:
            logger.error(f"📚 COLLECTIONS: Failed to get collections: {e}")
            return ["project_documents"]
    
    def get_hierarchical_paths(self) -> List[Dict[str, Any]]:
        """
        Get unique hierarchical paths for content filtering from Milvus collection
        Returns unique folder paths only (no individual files)
        """
        try:
            logger.info(f"📚 HIERARCHICAL PATHS: Getting unique folder paths for collection {self.collection_name}")
            
            # Create a search request to get all documents with hierarchical_path
            # We'll use a dummy query vector but search with a very high limit to get all documents
            dummy_query = [0.0] * 384  # 384-dimensional zero vector for all-MiniLM-L6-v2
            
            from django_milvus_search.models import SearchRequest, IndexType, MetricType
            
            # Auto-detect collection metric type
            detected_metric = self.get_collection_metric_type(self.collection_name)
            
            search_request = SearchRequest(
                collection_name=self.collection_name,
                query_vectors=[dummy_query],
                index_type=IndexType.AUTOINDEX,
                metric_type=MetricType(detected_metric),
                limit=10000,  # High limit to get all documents
                output_fields=["hierarchical_path"]  # Only get hierarchical_path field
            )
            
            # Perform search
            search_result = self.milvus_service.search(search_request)
            
            # Extract unique hierarchical paths (folders only)
            unique_folder_paths = set()
            
            for hit in search_result.hits:
                hierarchical_path = hit.get("hierarchical_path", "")
                
                if hierarchical_path and hierarchical_path.strip():
                    # Clean the path
                    clean_path = hierarchical_path.strip().strip('/')
                    if clean_path:
                        # Add the full path as a folder
                        unique_folder_paths.add(clean_path)
                        
                        # Also add all parent folder paths
                        path_parts = clean_path.split('/')
                        for i in range(1, len(path_parts)):
                            parent_path = '/'.join(path_parts[:i])
                            if parent_path:
                                unique_folder_paths.add(parent_path)
            
            # Convert to sorted list of folder entries
            folder_list = []
            for folder_path in sorted(unique_folder_paths):
                folder_list.append({
                    "id": f"folder_{folder_path}",
                    "name": folder_path.split('/')[-1],  # Last part of path as folder name
                    "path": folder_path,
                    "type": "folder",
                    "displayName": folder_path,
                    "isFolder": True
                })
            
            logger.info(f"📚 HIERARCHICAL PATHS: Found {len(folder_list)} unique folder paths")
            if folder_list:
                logger.info(f"📚 HIERARCHICAL PATHS: Sample paths: {[f['displayName'] for f in folder_list[:5]]}")
            
            return folder_list
            
        except Exception as e:
            logger.error(f"📚 HIERARCHICAL PATHS: Failed to get paths: {e}")
            import traceback
            logger.error(f"📚 HIERARCHICAL PATHS: Traceback: {traceback.format_exc()}")
            return []

