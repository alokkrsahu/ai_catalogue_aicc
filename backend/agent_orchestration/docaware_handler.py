"""
DocAware Handler
===============

Handles DocAware integration and context management for conversation orchestration.
"""

import logging
from typing import Dict, List, Any, Optional
from asgiref.sync import sync_to_async

# Import DocAware services
from .docaware import EnhancedDocAwareAgentService, SearchMethod

logger = logging.getLogger('conversation_orchestrator')


class DocAwareHandler:
    """
    Handles DocAware integration and document context retrieval
    """
    
    def is_docaware_enabled(self, agent_node: Dict[str, Any]) -> bool:
        """
        Check if DocAware is enabled for this agent
        """
        agent_data = agent_node.get('data', {})
        return agent_data.get('doc_aware', False) and agent_data.get('search_method')
    
    async def get_docaware_context_from_conversation_query(self, agent_node: Dict[str, Any], search_query: str, project_id: str, conversation_history: str) -> str:
        """
        Retrieve document context using conversation-based search query for single agents
        
        Args:
            agent_node: Agent configuration
            search_query: Search query extracted from conversation
            project_id: Project ID for document search
            conversation_history: Full conversation history for context
            
        Returns:
            Formatted document context string
        """
        agent_data = agent_node.get('data', {})
        search_method = agent_data.get('search_method', 'semantic_search')
        search_parameters = agent_data.get('search_parameters', {})
        
        logger.info(f"📚 DOCAWARE: Single agent searching with method {search_method}")
        logger.info(f"📚 DOCAWARE: Query: {search_query[:100]}...")
        
        try:
            # Initialize DocAware service for this project using sync_to_async
            def create_docaware_service():
                return EnhancedDocAwareAgentService(project_id)
            
            docaware_service = await sync_to_async(create_docaware_service)()
            
            # Extract conversation context for contextual search methods
            conversation_context = self.extract_conversation_context(conversation_history)
            
            # Perform document search with the conversation-based query using sync_to_async
            def perform_search():
                return docaware_service.search_documents(
                    query=search_query,
                    search_method=SearchMethod(search_method),
                    method_parameters=search_parameters,
                    conversation_context=conversation_context
                )
            
            search_results = await sync_to_async(perform_search)()
            
            if not search_results:
                logger.info(f"📚 DOCAWARE: No relevant documents found for single agent query")
                return ""
            
            # Format results for prompt inclusion
            context_parts = []
            context_parts.append(f"Found {len(search_results)} relevant documents based on conversation context:\n")
            
            for i, result in enumerate(search_results[:5], 1):  # Limit to top 5 results
                content = result['content']
                metadata = result['metadata']
                
                # Truncate content for prompt efficiency
                if len(content) > 400:
                    content = content[:400] + f"... [content truncated]"
                
                context_parts.append(f"📄 Document {i} (Relevance: {metadata.get('score', 0):.3f}):")
                context_parts.append(f"   Source: {metadata.get('source', 'Unknown')}")
                
                if metadata.get('page'):
                    context_parts.append(f"   Page: {metadata['page']}")
                    
                context_parts.append(f"   Content: {content}")
                context_parts.append("")  # Empty line separator
            
            # Add search metadata
            context_parts.append(f"Search performed using: {search_method}")
            context_parts.append(f"Query derived from conversation history")
            
            result_text = "\n".join(context_parts)
            logger.info(f"📚 DOCAWARE: Generated context from {len(search_results)} results ({len(result_text)} chars)")
            
            return result_text
            
        except Exception as e:
            logger.error(f"❌ DOCAWARE: Error retrieving document context from conversation query: {e}")
            import traceback
            logger.error(f"❌ DOCAWARE: Traceback: {traceback.format_exc()}")
            return f"⚠️ Document search failed: {str(e)}"
    
    def get_docaware_context(self, agent_node: Dict[str, Any], conversation_history: str, project_id: str) -> str:
        """
        Retrieve document context using DocAware service
        """
        agent_data = agent_node.get('data', {})
        search_method = agent_data.get('search_method', 'semantic_search')
        search_parameters = agent_data.get('search_parameters', {})
        
        logger.info(f"📚 DOCAWARE: Getting context for agent with method {search_method}")
        
        try:
            # Initialize DocAware service for this project
            docaware_service = EnhancedDocAwareAgentService(project_id)
            
            # Extract query from recent conversation history
            query = self.extract_query_from_conversation(conversation_history)
            
            if not query:
                logger.warning(f"📚 DOCAWARE: No query could be extracted from conversation history")
                return ""
            
            # Get conversation context for contextual search
            conversation_context = self.extract_conversation_context(conversation_history)
            
            # Perform document search
            search_results = docaware_service.search_documents(
                query=query,
                search_method=SearchMethod(search_method),
                method_parameters=search_parameters,
                conversation_context=conversation_context
            )
            
            if not search_results:
                logger.info(f"📚 DOCAWARE: No relevant documents found for query: {query[:50]}...")
                return ""
            
            # Format results for prompt
            context_parts = []
            context_parts.append(f"Found {len(search_results)} relevant documents for your query:\n")
            
            for i, result in enumerate(search_results[:5], 1):  # Limit to top 5 results
                content = result['content'][:500] + "..." if len(result['content']) > 500 else result['content']
                metadata = result['metadata']
                
                context_parts.append(f"Document {i} (Score: {metadata.get('score', 0):.3f}):")
                context_parts.append(f"Source: {metadata.get('source', 'Unknown')}")
                if metadata.get('page'):
                    context_parts.append(f"Page: {metadata['page']}")
                context_parts.append(f"Content: {content}")
                context_parts.append("")  # Empty line separator
            
            result_text = "\n".join(context_parts)
            logger.info(f"📚 DOCAWARE: Generated context with {len(search_results)} results ({len(result_text)} chars)")
            
            return result_text
            
        except Exception as e:
            logger.error(f"❌ DOCAWARE: Error retrieving document context: {e}")
            return ""
    
    def extract_query_from_conversation(self, conversation_history: str, max_length: int = 200) -> str:
        """
        Extract a search query from the conversation history
        """
        logger.info(f"📚 DOCAWARE QUERY EXTRACTION: Starting with conversation: '{conversation_history[:200]}...'")
        
        if not conversation_history.strip():
            logger.warning(f"📚 DOCAWARE QUERY EXTRACTION: Empty conversation history")
            return ""
        
        # Split conversation into turns
        lines = conversation_history.strip().split('\n')
        logger.info(f"📚 DOCAWARE QUERY EXTRACTION: Split into {len(lines)} lines: {lines}")
        
        # Get the last few meaningful lines (skip empty lines)
        recent_lines = [line.strip() for line in lines[-5:] if line.strip()]
        logger.info(f"📚 DOCAWARE QUERY EXTRACTION: Recent lines: {recent_lines}")
        
        if not recent_lines:
            logger.warning(f"📚 DOCAWARE QUERY EXTRACTION: No recent meaningful lines found")
            return ""
        
        # Use the last user message or a combination of recent context
        query_text = " ".join(recent_lines)
        logger.info(f"📚 DOCAWARE QUERY EXTRACTION: Combined query text: '{query_text}'")
        
        # Truncate if too long
        if len(query_text) > max_length:
            query_text = query_text[:max_length].rsplit(' ', 1)[0] + "..."
            logger.info(f"📚 DOCAWARE QUERY EXTRACTION: Truncated to: '{query_text}'")
        
        # Check for forbidden patterns
        rejected_queries = ['test query', 'test query for document search', 'sample query', 'example query']
        if query_text.lower().strip() in rejected_queries:
            logger.error(f"📚 DOCAWARE QUERY EXTRACTION: DETECTED FORBIDDEN QUERY: '{query_text}' - This should not happen!")
            logger.error(f"📚 DOCAWARE QUERY EXTRACTION: Original conversation history was: '{conversation_history}'")
            # Return empty to prevent the forbidden query from being used
            return ""
        
        logger.info(f"📚 DOCAWARE QUERY EXTRACTION: Final extracted query: '{query_text[:100]}...'")
        return query_text
    
    def extract_conversation_context(self, conversation_history: str, max_turns: int = 3) -> List[str]:
        """
        Extract conversation context for contextual search
        """
        if not conversation_history.strip():
            return []
        
        # Split into turns and get recent ones
        lines = conversation_history.strip().split('\n')
        meaningful_lines = [line.strip() for line in lines if line.strip()]
        
        # Take last few turns
        recent_context = meaningful_lines[-max_turns:] if meaningful_lines else []
        
        logger.debug(f"📚 DOCAWARE: Extracted context with {len(recent_context)} turns")
        return recent_context
    
    def extract_search_query_from_aggregated_input(self, aggregated_context: Dict[str, Any]) -> str:
        """
        Extract search query from aggregated input context (all connected agent outputs)
        
        Args:
            aggregated_context: Output from aggregate_multiple_inputs
            
        Returns:
            Search query string extracted from aggregated inputs
        """
        logger.info(f"📚 AGGREGATED INPUT QUERY EXTRACTION: Starting with {aggregated_context['input_count']} inputs")
        logger.info(f"📚 AGGREGATED INPUT QUERY EXTRACTION: Primary input: '{str(aggregated_context.get('primary_input', ''))[:200]}...'")
        logger.info(f"📚 AGGREGATED INPUT QUERY EXTRACTION: Secondary inputs count: {len(aggregated_context.get('secondary_inputs', []))}")
        
        # Combine all input content for search query
        query_parts = []
        
        # Add primary input
        if aggregated_context['primary_input']:
            primary_input = str(aggregated_context['primary_input'])
            query_parts.append(primary_input)
            logger.info(f"📚 AGGREGATED INPUT QUERY EXTRACTION: Added primary input: '{primary_input[:100]}...'")
        
        # Add secondary inputs
        for i, secondary in enumerate(aggregated_context['secondary_inputs']):
            if secondary.get('content'):
                secondary_content = str(secondary['content'])
                query_parts.append(secondary_content)
                logger.info(f"📚 AGGREGATED INPUT QUERY EXTRACTION: Added secondary input {i+1}: '{secondary_content[:100]}...'")
        
        # Combine and clean up
        combined_query = " ".join(query_parts).strip()
        logger.info(f"📚 AGGREGATED INPUT QUERY EXTRACTION: Combined query before processing: '{combined_query[:200]}...'")
        
        if not combined_query:
            logger.warning(f"📚 AGGREGATED INPUT QUERY EXTRACTION: Empty combined query")
            return ""
        
        # Limit query length for search efficiency
        max_query_length = 500
        if len(combined_query) > max_query_length:
            # Try to break at sentence boundary
            truncated = combined_query[:max_query_length]
            last_sentence_end = max(truncated.rfind('.'), truncated.rfind('!'), truncated.rfind('?'))
            
            if last_sentence_end > max_query_length * 0.7:  # If we can get at least 70% with complete sentences
                combined_query = truncated[:last_sentence_end + 1]
            else:
                # Break at word boundary
                combined_query = truncated.rsplit(' ', 1)[0] + "..."
            logger.info(f"📚 AGGREGATED INPUT QUERY EXTRACTION: Truncated to: '{combined_query}'")
        
        # Check for forbidden patterns
        rejected_queries = ['test query', 'test query for document search', 'sample query', 'example query']
        if combined_query.lower().strip() in rejected_queries:
            logger.error(f"📚 AGGREGATED INPUT QUERY EXTRACTION: DETECTED FORBIDDEN QUERY: '{combined_query}' - This should not happen!")
            logger.error(f"📚 AGGREGATED INPUT QUERY EXTRACTION: Original aggregated context was: {aggregated_context}")
            # Return empty to prevent the forbidden query from being used
            return ""
        
        logger.info(f"📚 AGGREGATED INPUT QUERY EXTRACTION: Final extracted query: '{combined_query[:100]}...'")
        
        return combined_query
    
    async def get_docaware_context_from_query(self, agent_node: Dict[str, Any], search_query: str, project_id: str, aggregated_context: Dict[str, Any]) -> str:
        """
        Retrieve document context using a specific search query (from aggregated input)
        
        Args:
            agent_node: Agent configuration
            search_query: Search query extracted from aggregated inputs
            project_id: Project ID for document search
            aggregated_context: Full aggregated context for metadata
            
        Returns:
            Formatted document context string
        """
        agent_data = agent_node.get('data', {})
        search_method = agent_data.get('search_method', 'semantic_search')
        search_parameters = agent_data.get('search_parameters', {})
        
        logger.info(f"📚 DOCAWARE: Searching documents with method {search_method}")
        logger.info(f"📚 DOCAWARE: Query: {search_query[:100]}...")
        
        try:
            # Initialize DocAware service for this project using sync_to_async
            def create_docaware_service():
                return EnhancedDocAwareAgentService(project_id)
            
            docaware_service = await sync_to_async(create_docaware_service)()
            
            # Extract conversation context from aggregated input for contextual search methods
            conversation_context = self.extract_conversation_context_from_aggregated_input(aggregated_context)
            
            # Perform document search with the aggregated input query using sync_to_async
            def perform_search():
                return docaware_service.search_documents(
                    query=search_query,
                    search_method=SearchMethod(search_method),
                    method_parameters=search_parameters,
                    conversation_context=conversation_context
                )
            
            search_results = await sync_to_async(perform_search)()
            
            if not search_results:
                logger.info(f"📚 DOCAWARE: No relevant documents found for aggregated input query")
                return ""
            
            # Format results for prompt inclusion
            context_parts = []
            context_parts.append(f"Found {len(search_results)} relevant documents based on connected agent inputs:\n")
            
            for i, result in enumerate(search_results[:5], 1):  # Limit to top 5 results
                content = result['content']
                metadata = result['metadata']
                
                # Truncate content for prompt efficiency
                if len(content) > 400:
                    content = content[:400] + f"... [content truncated]"
                
                context_parts.append(f"📄 Document {i} (Relevance: {metadata.get('score', 0):.3f}):")
                context_parts.append(f"   Source: {metadata.get('source', 'Unknown')}")
                
                if metadata.get('page'):
                    context_parts.append(f"   Page: {metadata['page']}")
                    
                context_parts.append(f"   Content: {content}")
                context_parts.append("")  # Empty line separator
            
            # Add search metadata
            context_parts.append(f"Search performed using: {search_method}")
            context_parts.append(f"Query derived from {aggregated_context['input_count']} connected agent outputs")
            
            result_text = "\n".join(context_parts)
            logger.info(f"📚 DOCAWARE: Generated context from {len(search_results)} results ({len(result_text)} chars)")
            
            return result_text
            
        except Exception as e:
            logger.error(f"❌ DOCAWARE: Error retrieving document context from aggregated input: {e}")
            import traceback
            logger.error(f"❌ DOCAWARE: Traceback: {traceback.format_exc()}")
            return f"⚠️ Document search failed: {str(e)}"
    
    def extract_conversation_context_from_aggregated_input(self, aggregated_context: Dict[str, Any]) -> List[str]:
        """
        Extract conversation context from aggregated input for contextual search methods
        
        Args:
            aggregated_context: Output from aggregate_multiple_inputs
            
        Returns:
            List of conversation context strings
        """
        context_list = []
        
        # Add primary input as context
        if aggregated_context['primary_input']:
            context_list.append(str(aggregated_context['primary_input']))
        
        # Add secondary inputs as context
        for secondary in aggregated_context['secondary_inputs']:
            if secondary.get('content'):
                context_list.append(f"{secondary['name']}: {secondary['content']}")
        
        logger.debug(f"📚 DOCAWARE: Extracted {len(context_list)} context items from aggregated input")
        return context_list