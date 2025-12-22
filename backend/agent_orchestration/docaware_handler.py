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
    
    def __init__(self, llm_provider_manager=None):
        """
        Initialize DocAwareHandler
        
        Args:
            llm_provider_manager: Optional LLMProviderManager instance for query refinement
        """
        self.llm_provider_manager = llm_provider_manager
    
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

            # Extract content_filters from agent config
            content_filters = agent_data.get('content_filters', [])

            # Perform document search with the conversation-based query using sync_to_async
            def perform_search():
                return docaware_service.search_documents(
                    query=search_query,
                    search_method=SearchMethod(search_method),
                    method_parameters=search_parameters,
                    conversation_context=conversation_context,
                    content_filters=content_filters
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

            # Extract content_filters from agent config
            content_filters = agent_data.get('content_filters', [])

            # Perform document search
            search_results = docaware_service.search_documents(
                query=query,
                search_method=SearchMethod(search_method),
                method_parameters=search_parameters,
                conversation_context=conversation_context,
                content_filters=content_filters
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
    
    def extract_query_from_conversation(self, conversation_history: str, max_length: Optional[int] = None) -> str:
        """
        Extract a search query from the conversation history
        
        Intelligently extracts the user's actual question, not the full conversation.
        Prioritizes the last user message, ignoring assistant responses and start node messages.
        
        Args:
            conversation_history: Full conversation history
            max_length: Optional maximum length (default: None - no limit)
                       Kept for backward compatibility but not enforced
        """
        logger.info(f"📚 DOCAWARE QUERY EXTRACTION: Starting with conversation: '{conversation_history[:200]}...'")
        
        if not conversation_history.strip():
            logger.warning(f"📚 DOCAWARE QUERY EXTRACTION: Empty conversation history")
            return ""
        
        # Split conversation into lines
        lines = conversation_history.strip().split('\n')
        logger.info(f"📚 DOCAWARE QUERY EXTRACTION: Split into {len(lines)} lines")
        
        # Look for the last user message (most relevant for search)
        # Format can be: "User: ..." or "User: ..." or node names like "Start Node: ..."
        user_query = None
        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
            
            # Check if this is a user message
            # Patterns: "User:", "user:", or lines that don't start with assistant/agent names
            line_lower = line.lower()
            
            # Skip assistant/agent responses
            if any(skip in line_lower for skip in ['assistant:', 'ai assistant', 'start node:', 'end node:']):
                continue
            
            # Check for explicit "User:" prefix
            if line_lower.startswith('user:'):
                user_query = line.split(':', 1)[1].strip() if ':' in line else line
                logger.info(f"📚 DOCAWARE QUERY EXTRACTION: Found user message with 'User:' prefix: '{user_query[:100]}...'")
                break
            
            # If no explicit "User:" found, check if line doesn't look like an assistant response
            # and contains a question or query-like content
            if ':' in line:
                prefix = line.split(':', 1)[0].strip().lower()
                # If it's not an assistant/agent prefix, it might be a user message
                if 'assistant' not in prefix and 'ai' not in prefix and 'start' not in prefix and 'end' not in prefix:
                    # This might be a user message without explicit "User:" label
                    potential_query = line.split(':', 1)[1].strip() if ':' in line else line
                    # Only use if it looks like a question/query (has question words or is reasonably short)
                    if any(word in potential_query.lower() for word in ['what', 'how', 'tell', 'explain', 'find', 'search', 'about', '?']):
                        user_query = potential_query
                        logger.info(f"📚 DOCAWARE QUERY EXTRACTION: Found potential user query: '{user_query[:100]}...'")
                        break
        
        # If we found a user query, use it
        if user_query:
            query_text = user_query
        else:
            # Fallback: get the last few meaningful lines (excluding assistant responses)
            recent_lines = []
            for line in reversed(lines[-10:]):
                line = line.strip()
                if not line:
                    continue
                line_lower = line.lower()
                # Skip assistant/agent responses
                if any(skip in line_lower for skip in ['assistant:', 'ai assistant', 'start node:', 'end node:']):
                    continue
                recent_lines.insert(0, line)
                if len(recent_lines) >= 3:  # Limit to last 3 non-assistant lines
                    break
            
            if recent_lines:
                query_text = " ".join(recent_lines)
                logger.info(f"📚 DOCAWARE QUERY EXTRACTION: Using fallback - combined {len(recent_lines)} lines")
            else:
                logger.warning(f"📚 DOCAWARE QUERY EXTRACTION: No user query found in conversation history")
                return ""
        
        logger.info(f"📚 DOCAWARE QUERY EXTRACTION: Extracted query length: {len(query_text)} characters")
        logger.info(f"📚 DOCAWARE QUERY EXTRACTION: Query: '{query_text[:200]}...'")
        
        # No truncation by default - use full query to preserve all context
        # The embedding model will handle longer queries internally
        # Only truncate if explicitly requested (for very long conversations)
        if max_length and len(query_text) > max_length:
            # Try to break at sentence boundary for very long conversations
            truncated = query_text[:max_length]
            last_sentence_end = max(truncated.rfind('.'), truncated.rfind('!'), truncated.rfind('?'))
            
            if last_sentence_end > max_length * 0.7:  # If we can get at least 70% with complete sentences
                query_text = truncated[:last_sentence_end + 1]
            else:
                # Break at word boundary
                query_text = truncated.rsplit(' ', 1)[0] + "..."
            logger.info(f"📚 DOCAWARE QUERY EXTRACTION: Truncated to {len(query_text)} chars due to explicit max_length limit")
        else:
            logger.info(f"📚 DOCAWARE QUERY EXTRACTION: Using full query ({len(query_text)} chars) - no truncation")
        
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
    
    def extract_search_query_from_aggregated_input(
        self, 
        aggregated_context: Dict[str, Any], 
        agent_node: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Extract search query from aggregated input context (all connected agent outputs)
        
        Args:
            aggregated_context: Output from aggregate_multiple_inputs
            agent_node: Optional agent node for query refinement settings
            
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
        logger.info(f"📚 AGGREGATED INPUT QUERY EXTRACTION: Combined query length: {len(combined_query)} characters")
        logger.info(f"📚 AGGREGATED INPUT QUERY EXTRACTION: Combined query preview: '{combined_query[:200]}...'")
        
        if not combined_query:
            logger.warning(f"📚 AGGREGATED INPUT QUERY EXTRACTION: Empty combined query")
            return ""
        
        # No truncation - use full query to preserve all context
        # The embedding model will handle longer queries internally
        logger.info(f"📚 AGGREGATED INPUT QUERY EXTRACTION: Using full query ({len(combined_query)} chars) - no truncation")
        
        # Check for forbidden patterns
        rejected_queries = ['test query', 'test query for document search', 'sample query', 'example query']
        if combined_query.lower().strip() in rejected_queries:
            logger.error(f"📚 AGGREGATED INPUT QUERY EXTRACTION: DETECTED FORBIDDEN QUERY: '{combined_query}' - This should not happen!")
            logger.error(f"📚 AGGREGATED INPUT QUERY EXTRACTION: Original aggregated context was: {aggregated_context}")
            # Return empty to prevent the forbidden query from being used
            return ""
        
        logger.info(f"📚 AGGREGATED INPUT QUERY EXTRACTION: Final extracted query: '{combined_query[:100]}...'")
        
        # Note: LLM refinement will be applied in get_docaware_context_from_query if enabled
        # This keeps the extraction method synchronous and allows async refinement later
        
        return combined_query
    
    async def refine_query_with_llm(
        self, 
        query: str, 
        project_id: str, 
        agent_node: Dict[str, Any]
    ) -> str:
        """
        Refine search query using LLM to preserve all key concepts while optimizing for search
        
        Args:
            query: Original search query (can be very long)
            project_id: Project ID for LLM API key retrieval
            agent_node: Agent configuration (may contain LLM provider settings)
            
        Returns:
            Refined query optimized for search, or original query if LLM refinement fails
        """
        if not self.llm_provider_manager:
            logger.warning(f"📚 QUERY REFINEMENT: LLM provider manager not available, using original query")
            return query
        
        if not query or len(query.strip()) < 50:
            # Don't refine very short queries
            logger.debug(f"📚 QUERY REFINEMENT: Query too short ({len(query)} chars), skipping refinement")
            return query
        
        try:
            # Get project for API key retrieval
            from users.models import IntelliDocProject
            from asgiref.sync import sync_to_async
            
            project = await sync_to_async(IntelliDocProject.objects.get)(project_id=project_id)
            
            # Get agent config for LLM provider settings
            agent_data = agent_node.get('data', {})
            
            # Use agent's LLM provider if specified, otherwise default to OpenAI
            llm_provider_type = agent_data.get('llm_provider', 'openai')
            llm_model = agent_data.get('llm_model', 'gpt-3.5-turbo')
            
            # Create LLM provider configuration
            agent_config = {
                'llm_provider': llm_provider_type,
                'llm_model': llm_model,
                'max_tokens': 200,  # Short response for query refinement
                'temperature': 0.3  # Lower temperature for more focused queries
            }
            
            logger.info(f"📚 QUERY REFINEMENT: Refining query ({len(query)} chars) using {llm_provider_type} {llm_model}")
            
            # Get LLM provider
            llm_provider = await self.llm_provider_manager.get_llm_provider(agent_config, project)
            
            if not llm_provider:
                logger.warning(f"📚 QUERY REFINEMENT: Could not create LLM provider, using original query")
                return query
            
            # Create refinement prompt
            refinement_prompt = f"""You are a search query optimizer. Your task is to create an optimal search query that preserves all key concepts from the input while being concise and effective for document retrieval.

Original query (from multiple agent outputs):
{query}

Create an optimized search query that:
1. Preserves ALL key concepts, topics, and important information
2. Combines related concepts intelligently
3. Removes redundancy and filler words
4. Maintains the semantic meaning and intent
5. Is optimized for vector similarity search

Return ONLY the refined search query, nothing else. Do not add explanations or commentary.

Refined search query:"""
            
            # Generate refined query
            llm_response = await llm_provider.generate_response(
                prompt=refinement_prompt,
                temperature=0.3
            )
            
            if llm_response.error:
                logger.warning(f"📚 QUERY REFINEMENT: LLM generation failed: {llm_response.error}, using original query")
                return query
            
            refined_query = llm_response.text.strip()
            
            # Clean up the response (remove quotes if present, trim whitespace)
            refined_query = refined_query.strip('"\'')
            
            if not refined_query or len(refined_query) < 10:
                logger.warning(f"📚 QUERY REFINEMENT: Refined query too short or empty, using original query")
                return query
            
            logger.info(f"📚 QUERY REFINEMENT: Successfully refined query from {len(query)} to {len(refined_query)} chars")
            logger.debug(f"📚 QUERY REFINEMENT: Original: '{query[:200]}...'")
            logger.debug(f"📚 QUERY REFINEMENT: Refined: '{refined_query[:200]}...'")
            
            return refined_query
            
        except Exception as e:
            logger.error(f"❌ QUERY REFINEMENT: Error during query refinement: {e}")
            import traceback
            logger.error(f"❌ QUERY REFINEMENT: Traceback: {traceback.format_exc()}")
            # Fallback to original query on any error
            return query
    
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
        
        # Check if query refinement is enabled
        query_refinement_enabled = agent_data.get('query_refinement_enabled', False)
        
        # Apply LLM refinement if enabled
        if query_refinement_enabled and self.llm_provider_manager:
            logger.info(f"📚 DOCAWARE: Query refinement enabled, refining query before search")
            search_query = await self.refine_query_with_llm(search_query, project_id, agent_node)
        
        logger.info(f"📚 DOCAWARE: Searching documents with method {search_method}")
        logger.info(f"📚 DOCAWARE: Query length: {len(search_query)} chars, preview: '{search_query[:100]}...'")
        
        try:
            # Initialize DocAware service for this project using sync_to_async
            def create_docaware_service():
                return EnhancedDocAwareAgentService(project_id)
            
            docaware_service = await sync_to_async(create_docaware_service)()
            
            # Extract conversation context from aggregated input for contextual search methods
            conversation_context = self.extract_conversation_context_from_aggregated_input(aggregated_context)

            # Extract content_filters from agent config
            content_filters = agent_data.get('content_filters', [])

            # Perform document search with the aggregated input query using sync_to_async
            def perform_search():
                return docaware_service.search_documents(
                    query=search_query,
                    search_method=SearchMethod(search_method),
                    method_parameters=search_parameters,
                    conversation_context=conversation_context,
                    content_filters=content_filters
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