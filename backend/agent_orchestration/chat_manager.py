"""
Chat Manager
============

Handles group chat management and delegate conversation execution for conversation orchestration.
"""

import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger('conversation_orchestrator')


class ChatManager:
    """
    Manages group chat orchestration and delegate conversations
    """
    
    def __init__(self, llm_provider_manager, workflow_parser, docaware_handler):
        self.llm_provider_manager = llm_provider_manager
        self.workflow_parser = workflow_parser
        self.docaware_handler = docaware_handler
    
    async def execute_group_chat_manager_with_multiple_inputs(self, chat_manager_node: Dict[str, Any], llm_provider, input_sources: List[Dict[str, Any]], executed_nodes: Dict[str, str], execution_sequence: List[Dict[str, Any]], graph_json: Dict[str, Any], project_id: Optional[str] = None) -> str:
        """
        Execute GroupChatManager with multiple inputs support
        Enhanced version that handles multiple input sources
        
        Args:
            chat_manager_node: The GroupChatManager node data
            llm_provider: LLM provider instance
            input_sources: List of input node metadata
            executed_nodes: Dict mapping node_id to their outputs
            execution_sequence: Complete workflow execution sequence
            graph_json: Full workflow graph data
            project_id: Project ID for DocAware functionality
        
        Returns:
            GroupChatManager response string
        """
        manager_name = chat_manager_node.get('data', {}).get('name', 'Chat Manager')
        manager_data = chat_manager_node.get('data', {})
        chat_manager_id = chat_manager_node.get('id')
        
        logger.info(f"👥 GROUP CHAT MANAGER (MULTI-INPUT): Starting enhanced execution for {manager_name}")
        logger.info(f"📥 GROUP CHAT MANAGER (MULTI-INPUT): Processing {len(input_sources)} input sources")
        
        # Aggregate multiple inputs into structured context
        aggregated_context = self.workflow_parser.aggregate_multiple_inputs(input_sources, executed_nodes)
        formatted_context = self.workflow_parser.format_multiple_inputs_prompt(aggregated_context)
        
        # Find all delegate agents connected to this GroupChatManager
        delegate_nodes = []
        edges = graph_json.get('edges', [])
        
        # Find all nodes that have incoming edges from this GroupChatManager
        connected_delegate_ids = set()
        for edge in edges:
            if edge.get('source') == chat_manager_id:
                target_id = edge.get('target')
                # Find the target node in execution sequence
                for node in execution_sequence:
                    if node.get('id') == target_id and node.get('type') == 'DelegateAgent':
                        connected_delegate_ids.add(target_id)
                        delegate_nodes.append(node)
                        logger.info(f"🔗 GROUP CHAT MANAGER (MULTI-INPUT): Found connected delegate: {node.get('data', {}).get('name', target_id)}")
        
        # Also check for bidirectional edges
        for edge in edges:
            if edge.get('target') == chat_manager_id:
                source_id = edge.get('source')
                for node in execution_sequence:
                    if node.get('id') == source_id and node.get('type') == 'DelegateAgent' and source_id not in connected_delegate_ids:
                        connected_delegate_ids.add(source_id)
                        delegate_nodes.append(node)
                        logger.info(f"🔗 GROUP CHAT MANAGER (MULTI-INPUT): Found bidirectionally connected delegate: {node.get('data', {}).get('name', source_id)}")
        
        logger.info(f"🤝 GROUP CHAT MANAGER (MULTI-INPUT): Found {len(delegate_nodes)} connected delegate agents")
        
        if not delegate_nodes:
            error_message = f"GroupChatManager {manager_name} has no connected delegate agents. Please connect DelegateAgent nodes to this GroupChatManager via edges in the workflow graph."
            logger.error(f"❌ GROUP CHAT MANAGER (MULTI-INPUT): {error_message}")
            raise Exception(error_message)
        
        # Get configuration
        max_rounds = manager_data.get('max_rounds', 10)
        if max_rounds <= 0:
            logger.warning(f"⚠️ GROUP CHAT MANAGER (MULTI-INPUT): max_rounds was {max_rounds}, setting to 1")
            max_rounds = 1
        
        termination_strategy = manager_data.get('termination_strategy', 'all_delegates_complete')
        
        logger.info(f"🔧 GROUP CHAT MANAGER (MULTI-INPUT): Configuration - max_rounds: {max_rounds}, inputs: {aggregated_context['input_count']}")
        
        # Initialize delegate tracking
        delegate_status = {}
        for delegate in delegate_nodes:
            delegate_name = delegate.get('data', {}).get('name', 'Delegate')
            delegate_status[delegate_name] = {
                'iterations': 0,
                'max_iterations': delegate.get('data', {}).get('number_of_iterations', 5),
                'termination_condition': delegate.get('data', {}).get('termination_condition', ''),  # NO DEFAULT - must come from UI
                'completed': False,
                'node': delegate
            }
        
        # Process delegates with multiple input context
        conversation_log = []
        total_iterations = 0
        
        logger.info(f"📊 GROUP CHAT MANAGER (MULTI-INPUT): Delegate status before execution: {delegate_status}")
        logger.info(f"📊 GROUP CHAT MANAGER (MULTI-INPUT): About to enter execution loop with max_rounds: {max_rounds}")
        
        # Execute all delegates with multi-input context
        logger.info(f"🔄 GROUP CHAT MANAGER (MULTI-INPUT): Starting execution loop with {len(delegate_nodes)} delegates")
        
        for round_num in range(max_rounds):
            logger.info(f"🔄 GROUP CHAT MANAGER (MULTI-INPUT): Round {round_num + 1}/{max_rounds}")
            
            delegates_processed_this_round = 0
            
            for delegate_name, status in list(delegate_status.items()):
                logger.info(f"🔄 GROUP CHAT MANAGER (MULTI-INPUT): Checking delegate {delegate_name}, completed: {status['completed']}, iterations: {status['iterations']}/{status['max_iterations']}")
                
                # Only skip if both completed AND has run at least once
                if status['completed'] and status['iterations'] > 0:
                    logger.info(f"🔄 GROUP CHAT MANAGER (MULTI-INPUT): Skipping completed delegate {delegate_name}")
                    continue
                
                logger.info(f"🔄 GROUP CHAT MANAGER (MULTI-INPUT): About to execute delegate {delegate_name}")
                delegates_processed_this_round += 1
                
                # Execute delegate with multiple input context
                try:
                    logger.info(f"📊 GROUP CHAT MANAGER (MULTI-INPUT): Calling execute_delegate_conversation_with_multiple_inputs for {delegate_name}")
                    delegate_response = await self.execute_delegate_conversation_with_multiple_inputs(
                        status['node'], 
                        llm_provider, 
                        formatted_context,  # Use multi-input formatted context
                        aggregated_context,  # Pass raw context for metadata
                        conversation_log,
                        status,
                        project_id  # Add project_id for DocAware functionality
                    )
                    logger.info(f"✅ GROUP CHAT MANAGER (MULTI-INPUT): Successfully executed delegate {delegate_name} - response length: {len(delegate_response)} chars")
                    
                    # Ensure we have a valid response
                    if not delegate_response or len(delegate_response.strip()) == 0:
                        logger.warning(f"⚠️ GROUP CHAT MANAGER (MULTI-INPUT): {delegate_name} returned empty response, creating default")
                        delegate_response = f"I am {delegate_name} and I have processed the multiple input sources. No specific output generated."
                        
                except Exception as delegate_exec_error:
                    logger.error(f"❌ GROUP CHAT MANAGER (MULTI-INPUT): Failed to execute delegate {delegate_name}: {delegate_exec_error}")
                    import traceback
                    logger.error(f"❌ GROUP CHAT MANAGER (MULTI-INPUT): Full traceback: {traceback.format_exc()}")
                    delegate_response = f"ERROR: Delegate execution failed: {delegate_exec_error}"
                
                # Always add response to conversation log
                conversation_log.append(f"[Round {round_num + 1}] {delegate_name}: {delegate_response}")
                
                # Check if delegate response is an error
                if delegate_response.startswith("ERROR:"):
                    logger.error(f"❌ GROUP CHAT MANAGER (MULTI-INPUT): {delegate_name} failed: {delegate_response}")
                    status['completed'] = True
                else:
                    logger.info(f"✅ GROUP CHAT MANAGER (MULTI-INPUT): {delegate_name} response added to conversation log")
                
                # Update iteration count
                status['iterations'] += 1
                total_iterations += 1
                logger.info(f"📊 GROUP CHAT MANAGER (MULTI-INPUT): {delegate_name} iteration count: {status['iterations']}/{status['max_iterations']}")
                
                # Check termination conditions - ONLY terminate if:
                # 1. Explicit termination condition is set AND appears at end of response, OR
                # 2. Maximum iterations reached
                termination_met = False
                
                # Check for explicit termination condition (only if one is set)
                if status['termination_condition'] and status['termination_condition'].strip():
                    # Only check at the END of the response to avoid false positives
                    if delegate_response.strip().endswith(status['termination_condition']):
                        termination_met = True
                        logger.info(f"✅ GROUP CHAT MANAGER (MULTI-INPUT): Delegate {delegate_name} used explicit termination: '{status['termination_condition']}'")
                
                # Check for max iterations reached
                if status['iterations'] >= status['max_iterations']:
                    termination_met = True
                    logger.info(f"✅ GROUP CHAT MANAGER (MULTI-INPUT): Delegate {delegate_name} reached max iterations: {status['iterations']}/{status['max_iterations']}")
                
                if termination_met:
                    status['completed'] = True
                    logger.info(f"✅ GROUP CHAT MANAGER (MULTI-INPUT): Delegate {delegate_name} completed")
                else:
                    logger.info(f"🔄 GROUP CHAT MANAGER (MULTI-INPUT): Delegate {delegate_name} continuing ({status['iterations']}/{status['max_iterations']})")
                
                # Check global termination strategy after each delegate
                try:
                    if self.check_termination_strategy(delegate_status, termination_strategy):
                        logger.info(f"🏁 GROUP CHAT MANAGER (MULTI-INPUT): Termination strategy '{termination_strategy}' triggered after {delegate_name}")
                        break
                except Exception as term_error:
                    logger.error(f"❌ GROUP CHAT MANAGER (MULTI-INPUT): Termination strategy check failed: {term_error}")
            
            logger.info(f"📊 GROUP CHAT MANAGER (MULTI-INPUT): Round {round_num + 1} completed - processed {delegates_processed_this_round} delegates")
            
            # Check if all delegates completed
            if delegates_processed_this_round == 0:
                all_completed = all(status['completed'] and status['iterations'] > 0 for status in delegate_status.values())
                if all_completed:
                    logger.info(f"✅ GROUP CHAT MANAGER (MULTI-INPUT): All delegates completed, ending execution")
                    break
                else:
                    logger.warning(f"⚠️ GROUP CHAT MANAGER (MULTI-INPUT): No delegates processed in round {round_num + 1} but not all complete - continuing")
            
            # Check global termination
            try:
                if self.check_termination_strategy(delegate_status, termination_strategy):
                    logger.info(f"🏁 GROUP CHAT MANAGER (MULTI-INPUT): Global termination after round {round_num + 1}")
                    break
            except Exception as term_error:
                logger.error(f"❌ GROUP CHAT MANAGER (MULTI-INPUT): Final termination check failed: {term_error}")
                break
        
        logger.info(f"📊 GROUP CHAT MANAGER (MULTI-INPUT): Execution loop completed after {max_rounds} rounds or early termination")
        
        # Ensure we have delegate conversations
        if not conversation_log:
            error_message = f"GroupChatManager {manager_name} with multiple inputs completed execution but no delegate conversations were generated. Check delegate configurations and API keys."
            logger.error(f"❌ GROUP CHAT MANAGER (MULTI-INPUT): {error_message}")
            raise Exception(error_message)
        
        # Generate final response from GroupChatManager with multi-input awareness
        final_prompt = f"""
        You are the Group Chat Manager named {manager_name}.
        
        You have processed multiple input sources and coordinated delegate responses.
        
        {formatted_context}
        
        Delegate Conversation Log:
        {"; ".join(conversation_log)}
        
        Based on the multiple input sources and delegate conversations, provide a comprehensive summary and final output.
        Focus on synthesizing insights from all inputs and delegate responses into actionable conclusions.
        Highlight how the different input sources contributed to the final result.
        """
        
        final_response = await llm_provider.generate_response(
            prompt=final_prompt,
            temperature=manager_data.get('temperature', 0.5)
        )
        
        if final_response.error:
            raise Exception(f"GroupChatManager multi-input final response error: {final_response.error}")
        
        final_output = f"""GroupChatManager Multi-Input Summary (processed {total_iterations} delegate iterations from {aggregated_context['input_count']} input sources):
        
        {final_response.text.strip()}
        
        Input Sources Summary:
        {aggregated_context['input_summary']}
        
        Delegate Processing Summary:
        {self.generate_delegate_summary(delegate_status)}
        """
        
        logger.info(f"✅ GROUP CHAT MANAGER (MULTI-INPUT): Completed execution with {total_iterations} total iterations from {aggregated_context['input_count']} inputs")
        
        # Return structured data for message logging
        return {
            'final_response': final_output,
            'delegate_conversations': conversation_log,
            'delegate_status': delegate_status,
            'total_iterations': total_iterations,
            'input_count': aggregated_context['input_count']
        }
    
    async def execute_delegate_conversation_with_multiple_inputs(self, delegate_node: Dict[str, Any], llm_provider, formatted_context: str, aggregated_context: Dict[str, Any], conversation_log: List[str], status: Dict[str, Any], project_id: Optional[str] = None) -> str:
        """
        Execute a single conversation round with a delegate agent using multiple inputs
        Enhanced version that handles multiple input sources and DocAware integration
        
        Args:
            delegate_node: The delegate node data
            llm_provider: LLM provider instance
            formatted_context: Formatted multi-input context string
            aggregated_context: Raw aggregated context data
            conversation_log: Previous delegate conversation log
            status: Delegate status tracking
            project_id: Project ID for DocAware functionality
        
        Returns:
            Delegate response string
        """
        delegate_name = delegate_node.get('data', {}).get('name', 'Delegate')
        delegate_data = delegate_node.get('data', {})
        
        logger.info(f"🤝 DELEGATE (MULTI-INPUT): Starting execution for {delegate_name}")
        logger.info(f"🤝 DELEGATE (MULTI-INPUT): Processing {aggregated_context['input_count']} input sources")
        logger.info(f"🤝 DELEGATE (MULTI-INPUT): DocAware enabled: {self.docaware_handler.is_docaware_enabled(delegate_node)}")
        
        # Create delegate-specific LLM provider if needed
        delegate_config = {
            'llm_provider': delegate_data.get('llm_provider', 'openai'),
            'llm_model': delegate_data.get('llm_model', 'gpt-4')
        }
        
        logger.info(f"🔧 DELEGATE (MULTI-INPUT): Config for {delegate_name}: {delegate_config}")
        
        # Try to create delegate-specific LLM provider with project context
        delegate_llm = None
        try:
            logger.info(f"🔧 DELEGATE (MULTI-INPUT): Attempting to create LLM provider for {delegate_name}")
            # Get project from project_id for API key resolution
            project = None
            if project_id:
                from users.models import IntelliDocProject
                from asgiref.sync import sync_to_async
                try:
                    project = await sync_to_async(IntelliDocProject.objects.get)(project_id=project_id)
                except IntelliDocProject.DoesNotExist:
                    logger.warning(f"⚠️ DELEGATE (MULTI-INPUT): Project {project_id} not found for {delegate_name}")
            
            delegate_llm = await self.llm_provider_manager.get_llm_provider(delegate_config, project)
            if delegate_llm:
                logger.info(f"✅ DELEGATE (MULTI-INPUT): Successfully created LLM provider for {delegate_name}")
            else:
                logger.warning(f"⚠️ DELEGATE (MULTI-INPUT): Failed to create LLM provider for {delegate_name}, trying fallback")
        except Exception as provider_error:
            logger.error(f"❌ DELEGATE (MULTI-INPUT): Error creating provider for {delegate_name}: {provider_error}")
        
        # Fallback to provided LLM provider
        if not delegate_llm:
            logger.info(f"🔄 DELEGATE (MULTI-INPUT): Using fallback LLM provider for {delegate_name}")
            delegate_llm = llm_provider
            
        if not delegate_llm:
            error_msg = f"No LLM provider available for delegate {delegate_name}"
            logger.error(f"❌ DELEGATE (MULTI-INPUT): {error_msg}")
            return f"ERROR: {error_msg}"
        
        # 📚 DOCAWARE INTEGRATION FOR DELEGATE AGENTS
        document_context = ""
        if self.docaware_handler.is_docaware_enabled(delegate_node) and project_id:
            try:
                # Use aggregated input as search query for DocAware
                search_query = self.docaware_handler.extract_search_query_from_aggregated_input(aggregated_context)
                
                if search_query:
                    logger.info(f"📚 DOCAWARE: Delegate {delegate_name} using aggregated input as search query")
                    logger.info(f"📚 DOCAWARE: Query: {search_query[:100]}...")
                    
                    document_context = await self.docaware_handler.get_docaware_context_from_query(
                        delegate_node, search_query, project_id, aggregated_context
                    )
                    
                    if document_context:
                        logger.info(f"📚 DOCAWARE: Added document context to delegate {delegate_name} prompt ({len(document_context)} chars)")
                else:
                    logger.warning(f"📚 DOCAWARE: No search query could be extracted from aggregated input for delegate {delegate_name}")
                    
            except Exception as e:
                logger.error(f"❌ DOCAWARE: Failed to get document context for delegate {delegate_name}: {e}")
                import traceback
                logger.error(f"❌ DOCAWARE: Traceback: {traceback.format_exc()}")
        
        # Craft enhanced delegate prompt with multiple inputs and optional DocAware context
        prompt_parts = []
        prompt_parts.append(f"You are {delegate_name}, a specialized delegate agent.")
        prompt_parts.append(f"")
        prompt_parts.append(f"System Message: {delegate_data.get('system_message', 'You are a helpful specialized agent.')}")
        
        # Add DocAware document context if available
        if document_context:
            prompt_parts.append("")
            prompt_parts.append("=== RELEVANT DOCUMENTS ===")
            prompt_parts.append(document_context)
            prompt_parts.append("=== END DOCUMENTS ===")
        
        prompt_parts.extend([
            f"",
            f"Multiple Input Context ({aggregated_context['input_count']} sources):",
            formatted_context,
            f"",
            f"Previous Delegate Conversations:",
            f"{'; '.join(conversation_log[-3:]) if conversation_log else 'None'}",
            f"",
            f"Current Iteration: {status['iterations'] + 1}/{status['max_iterations']}",
            f"",
            f"Instructions:",
            f"- Analyze and synthesize information from ALL input sources"
        ])
        
        if document_context:
            prompt_parts.append(f"- Use the relevant documents to provide accurate and contextual information")
            prompt_parts.append(f"- Reference specific information from the documents when applicable")
        
        prompt_parts.extend([
            f"- Provide specialized analysis based on your role and the multiple inputs",
            f"- Consider how different input sources relate to each other",
            f"- Be specific and actionable in your response",
            f"- If you have completed your analysis and want to terminate early, end your response with '{status['termination_condition']}'",
            f"- Consider the previous delegate conversations to avoid duplication",
            f"",
            f"Your response:"
        ])
        
        delegate_prompt = "\n".join(prompt_parts)
        
        logger.info(f"🤝 DELEGATE (MULTI-INPUT): Executing {delegate_name} iteration {status['iterations'] + 1}")
        logger.info(f"🤝 DELEGATE (MULTI-INPUT): About to call LLM with prompt length: {len(delegate_prompt)} chars")
        logger.info(f"🤝 DELEGATE (MULTI-INPUT): Using provider type: {type(delegate_llm).__name__}")
        
        try:
            logger.info(f"🤝 DELEGATE (MULTI-INPUT): About to call generate_response for {delegate_name}")
            
            delegate_response = await delegate_llm.generate_response(
                prompt=delegate_prompt
            )
            logger.info(f"🤝 DELEGATE (MULTI-INPUT): LLM call completed for {delegate_name}")
            logger.info(f"🤝 DELEGATE (MULTI-INPUT): Response type: {type(delegate_response)}")
            
            # Enhanced error checking
            if hasattr(delegate_response, 'error') and delegate_response.error:
                error_msg = f"Delegate {delegate_name} encountered an error: {delegate_response.error}"
                logger.error(f"❌ DELEGATE (MULTI-INPUT): {error_msg}")
                return f"ERROR: {error_msg}"
            
            # Check for text attribute
            if not hasattr(delegate_response, 'text'):
                error_msg = f"Delegate {delegate_name} response missing 'text' attribute. Response type: {type(delegate_response)}"
                logger.error(f"❌ DELEGATE (MULTI-INPUT): {error_msg}")
                return f"ERROR: {error_msg}"
            
            if not delegate_response.text:
                error_msg = f"Delegate {delegate_name} received empty response from LLM"
                logger.error(f"❌ DELEGATE (MULTI-INPUT): {error_msg}")
                return f"ERROR: {error_msg}"
            
            response_text = delegate_response.text.strip()
            logger.info(f"✅ DELEGATE (MULTI-INPUT): {delegate_name} generated response ({len(response_text)} chars)")
            
            # Log a preview of the response for debugging
            preview = response_text[:100] + "..." if len(response_text) > 100 else response_text
            logger.info(f"📝 DELEGATE (MULTI-INPUT): {delegate_name} response preview: {preview}")
            
            return response_text
            
        except Exception as e:
            error_msg = f"Delegate {delegate_name} execution failed: {str(e)}"
            logger.error(f"❌ DELEGATE (MULTI-INPUT): {error_msg}")
            logger.error(f"❌ DELEGATE (MULTI-INPUT): Exception type: {type(e).__name__}")
            import traceback
            logger.error(f"❌ DELEGATE (MULTI-INPUT): Traceback: {traceback.format_exc()}")
            return f"ERROR: {error_msg}"

    async def craft_conversation_prompt(self, conversation_history: str, agent_node: Dict[str, Any], project_id: Optional[str] = None) -> str:
        """
        Craft conversation prompt for an agent including full conversation history
        Enhanced with DocAware RAG capabilities
        """
        agent_name = agent_node.get('data', {}).get('name', 'Agent')
        agent_system_message = agent_node.get('data', {}).get('system_message', '')
        agent_instructions = agent_node.get('data', {}).get('instructions', '')
        
        # Build the prompt with conversation context
        prompt_parts = []
        
        # Add system message if available
        if agent_system_message:
            prompt_parts.append(f"System: {agent_system_message}")
        
        # Add agent-specific instructions
        if agent_instructions:
            prompt_parts.append(f"Instructions for {agent_name}: {agent_instructions}")
        
        # 📚 DOCAWARE INTEGRATION: Add document context if enabled (FIXED FOR SINGLE AGENTS)
        if self.docaware_handler.is_docaware_enabled(agent_node) and project_id:
            try:
                # Use conversation history as search query for single agents
                search_query = self.docaware_handler.extract_query_from_conversation(conversation_history)
                
                if search_query:
                    logger.info(f"📚 DOCAWARE: Single agent {agent_name} using conversation-based search query")
                    logger.info(f"📚 DOCAWARE: Query: {search_query[:100]}...")
                    
                    document_context = await self.docaware_handler.get_docaware_context_from_conversation_query(
                        agent_node, search_query, project_id, conversation_history
                    )
                    
                    if document_context:
                        prompt_parts.append("\n=== RELEVANT DOCUMENTS ===")
                        prompt_parts.append(document_context)
                        prompt_parts.append("=== END DOCUMENTS ===\n")
                        logger.info(f"📚 DOCAWARE: Added document context to single agent {agent_name} prompt ({len(document_context)} chars)")
                else:
                    logger.warning(f"📚 DOCAWARE: No search query could be extracted from conversation history for {agent_name}")
                    
            except Exception as e:
                logger.error(f"❌ DOCAWARE: Failed to get document context for single agent {agent_name}: {e}")
                import traceback
                logger.error(f"❌ DOCAWARE: Traceback: {traceback.format_exc()}")
        
        # Add conversation history
        if conversation_history.strip():
            prompt_parts.append("Conversation History:")
            prompt_parts.append(conversation_history)
        
        # Add agent prompt
        prompt_parts.append(f"\n{agent_name}, please provide your response:")
        
        return "\n".join(prompt_parts)
    
    async def craft_conversation_prompt_with_docaware(self, aggregated_context: Dict[str, Any], agent_node: Dict[str, Any], project_id: Optional[str] = None, conversation_history: str = "") -> str:
        """
        Enhanced conversation prompt crafting with DocAware using aggregated input as search query
        
        Args:
            aggregated_context: Output from aggregate_multiple_inputs containing all agent inputs
            agent_node: Agent node configuration
            project_id: Project ID for DocAware search
            conversation_history: Traditional conversation history (fallback)
        
        Returns:
            Enhanced prompt with document context from aggregated input search
        """
        agent_name = agent_node.get('data', {}).get('name', 'Agent')
        agent_system_message = agent_node.get('data', {}).get('system_message', '')
        agent_instructions = agent_node.get('data', {}).get('instructions', '')
        
        # Build the prompt with conversation context
        prompt_parts = []
        
        # Add system message if available
        if agent_system_message:
            prompt_parts.append(f"System: {agent_system_message}")
        
        # Add agent-specific instructions
        if agent_instructions:
            prompt_parts.append(f"Instructions for {agent_name}: {agent_instructions}")
        
        # 📚 ENHANCED DOCAWARE INTEGRATION: Use aggregated input as search query
        if self.docaware_handler.is_docaware_enabled(agent_node) and project_id:
            try:
                # Use aggregated input as search query instead of conversation history
                search_query = self.docaware_handler.extract_search_query_from_aggregated_input(aggregated_context)
                
                if search_query:
                    logger.info(f"📚 DOCAWARE: Using aggregated input as search query for {agent_name}")
                    logger.info(f"📚 DOCAWARE: Search query: {search_query[:100]}...")
                    
                    document_context = await self.docaware_handler.get_docaware_context_from_query(
                        agent_node, search_query, project_id, aggregated_context
                    )
                    
                    if document_context:
                        prompt_parts.append("\n=== RELEVANT DOCUMENTS ===")
                        prompt_parts.append(document_context)
                        prompt_parts.append("=== END DOCUMENTS ===\n")
                        logger.info(f"📚 DOCAWARE: Added document context to {agent_name} prompt ({len(document_context)} chars)")
                else:
                    logger.warning(f"📚 DOCAWARE: No search query could be extracted from aggregated input for {agent_name}")
                    
            except Exception as e:
                logger.error(f"❌ DOCAWARE: Failed to get document context for {agent_name}: {e}")
                import traceback
                logger.error(f"❌ DOCAWARE: Traceback: {traceback.format_exc()}")
        
        # Add aggregated input context
        if aggregated_context['input_count'] > 0:
            formatted_context = self.workflow_parser.format_multiple_inputs_prompt(aggregated_context)
            prompt_parts.append("=== INPUT FROM CONNECTED AGENTS ===")
            prompt_parts.append(formatted_context)
            prompt_parts.append("=== END INPUT ===")
        
        # Add conversation history if available (for context)
        if conversation_history.strip():
            prompt_parts.append("\n=== CONVERSATION HISTORY ===")
            prompt_parts.append(conversation_history)
            prompt_parts.append("=== END HISTORY ===")
        
        # Add agent prompt
        prompt_parts.append(f"\n{agent_name}, please analyze the inputs and provide your response:")
        
        return "\n".join(prompt_parts)
    
    async def execute_group_chat_manager(self, chat_manager_node: Dict[str, Any], llm_provider, conversation_history: str, execution_sequence: List[Dict[str, Any]], graph_json: Dict[str, Any]) -> str:
        """
        Execute GroupChatManager with delegate processing using enhanced logic
        """
        manager_name = chat_manager_node.get('data', {}).get('name', 'Chat Manager')
        manager_data = chat_manager_node.get('data', {})
        chat_manager_id = chat_manager_node.get('id')
        
        logger.info(f"👥 GROUP CHAT MANAGER: Starting enhanced execution for {manager_name}")
        
        # Find all delegate agents connected to this GroupChatManager by checking graph edges
        delegate_nodes = []
        edges = graph_json.get('edges', [])
        
        # Find all nodes that have incoming edges from this GroupChatManager
        connected_delegate_ids = set()
        for edge in edges:
            if edge.get('source') == chat_manager_id:
                target_id = edge.get('target')
                # Find the target node in execution sequence
                for node in execution_sequence:
                    if node.get('id') == target_id and node.get('type') == 'DelegateAgent':
                        connected_delegate_ids.add(target_id)
                        delegate_nodes.append(node)
                        logger.info(f"🔗 GROUP CHAT MANAGER: Found connected delegate: {node.get('data', {}).get('name', target_id)}")
        
        # Also check for edges going TO the GroupChatManager from delegates (bidirectional)
        for edge in edges:
            if edge.get('target') == chat_manager_id:
                source_id = edge.get('source')
                # Find the source node in execution sequence
                for node in execution_sequence:
                    if node.get('id') == source_id and node.get('type') == 'DelegateAgent' and source_id not in connected_delegate_ids:
                        connected_delegate_ids.add(source_id)
                        delegate_nodes.append(node)
                        logger.info(f"🔗 GROUP CHAT MANAGER: Found bidirectionally connected delegate: {node.get('data', {}).get('name', source_id)}")
        
        logger.info(f"🤝 GROUP CHAT MANAGER: Found {len(delegate_nodes)} connected delegate agents")
        
        # CRITICAL FIX: If no delegates found, return error instead of fake response
        if not delegate_nodes:
            error_message = f"GroupChatManager {manager_name} has no connected delegate agents. Please connect DelegateAgent nodes to this GroupChatManager via edges in the workflow graph."
            logger.error(f"❌ GROUP CHAT MANAGER: {error_message}")
            raise Exception(error_message)
        
        # Get configuration
        max_rounds = manager_data.get('max_rounds', 10)
        
        # Debug configuration values
        logger.info(f"🔧 GROUP CHAT MANAGER: Configuration - max_rounds: {max_rounds}")
        
        # Ensure max_rounds is at least 1
        if max_rounds <= 0:
            logger.warning(f"⚠️ GROUP CHAT MANAGER: max_rounds was {max_rounds}, setting to 1")
            max_rounds = 1
        termination_strategy = manager_data.get('termination_strategy', 'all_delegates_complete')
        
        # Initialize delegate tracking
        delegate_status = {}
        for delegate in delegate_nodes:
            delegate_name = delegate.get('data', {}).get('name', 'Delegate')
            delegate_status[delegate_name] = {
                'iterations': 0,
                'max_iterations': delegate.get('data', {}).get('number_of_iterations', 5),
                'termination_condition': delegate.get('data', {}).get('termination_condition', ''),  # NO DEFAULT - must come from UI
                'completed': False,
                'node': delegate
            }
        
        # Process delegates based on strategy
        conversation_log = []
        total_iterations = 0
        
        # Debug delegate status before execution
        logger.info(f"📊 GROUP CHAT MANAGER: Delegate status before execution: {delegate_status}")
        logger.info(f"📊 GROUP CHAT MANAGER: About to enter execution loop with max_rounds: {max_rounds}")
        
        # Execute all delegates at least once regardless of strategy
        logger.info(f"🔄 GROUP CHAT MANAGER: Starting execution loop with {len(delegate_nodes)} delegates")
        
        for round_num in range(max_rounds):
            logger.info(f"🔄 GROUP CHAT MANAGER: Round {round_num + 1}/{max_rounds}")
            
            # Track if any delegates were processed this round
            delegates_processed_this_round = 0
            
            for delegate_name, status in list(delegate_status.items()):
                logger.info(f"🔄 GROUP CHAT MANAGER: Checking delegate {delegate_name}, completed: {status['completed']}, iterations: {status['iterations']}/{status['max_iterations']}")
                
                # Only skip if both completed AND has run at least once
                if status['completed'] and status['iterations'] > 0:
                    logger.info(f"🔄 GROUP CHAT MANAGER: Skipping completed delegate {delegate_name}")
                    continue
                
                logger.info(f"🔄 GROUP CHAT MANAGER: About to execute delegate {delegate_name}")
                delegates_processed_this_round += 1
                
                # Execute delegate conversation
                try:
                    logger.info(f"📊 GROUP CHAT MANAGER: Calling execute_delegate_conversation for {delegate_name}")
                    delegate_response = await self.execute_delegate_conversation(
                        status['node'], 
                        llm_provider, 
                        conversation_history, 
                        conversation_log,
                        status
                    )
                    logger.info(f"✅ GROUP CHAT MANAGER: Successfully executed delegate {delegate_name} - response length: {len(delegate_response)} chars")
                    
                    # Ensure we have a valid response
                    if not delegate_response or len(delegate_response.strip()) == 0:
                        logger.warning(f"⚠️ GROUP CHAT MANAGER: {delegate_name} returned empty response, creating default")
                        delegate_response = f"I am {delegate_name} and I have processed the request. No specific output generated."
                        
                except Exception as delegate_exec_error:
                    logger.error(f"❌ GROUP CHAT MANAGER: Failed to execute delegate {delegate_name}: {delegate_exec_error}")
                    import traceback
                    logger.error(f"❌ GROUP CHAT MANAGER: Full traceback: {traceback.format_exc()}")
                    delegate_response = f"ERROR: Delegate execution failed: {delegate_exec_error}"
                
                # Always add response to conversation log
                conversation_log.append(f"[Round {round_num + 1}] {delegate_name}: {delegate_response}")
                
                # Check if delegate response is an error
                if delegate_response.startswith("ERROR:"):
                    logger.error(f"❌ GROUP CHAT MANAGER: {delegate_name} failed: {delegate_response}")
                    status['completed'] = True
                else:
                    logger.info(f"✅ GROUP CHAT MANAGER: {delegate_name} response added to conversation log")
                
                # Update iteration count
                status['iterations'] += 1
                total_iterations += 1
                logger.info(f"📊 GROUP CHAT MANAGER: {delegate_name} iteration count: {status['iterations']}/{status['max_iterations']}")
                
                # Check termination conditions - ONLY terminate if:
                # 1. Explicit termination condition is set AND appears at end of response, OR
                # 2. Maximum iterations reached
                termination_met = False
                
                # Check for explicit termination condition (only if one is set)
                if status['termination_condition'] and status['termination_condition'].strip():
                    # Only check at the END of the response to avoid false positives
                    if delegate_response.strip().endswith(status['termination_condition']):
                        termination_met = True
                        logger.info(f"✅ GROUP CHAT MANAGER: Delegate {delegate_name} used explicit termination: '{status['termination_condition']}'")
                
                # Check for max iterations reached
                if status['iterations'] >= status['max_iterations']:
                    termination_met = True
                    logger.info(f"✅ GROUP CHAT MANAGER: Delegate {delegate_name} reached max iterations: {status['iterations']}/{status['max_iterations']}")
                
                if termination_met:
                    status['completed'] = True
                    logger.info(f"✅ GROUP CHAT MANAGER: Delegate {delegate_name} completed")
                else:
                    logger.info(f"🔄 GROUP CHAT MANAGER: Delegate {delegate_name} continuing ({status['iterations']}/{status['max_iterations']})")
                
                # Check global termination strategy after each delegate
                try:
                    if self.check_termination_strategy(delegate_status, termination_strategy):
                        logger.info(f"🏁 GROUP CHAT MANAGER: Termination strategy '{termination_strategy}' triggered after {delegate_name}")
                        break
                except Exception as term_error:
                    logger.error(f"❌ GROUP CHAT MANAGER: Termination strategy check failed: {term_error}")
                    # Continue execution despite termination check failure
            
            logger.info(f"📊 GROUP CHAT MANAGER: Round {round_num + 1} completed - processed {delegates_processed_this_round} delegates")
            
            # If no delegates were processed this round, check if all are truly complete
            if delegates_processed_this_round == 0:
                all_completed = all(status['completed'] and status['iterations'] > 0 for status in delegate_status.values())
                if all_completed:
                    logger.info(f"✅ GROUP CHAT MANAGER: All delegates completed, ending execution")
                    break
                else:
                    logger.warning(f"⚠️ GROUP CHAT MANAGER: No delegates processed in round {round_num + 1} but not all complete - continuing")
            
            # Check global termination after processing all delegates in this round
            try:
                if self.check_termination_strategy(delegate_status, termination_strategy):
                    logger.info(f"🏁 GROUP CHAT MANAGER: Global termination after round {round_num + 1}")
                    break
            except Exception as term_error:
                logger.error(f"❌ GROUP CHAT MANAGER: Final termination check failed: {term_error}")
                break  # Exit to prevent infinite loop
        
        logger.info(f"📊 GROUP CHAT MANAGER: Execution loop completed after {max_rounds} rounds or early termination")
        
        # CRITICAL FIX: Ensure we actually have delegate conversations before generating summary
        if not conversation_log:
            error_message = f"GroupChatManager {manager_name} completed execution but no delegate conversations were generated. Check delegate configurations and API keys."
            logger.error(f"❌ GROUP CHAT MANAGER: {error_message}")
            logger.error(f"❌ GROUP CHAT MANAGER: Debug info - Delegate status: {delegate_status}")
            logger.error(f"❌ GROUP CHAT MANAGER: Debug info - Total iterations: {total_iterations}")
            logger.error(f"❌ GROUP CHAT MANAGER: Debug info - Max rounds: {max_rounds}")
            logger.error(f"❌ GROUP CHAT MANAGER: Debug info - Number of delegate nodes: {len(delegate_nodes)}")
            
            # Try to get more debug info about why delegates didn't execute
            for delegate_name, status in delegate_status.items():
                node_data = status['node'].get('data', {})
                logger.error(f"❌ GROUP CHAT MANAGER: Delegate {delegate_name} config: provider={node_data.get('llm_provider', 'unknown')}, model={node_data.get('llm_model', 'unknown')}")
            
            raise Exception(error_message)
        
        # Generate final response from GroupChatManager
        final_prompt = f"""
        You are the Group Chat Manager named {manager_name}.
        
        Original Conversation History:
        {conversation_history}
        
        Delegate Conversation Log:
        {"; ".join(conversation_log)}
        
        Based on the delegate conversations and original context, provide a comprehensive summary and final output.
        Focus on synthesizing the delegate insights into actionable conclusions.
        """
        
        final_response = await llm_provider.generate_response(
            prompt=final_prompt,
            temperature=manager_data.get('temperature', 0.5)
        )
        
        if final_response.error:
            raise Exception(f"GroupChatManager final response error: {final_response.error}")
        
        final_output = f"""GroupChatManager Summary (processed {total_iterations} delegate iterations):
        
        {final_response.text.strip()}
        
        Delegate Processing Summary:
        {self.generate_delegate_summary(delegate_status)}
        """
        
        logger.info(f"✅ GROUP CHAT MANAGER: Completed execution with {total_iterations} total iterations")
        
        # Return structured data for message logging
        return {
            'final_response': final_output,
            'delegate_conversations': conversation_log,
            'delegate_status': delegate_status,
            'total_iterations': total_iterations,
            'input_count': 1
        }
    
    async def execute_delegate_conversation(self, delegate_node: Dict[str, Any], llm_provider, conversation_history: str, conversation_log: List[str], status: Dict[str, Any]) -> str:
        """
        Execute a single conversation round with a delegate agent
        """
        delegate_name = delegate_node.get('data', {}).get('name', 'Delegate')
        delegate_data = delegate_node.get('data', {})
        
        logger.info(f"🤝 DELEGATE: Starting execution for {delegate_name}")
        logger.info(f"🤝 DELEGATE: Delegate data keys: {list(delegate_data.keys())}")
        
        # Create delegate-specific LLM provider if needed
        delegate_config = {
            'llm_provider': delegate_data.get('llm_provider', 'openai'),  # Changed default to openai
            'llm_model': delegate_data.get('llm_model', 'gpt-4')  # Use gpt-4 by default
        }
        
        logger.info(f"🔧 DELEGATE: Config for {delegate_name}: {delegate_config}")
        
        # Try to create delegate-specific LLM provider with modern async method
        delegate_llm = None
        try:
            logger.info(f"🔧 DELEGATE: Attempting to create LLM provider for {delegate_name}")
            # Use modern async method with project support (same as AssistantAgent)
            # Note: This legacy method doesn't have project context, so passing None
            delegate_llm = await self.llm_provider_manager.get_llm_provider(delegate_config, None)
            if delegate_llm:
                logger.info(f"✅ DELEGATE: Successfully created LLM provider for {delegate_name}")
            else:
                logger.warning(f"⚠️ DELEGATE: Failed to create LLM provider for {delegate_name}, trying fallback")
        except Exception as provider_error:
            logger.error(f"❌ DELEGATE: Error creating provider for {delegate_name}: {provider_error}")
        
        # Fallback to provided LLM provider
        if not delegate_llm:
            logger.info(f"🔄 DELEGATE: Using fallback LLM provider for {delegate_name}")
            delegate_llm = llm_provider
            
        if not delegate_llm:
            error_msg = f"No LLM provider available for delegate {delegate_name}"
            logger.error(f"❌ DELEGATE: {error_msg}")
            return f"ERROR: {error_msg}"
        
        # Craft delegate prompt
        delegate_prompt = f"""
        You are {delegate_name}, a specialized delegate agent.
        
        System Message: {delegate_data.get('system_message', 'You are a helpful specialized agent.')}
        
        Original Task Context:
        {conversation_history}
        
        Previous Delegate Conversations:
        {"; ".join(conversation_log[-3:]) if conversation_log else "None"}
        
        Current Iteration: {status['iterations'] + 1}/{status['max_iterations']}
        
        Instructions:
        - Provide specialized analysis or assistance based on your role
        - Be specific and actionable in your response
        - If you have completed your analysis and want to terminate early, end your response with "{status['termination_condition']}"
        - Consider the previous delegate conversations to avoid duplication
        
        Your response:
        """
        
        logger.info(f"🤝 DELEGATE: Executing {delegate_name} iteration {status['iterations'] + 1}")
        logger.info(f"🤝 DELEGATE: About to call LLM with prompt length: {len(delegate_prompt)} chars")
        logger.info(f"🤝 DELEGATE: Using provider type: {type(delegate_llm).__name__}")
        
        try:
            logger.info(f"🤝 DELEGATE: About to call generate_response for {delegate_name}")
            
            # Add debugging for the actual API call
            logger.info(f"🤝 DELEGATE: API Key available: {bool(delegate_llm)}")
            
            delegate_response = await delegate_llm.generate_response(
                prompt=delegate_prompt
            )
            logger.info(f"🤝 DELEGATE: LLM call completed for {delegate_name}")
            logger.info(f"🤝 DELEGATE: Response type: {type(delegate_response)}")
            
            # Enhanced error checking
            if hasattr(delegate_response, 'error') and delegate_response.error:
                error_msg = f"Delegate {delegate_name} encountered an error: {delegate_response.error}"
                logger.error(f"❌ DELEGATE: {error_msg}")
                return f"ERROR: {error_msg}"
            
            # Check for text attribute
            if not hasattr(delegate_response, 'text'):
                error_msg = f"Delegate {delegate_name} response missing 'text' attribute. Response type: {type(delegate_response)}"
                logger.error(f"❌ DELEGATE: {error_msg}")
                return f"ERROR: {error_msg}"
            
            if not delegate_response.text:
                error_msg = f"Delegate {delegate_name} received empty response from LLM"
                logger.error(f"❌ DELEGATE: {error_msg}")
                return f"ERROR: {error_msg}"
            
            response_text = delegate_response.text.strip()
            logger.info(f"✅ DELEGATE: {delegate_name} generated response ({len(response_text)} chars)")
            
            # Log a preview of the response for debugging
            preview = response_text[:100] + "..." if len(response_text) > 100 else response_text
            logger.info(f"📝 DELEGATE: {delegate_name} response preview: {preview}")
            
            return response_text
            
        except Exception as e:
            error_msg = f"Delegate {delegate_name} execution failed: {str(e)}"
            logger.error(f"❌ DELEGATE: {error_msg}")
            logger.error(f"❌ DELEGATE: Exception type: {type(e).__name__}")
            import traceback
            logger.error(f"❌ DELEGATE: Traceback: {traceback.format_exc()}")
            return f"ERROR: {error_msg}"

    def check_termination_strategy(self, delegate_status: Dict[str, Dict], strategy: str) -> bool:
        """
        Check if termination strategy conditions are met
        """
        if strategy == 'all_delegates_complete':
            return all(status['completed'] for status in delegate_status.values())
        elif strategy == 'any_delegate_complete':
            return any(status['completed'] for status in delegate_status.values())
        else:
            logger.warning(f"⚠️ Unknown termination strategy: {strategy}, defaulting to all_delegates_complete")
            return all(status['completed'] for status in delegate_status.values())
    
    def generate_delegate_summary(self, delegate_status: Dict[str, Dict]) -> str:
        """
        Generate summary of delegate processing status
        """
        summary_parts = []
        for delegate_name, status in delegate_status.items():
            summary_parts.append(f"- {delegate_name}: {status['iterations']}/{status['max_iterations']} iterations, completed: {status['completed']}")
        return "\n".join(summary_parts)