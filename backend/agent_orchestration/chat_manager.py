"""
Chat Manager
============

Handles group chat management and delegate conversation execution for conversation orchestration.
"""

import logging
import asyncio
from typing import Dict, List, Any, Optional
from asgiref.sync import sync_to_async

from .query_analysis_service import get_query_analysis_service
from .message_protocol import DelegationMessageProtocol, MessageType

logger = logging.getLogger('conversation_orchestrator')


class ChatManager:
    """
    Manages group chat orchestration and delegate conversations
    """
    
    def __init__(self, llm_provider_manager, workflow_parser, docaware_handler):
        self.llm_provider_manager = llm_provider_manager
        self.workflow_parser = workflow_parser
        self.docaware_handler = docaware_handler
    
    async def execute_group_chat_manager_with_multiple_inputs(self, chat_manager_node: Dict[str, Any], llm_provider, input_sources: List[Dict[str, Any]], executed_nodes: Dict[str, str], execution_sequence: List[Dict[str, Any]], graph_json: Dict[str, Any], project_id: Optional[str] = None, project: Optional[Any] = None) -> Dict[str, Any]:
        """
        Execute GroupChatManager with multiple inputs support
        Enhanced version that handles multiple input sources
        
        Supports both round-robin and intelligent delegation modes.
        
        Args:
            chat_manager_node: The GroupChatManager node data
            llm_provider: LLM provider instance
            input_sources: List of input node metadata
            executed_nodes: Dict mapping node_id to their outputs
            execution_sequence: Complete workflow execution sequence
            graph_json: Full workflow graph data
            project_id: Project ID for DocAware functionality
            project: Project instance for API keys (optional)
        
        Returns:
            Dict with final_response, delegate_conversations, delegate_status, total_iterations, etc.
        """
        manager_name = chat_manager_node.get('data', {}).get('name', 'Chat Manager')
        manager_data = chat_manager_node.get('data', {})
        chat_manager_id = chat_manager_node.get('id')
        
        logger.info(f"👥 GROUP CHAT MANAGER (MULTI-INPUT): Starting enhanced execution for {manager_name}")
        logger.info(f"📥 GROUP CHAT MANAGER (MULTI-INPUT): Processing {len(input_sources)} input sources")
        
        # Check delegation mode
        delegation_mode = manager_data.get('delegation_mode', 'round_robin')
        logger.info(f"🔧 GROUP CHAT MANAGER (MULTI-INPUT): Delegation mode: {delegation_mode}")
        
        # Route to intelligent delegation if enabled
        if delegation_mode == 'intelligent':
            try:
                # Get project for API keys if not provided
                if project is None and project_id:
                    from users.models import IntelliDocProject
                    from asgiref.sync import sync_to_async
                    try:
                        project = await sync_to_async(IntelliDocProject.objects.get)(project_id=project_id)
                    except IntelliDocProject.DoesNotExist:
                        logger.warning(f"⚠️ GROUP CHAT MANAGER (MULTI-INPUT): Project {project_id} not found")
                
                logger.info(f"🧠 GROUP CHAT MANAGER (MULTI-INPUT): Using intelligent delegation mode")
                return await self.execute_group_chat_manager_intelligent_delegation(
                    chat_manager_node=chat_manager_node,
                    llm_provider=llm_provider,
                    input_sources=input_sources,
                    executed_nodes=executed_nodes,
                    execution_sequence=execution_sequence,
                    graph_json=graph_json,
                    project_id=project_id,
                    project=project
                )
            except Exception as e:
                logger.error(f"❌ GROUP CHAT MANAGER (MULTI-INPUT): Intelligent delegation failed, falling back to round-robin: {e}")
                import traceback
                logger.error(f"❌ GROUP CHAT MANAGER (MULTI-INPUT): Traceback: {traceback.format_exc()}")
                # Fall through to round-robin mode
        
        # Default: round-robin mode (existing behavior)
        logger.info(f"🔄 GROUP CHAT MANAGER (MULTI-INPUT): Using round-robin delegation mode")
        
        # PARALLELIZE: Aggregate inputs and discover delegates simultaneously (independent operations)
        async def aggregate_inputs():
            return self.workflow_parser.aggregate_multiple_inputs(input_sources, executed_nodes)
        
        async def discover_delegates():
            # Find all delegate agents connected to this GroupChatManager
            # CRITICAL: Search in full graph_json, not just execution_sequence, because delegates
            # are excluded from the main execution sequence when connected via 'delegate' edges
            delegate_nodes = []
            edges = graph_json.get('edges', [])
            all_nodes = graph_json.get('nodes', [])  # Use full node list, not just execution_sequence
            
            connected_delegate_ids = set()
            for edge in edges:
                # Only consider delegate-type edges
                if edge.get('type') == 'delegate' and edge.get('source') == chat_manager_id:
                    target_id = edge.get('target')
                    # Find delegate in full graph, not just execution sequence
                    for node in all_nodes:
                        if node.get('id') == target_id and node.get('type') == 'DelegateAgent':
                            connected_delegate_ids.add(target_id)
                            delegate_nodes.append(node)
                            logger.info(f"🔗 GROUP CHAT MANAGER (MULTI-INPUT): Found connected delegate via delegate edge: {node.get('data', {}).get('name', target_id)}")
            
            # Also check bidirectional delegate edges (delegate -> GroupChatManager)
            for edge in edges:
                if edge.get('type') == 'delegate' and edge.get('target') == chat_manager_id:
                    source_id = edge.get('source')
                    # Find delegate in full graph, not just execution sequence
                    for node in all_nodes:
                        if node.get('id') == source_id and node.get('type') == 'DelegateAgent' and source_id not in connected_delegate_ids:
                            connected_delegate_ids.add(source_id)
                            delegate_nodes.append(node)
                            logger.info(f"🔗 GROUP CHAT MANAGER (MULTI-INPUT): Found bidirectionally connected delegate via delegate edge: {node.get('data', {}).get('name', source_id)}")
            
            logger.info(f"🤝 GROUP CHAT MANAGER (MULTI-INPUT): Found {len(delegate_nodes)} connected delegate agents")
            return delegate_nodes
        
        # Execute aggregation and discovery in parallel
        logger.info(f"🚀 GROUP CHAT MANAGER (MULTI-INPUT): Executing input aggregation and delegate discovery in parallel")
        aggregated_context, delegate_nodes = await asyncio.gather(
            aggregate_inputs(),
            discover_delegates()
        )
        formatted_context = self.workflow_parser.format_multiple_inputs_prompt(aggregated_context)
        
        if not delegate_nodes:
            error_message = f"GroupChatManager {manager_name} has no connected delegate agents. Please connect DelegateAgent nodes to this GroupChatManager via edges in the workflow graph."
            logger.error(f"❌ GROUP CHAT MANAGER (MULTI-INPUT): {error_message}")
            raise Exception(error_message)
        
        # Get configuration
        # For Round Robin, use max_iterations if available, otherwise fallback to max_rounds
        max_iterations = manager_data.get('max_iterations', None)
        if max_iterations is None:
            # Fallback to max_rounds for backward compatibility
            max_rounds = manager_data.get('max_rounds', 10)
            if max_rounds <= 0:
                logger.warning(f"⚠️ GROUP CHAT MANAGER (MULTI-INPUT): max_rounds was {max_rounds}, setting to 1")
                max_rounds = 1
            max_iterations = max_rounds
        else:
            # Use max_iterations from config
            if max_iterations <= 0:
                logger.warning(f"⚠️ GROUP CHAT MANAGER (MULTI-INPUT): max_iterations was {max_iterations}, setting to 2 (default)")
                max_iterations = 2
            max_rounds = max_iterations  # Use max_iterations as max_rounds for the loop
        
        termination_strategy = manager_data.get('termination_strategy', 'all_delegates_complete')
        
        logger.info(f"🔧 GROUP CHAT MANAGER (MULTI-INPUT): Configuration - max_iterations: {max_iterations}, max_rounds: {max_rounds}, inputs: {aggregated_context['input_count']}")
        
        # Initialize delegate tracking
        # Use max_iterations to control how many times each delegate executes in Round Robin mode
        delegate_status = {}
        for delegate in delegate_nodes:
            delegate_name = delegate.get('data', {}).get('name', 'Delegate')
            delegate_status[delegate_name] = {
                'iterations': 0,
                'max_iterations': max_iterations,  # Use max_iterations for Round Robin mode
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
            
            # PARALLELIZE: Create parallel tasks for all delegates in this round
            round_tasks = []
            for delegate_name, status in list(delegate_status.items()):
                logger.info(f"🔄 GROUP CHAT MANAGER (MULTI-INPUT): Checking delegate {delegate_name}, completed: {status['completed']}, iterations: {status['iterations']}/{status['max_iterations']}")
                
                # Only skip if both completed AND has run at least once
                if status['completed'] and status['iterations'] > 0:
                    logger.info(f"🔄 GROUP CHAT MANAGER (MULTI-INPUT): Skipping completed delegate {delegate_name}")
                    continue
                
                logger.info(f"🔄 GROUP CHAT MANAGER (MULTI-INPUT): About to execute delegate {delegate_name}")
                
                # Create async task for delegate execution (don't await yet)
                task = self.execute_delegate_conversation_with_multiple_inputs(
                    status['node'], 
                    llm_provider, 
                    formatted_context,  # Use multi-input formatted context
                    aggregated_context,  # Pass raw context for metadata
                    conversation_log,
                    status,
                    project_id  # Add project_id for DocAware functionality
                )
                round_tasks.append((delegate_name, status, task))
            
            # Execute all delegates in this round in parallel
            if round_tasks:
                logger.info(f"🚀 GROUP CHAT MANAGER (MULTI-INPUT): Executing {len(round_tasks)} delegates in parallel for round {round_num + 1}")
                round_results = await asyncio.gather(
                    *[task for _, _, task in round_tasks],
                    return_exceptions=True
                )
                
                # Process results from parallel execution
                for (delegate_name, status, _), delegate_response in zip(round_tasks, round_results):
                    try:
                        # Handle exceptions from parallel execution
                        if isinstance(delegate_response, Exception):
                            logger.error(f"❌ GROUP CHAT MANAGER (MULTI-INPUT): Exception executing delegate {delegate_name}: {delegate_response}")
                            import traceback
                            logger.error(f"❌ GROUP CHAT MANAGER (MULTI-INPUT): Full traceback: {traceback.format_exc()}")
                            delegate_response = f"ERROR: Delegate execution failed: {delegate_response}"
                        else:
                            logger.info(f"✅ GROUP CHAT MANAGER (MULTI-INPUT): Successfully executed delegate {delegate_name} - response length: {len(delegate_response)} chars")
                        
                        # Ensure we have a valid response
                        if not delegate_response or len(delegate_response.strip()) == 0:
                            logger.warning(f"⚠️ GROUP CHAT MANAGER (MULTI-INPUT): {delegate_name} returned empty response, creating default")
                            delegate_response = f"I am {delegate_name} and I have processed the multiple input sources. No specific output generated."
                        
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
                    except Exception as process_error:
                        logger.error(f"❌ GROUP CHAT MANAGER (MULTI-INPUT): Error processing result for {delegate_name}: {process_error}")
                        import traceback
                        logger.error(f"❌ GROUP CHAT MANAGER (MULTI-INPUT): Traceback: {traceback.format_exc()}")
                        # Mark as completed to prevent infinite loops
                        status['completed'] = True
                        conversation_log.append(f"[Round {round_num + 1}] {delegate_name}: ERROR: Failed to process result")
                
                # Check global termination strategy after all delegates in round complete
                try:
                    if self.check_termination_strategy(delegate_status, termination_strategy):
                        logger.info(f"🏁 GROUP CHAT MANAGER (MULTI-INPUT): Termination strategy '{termination_strategy}' triggered after round {round_num + 1}")
                        break
                except Exception as term_error:
                    logger.error(f"❌ GROUP CHAT MANAGER (MULTI-INPUT): Termination strategy check failed: {term_error}")
                
                logger.info(f"📊 GROUP CHAT MANAGER (MULTI-INPUT): Round {round_num + 1} completed - processed {len(round_tasks)} delegates in parallel")
            else:
                logger.info(f"📊 GROUP CHAT MANAGER (MULTI-INPUT): Round {round_num + 1} skipped - no delegates to execute")
            
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
            # Enhanced diagnostic logging before LLM call
            logger.info(f"🔍 DELEGATE DEBUG: About to call LLM for {delegate_name}")
            logger.info(f"🔍 DELEGATE DEBUG: Provider type: {type(delegate_llm).__name__}")
            logger.info(f"🔍 DELEGATE DEBUG: Has generate_response method: {hasattr(delegate_llm, 'generate_response')}")
            logger.info(f"🔍 DELEGATE DEBUG: LLM Model: {delegate_config.get('llm_model', 'unknown')}")
            logger.info(f"🔍 DELEGATE DEBUG: Temperature: {delegate_config.get('temperature', 0.4)}")
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
                logger.error(f"❌ DELEGATE (MULTI-INPUT): LLM Provider: {type(delegate_llm).__name__}")
                logger.error(f"❌ DELEGATE (MULTI-INPUT): Model: {delegate_config.get('llm_model', 'unknown')}")
                return f"ERROR: {error_msg}"

            # Check for text attribute
            if not hasattr(delegate_response, 'text'):
                error_msg = f"Delegate {delegate_name} response missing 'text' attribute. Response type: {type(delegate_response)}"
                logger.error(f"❌ DELEGATE (MULTI-INPUT): {error_msg}")
                logger.error(f"❌ DELEGATE (MULTI-INPUT): Response object type: {type(delegate_response)}")
                logger.error(f"❌ DELEGATE (MULTI-INPUT): Response attributes: {dir(delegate_response)}")
                logger.error(f"❌ DELEGATE (MULTI-INPUT): LLM Provider: {type(delegate_llm).__name__}")
                logger.error(f"❌ DELEGATE (MULTI-INPUT): Model: {delegate_config.get('llm_model', 'unknown')}")
                return f"ERROR: {error_msg}"

            if not delegate_response.text:
                error_msg = f"Delegate {delegate_name} received empty response from LLM"
                logger.error(f"❌ DELEGATE (MULTI-INPUT): {error_msg}")
                logger.error(f"❌ DELEGATE (MULTI-INPUT): Response object type: {type(delegate_response)}")
                logger.error(f"❌ DELEGATE (MULTI-INPUT): Response attributes: {dir(delegate_response)}")
                logger.error(f"❌ DELEGATE (MULTI-INPUT): Response error attribute: {getattr(delegate_response, 'error', 'N/A')}")
                logger.error(f"❌ DELEGATE (MULTI-INPUT): LLM Provider: {type(delegate_llm).__name__}")
                logger.error(f"❌ DELEGATE (MULTI-INPUT): Model: {delegate_config.get('llm_model', 'unknown')}")
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
        
        # Check delegation mode (for single-input mode)
        delegation_mode = manager_data.get('delegation_mode', 'round_robin')
        logger.info(f"🔧 GROUP CHAT MANAGER: Delegation mode: {delegation_mode}")
        
        # Note: Intelligent delegation requires multiple inputs for best results
        # For single input, we'll use round-robin by default
        if delegation_mode == 'intelligent':
            logger.warning(f"⚠️ GROUP CHAT MANAGER: Intelligent delegation works best with multiple inputs. Using round-robin for single input.")
            # Could implement intelligent delegation for single input if needed
        
        # Find all delegate agents connected to this GroupChatManager by checking graph edges
        # CRITICAL: Search in full graph_json, not just execution_sequence, because delegates
        # are excluded from the main execution sequence when connected via 'delegate' edges
        delegate_nodes = []
        edges = graph_json.get('edges', [])
        all_nodes = graph_json.get('nodes', [])  # Use full node list, not just execution_sequence
        
        connected_delegate_ids = set()
        for edge in edges:
            # Only consider delegate-type edges
            if edge.get('type') == 'delegate' and edge.get('source') == chat_manager_id:
                target_id = edge.get('target')
                # Find delegate in full graph, not just execution sequence
                for node in all_nodes:
                    if node.get('id') == target_id and node.get('type') == 'DelegateAgent':
                        connected_delegate_ids.add(target_id)
                        delegate_nodes.append(node)
                        logger.info(f"🔗 GROUP CHAT MANAGER: Found connected delegate via delegate edge: {node.get('data', {}).get('name', target_id)}")
        
        # Also check bidirectional delegate edges (delegate -> GroupChatManager)
        for edge in edges:
            if edge.get('type') == 'delegate' and edge.get('target') == chat_manager_id:
                source_id = edge.get('source')
                # Find delegate in full graph, not just execution sequence
                for node in all_nodes:
                    if node.get('id') == source_id and node.get('type') == 'DelegateAgent' and source_id not in connected_delegate_ids:
                        connected_delegate_ids.add(source_id)
                        delegate_nodes.append(node)
                        logger.info(f"🔗 GROUP CHAT MANAGER: Found bidirectionally connected delegate via delegate edge: {node.get('data', {}).get('name', source_id)}")
        
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
        # Use Group Chat Manager's max_rounds to control delegate iterations
        delegate_status = {}
        for delegate in delegate_nodes:
            delegate_name = delegate.get('data', {}).get('name', 'Delegate')
            delegate_status[delegate_name] = {
                'iterations': 0,
                'max_iterations': max_rounds,  # Use Group Chat Manager's max_rounds instead of delegate's number_of_iterations
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
    
    async def execute_group_chat_manager_intelligent_delegation(
        self,
        chat_manager_node: Dict[str, Any],
        llm_provider,
        input_sources: List[Dict[str, Any]],
        executed_nodes: Dict[str, str],
        execution_sequence: List[Dict[str, Any]],
        graph_json: Dict[str, Any],
        project_id: Optional[str] = None,
        project: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Execute GroupChatManager with intelligent task delegation
        
        Analyzes input, splits into subqueries, and routes to appropriate delegates
        based on their capabilities.
        
        Args:
            chat_manager_node: The GroupChatManager node data
            llm_provider: LLM provider instance
            input_sources: List of input node metadata
            executed_nodes: Dict mapping node_id to their outputs
            execution_sequence: Complete workflow execution sequence
            graph_json: Full workflow graph data
            project_id: Project ID for DocAware functionality
            project: Project instance for API keys
            
        Returns:
            Dict with final_response, delegate_conversations, delegate_status, etc.
        """
        manager_name = chat_manager_node.get('data', {}).get('name', 'Chat Manager')
        manager_data = chat_manager_node.get('data', {})
        chat_manager_id = chat_manager_node.get('id')
        
        logger.info(f"🧠 GROUP CHAT MANAGER (INTELLIGENT): Starting intelligent delegation for {manager_name}")
        logger.info(f"📥 GROUP CHAT MANAGER (INTELLIGENT): Processing {len(input_sources)} input sources")
        
        # Get project for API keys if not provided (required for all agents)
        if project is None and project_id:
            from users.models import IntelliDocProject
            from asgiref.sync import sync_to_async
            try:
                project = await sync_to_async(IntelliDocProject.objects.get)(project_id=project_id)
                logger.info(f"✅ GROUP CHAT MANAGER (INTELLIGENT): Retrieved project {project.name} for delegate API keys")
            except IntelliDocProject.DoesNotExist:
                logger.error(f"❌ GROUP CHAT MANAGER (INTELLIGENT): Project {project_id} not found - delegates require project-specific API keys")
            except Exception as e:
                logger.error(f"❌ GROUP CHAT MANAGER (INTELLIGENT): Error retrieving project {project_id}: {e}")
        
        if project:
            logger.info(f"🔑 GROUP CHAT MANAGER (INTELLIGENT): Using project {project.name} for delegate API keys")
        else:
            logger.error(f"❌ GROUP CHAT MANAGER (INTELLIGENT): No project available - delegates require project-specific API keys")
        
        # Get configuration
        confidence_threshold = manager_data.get('delegation_confidence_threshold', 0.7)
        delegation_timeout = manager_data.get('delegation_timeout', 30)  # seconds
        max_retries = manager_data.get('max_delegation_retries', 3)
        
        # Force max_rounds to 1 for intelligent delegation (single-pass delegation)
        max_rounds = 1
        logger.info(f"🧠 GROUP CHAT MANAGER (INTELLIGENT): Using hardcoded max_rounds=1 for intelligent delegation")
        
        # Ensure termination strategy is 'all_delegates_complete' for intelligent delegation
        termination_strategy = manager_data.get('termination_strategy', 'all_delegates_complete')
        if termination_strategy != 'all_delegates_complete':
            logger.info(f"🧠 GROUP CHAT MANAGER (INTELLIGENT): Overriding termination_strategy to 'all_delegates_complete' (was: {termination_strategy})")
            termination_strategy = 'all_delegates_complete'
        
        # PARALLELIZE: Aggregate inputs and discover delegates simultaneously (independent operations)
        async def aggregate_inputs():
            return self.workflow_parser.aggregate_multiple_inputs(input_sources, executed_nodes)
        
        async def discover_delegates():
            # Find all delegate agents connected to this GroupChatManager
            # CRITICAL: Search in full graph_json, not just execution_sequence, because delegates
            # are excluded from the main execution sequence when connected via 'delegate' edges
            delegate_nodes = []
            edges = graph_json.get('edges', [])
            all_nodes = graph_json.get('nodes', [])  # Use full node list, not just execution_sequence
            
            connected_delegate_ids = set()
            for edge in edges:
                # Only consider delegate-type edges
                if edge.get('type') == 'delegate' and edge.get('source') == chat_manager_id:
                    target_id = edge.get('target')
                    # Find delegate in full graph, not just execution sequence
                    for node in all_nodes:
                        if node.get('id') == target_id and node.get('type') == 'DelegateAgent':
                            connected_delegate_ids.add(target_id)
                            delegate_nodes.append(node)
                            logger.info(f"🔗 GROUP CHAT MANAGER (INTELLIGENT): Found connected delegate via delegate edge: {node.get('data', {}).get('name', target_id)}")
            
            # Also check bidirectional delegate edges (delegate -> GroupChatManager)
            for edge in edges:
                if edge.get('type') == 'delegate' and edge.get('target') == chat_manager_id:
                    source_id = edge.get('source')
                    # Find delegate in full graph, not just execution sequence
                    for node in all_nodes:
                        if node.get('id') == source_id and node.get('type') == 'DelegateAgent' and source_id not in connected_delegate_ids:
                            connected_delegate_ids.add(source_id)
                            delegate_nodes.append(node)
                            logger.info(f"🔗 GROUP CHAT MANAGER (INTELLIGENT): Found bidirectionally connected delegate via delegate edge: {node.get('data', {}).get('name', source_id)}")
            
            logger.info(f"🤝 GROUP CHAT MANAGER (INTELLIGENT): Found {len(delegate_nodes)} connected delegate agents")
            return delegate_nodes
        
        # Execute aggregation and discovery in parallel
        logger.info(f"🚀 GROUP CHAT MANAGER (INTELLIGENT): Executing input aggregation and delegate discovery in parallel")
        aggregated_context, delegate_nodes = await asyncio.gather(
            aggregate_inputs(),
            discover_delegates()
        )
        formatted_context = self.workflow_parser.format_multiple_inputs_prompt(aggregated_context)
        
        # Get the original input text for query analysis
        input_text = formatted_context
        if aggregated_context.get('input_summary'):
            input_text = aggregated_context['input_summary']
        elif aggregated_context.get('combined_text'):
            input_text = aggregated_context['combined_text']
        
        if not delegate_nodes:
            error_message = f"GroupChatManager {manager_name} has no connected delegate agents. Please connect DelegateAgent nodes to this GroupChatManager via edges in the workflow graph."
            logger.error(f"❌ GROUP CHAT MANAGER (INTELLIGENT): {error_message}")
            raise Exception(error_message)
        
        # Extract delegate descriptions
        delegate_descriptions = {}
        delegate_name_to_node = {}
        for delegate_node in delegate_nodes:
            delegate_name = delegate_node.get('data', {}).get('name', 'Delegate')
            delegate_description = delegate_node.get('data', {}).get('description', '')
            if not delegate_description:
                delegate_description = delegate_node.get('data', {}).get('system_message', '')
            if not delegate_description:
                delegate_description = f"{delegate_name} is a specialized delegate agent."
            
            delegate_descriptions[delegate_name] = delegate_description
            delegate_name_to_node[delegate_name] = delegate_node
            logger.info(f"📋 GROUP CHAT MANAGER (INTELLIGENT): Delegate {delegate_name}: {delegate_description[:100]}...")
        
        # Initialize query analysis service
        query_analysis_service = get_query_analysis_service(self.llm_provider_manager)
        
        # Step 1: Analyze and split query
        logger.info(f"🔍 GROUP CHAT MANAGER (INTELLIGENT): Analyzing and splitting input query")
        
        # Get max_subqueries from manager configuration (default: None = no limit)
        max_subqueries = manager_data.get('max_subqueries', None)
        if max_subqueries is not None:
            try:
                max_subqueries = int(max_subqueries)
                if max_subqueries <= 0:
                    logger.warning(f"⚠️ GROUP CHAT MANAGER (INTELLIGENT): Invalid max_subqueries value {max_subqueries}, ignoring limit")
                    max_subqueries = None
                else:
                    logger.info(f"📊 GROUP CHAT MANAGER (INTELLIGENT): Max subqueries limit set to {max_subqueries}")
            except (ValueError, TypeError):
                logger.warning(f"⚠️ GROUP CHAT MANAGER (INTELLIGENT): Invalid max_subqueries value, ignoring limit")
                max_subqueries = None
        
        try:
            subqueries = await query_analysis_service.analyze_and_split_query(
                input_text=input_text,
                delegate_descriptions=delegate_descriptions,
                llm_provider=llm_provider,
                project=project,
                max_subqueries=max_subqueries
            )
            
            if not subqueries:
                logger.warning(f"⚠️ GROUP CHAT MANAGER (INTELLIGENT): No subqueries generated, falling back to single query")
                subqueries = [{
                    'subquery_id': 'fallback_0',
                    'query': input_text,
                    'priority': 'medium',
                    'dependencies': [],
                    'suggested_delegates': list(delegate_descriptions.keys()),
                    'index': 0,
                    'created_at': ''
                }]
            
            logger.info(f"✅ GROUP CHAT MANAGER (INTELLIGENT): Split into {len(subqueries)} subqueries")
            
        except Exception as e:
            logger.error(f"❌ GROUP CHAT MANAGER (INTELLIGENT): Query analysis failed: {e}")
            import traceback
            logger.error(f"❌ GROUP CHAT MANAGER (INTELLIGENT): Traceback: {traceback.format_exc()}")
            # Fallback: treat entire input as single subquery
            subqueries = [{
                'subquery_id': 'fallback_0',
                'query': input_text,
                'priority': 'medium',
                'dependencies': [],
                'suggested_delegates': list(delegate_descriptions.keys()),
                'index': 0,
                'created_at': ''
            }]
        
        # Step 2: Match subqueries to delegates (PARALLELIZED)
        logger.info(f"🎯 GROUP CHAT MANAGER (INTELLIGENT): Matching {len(subqueries)} subqueries to delegates in parallel")
        subquery_assignments = {}
        
        # Track assignment statistics for debugging
        delegate_assignment_counts = {name: 0 for name in delegate_descriptions.keys()}
        
        # Create parallel matching tasks for all subqueries
        matching_tasks = []
        for subquery in subqueries:
            sq_id = subquery['subquery_id']
            sq_text = subquery['query']
            
            # Create async task for matching (don't await yet)
            task = query_analysis_service.match_subquery_to_delegate(
                subquery=sq_text,
                delegate_descriptions=delegate_descriptions,
                llm_provider=llm_provider,
                confidence_threshold=confidence_threshold,
                project=project
            )
            matching_tasks.append((sq_id, subquery, task))
        
        # Execute all matching operations in parallel
        logger.info(f"🚀 GROUP CHAT MANAGER (INTELLIGENT): Executing {len(matching_tasks)} subquery matching operations in parallel")
        matching_results = await asyncio.gather(
            *[task for _, _, task in matching_tasks],
            return_exceptions=True
        )
        
        # Process matching results
        for (sq_id, subquery, _), match_result in zip(matching_tasks, matching_results):
            try:
                # Handle exceptions from parallel execution
                if isinstance(match_result, Exception):
                    logger.error(f"❌ GROUP CHAT MANAGER (INTELLIGENT): Exception matching subquery {sq_id[:8]}: {match_result}")
                    # Fallback: assign to all delegates
                    assigned_delegates = list(delegate_descriptions.keys())
                    for delegate_name in assigned_delegates:
                        if delegate_name in delegate_assignment_counts:
                            delegate_assignment_counts[delegate_name] += 1
                    subquery_assignments[sq_id] = {
                        'subquery': subquery,
                        'assigned_delegates': assigned_delegates,
                        'confidence': 0.5,
                        'reasoning': f'Fallback: assigned to all delegates due to matching error: {str(match_result)}',
                        'status': 'pending'
                    }
                    continue
                
                # Process successful match result
                assigned_delegates = match_result.get('assigned_delegates', [])
                confidence = match_result.get('confidence', 0.0)
                reasoning = match_result.get('reasoning', '')
                
                logger.info(f"🎯 GROUP CHAT MANAGER (INTELLIGENT): Subquery {sq_id[:8]} matched to {len(assigned_delegates)} delegate(s) with confidence {confidence:.2f}")
                logger.info(f"🎯 GROUP CHAT MANAGER (INTELLIGENT): Assigned delegates: {', '.join(assigned_delegates)}")
                logger.info(f"🎯 GROUP CHAT MANAGER (INTELLIGENT): Reasoning: {reasoning}")
                
                # Log delegation decision for monitoring
                logger.info(f"📊 DELEGATION DECISION: subquery_id={sq_id[:8]}, delegates={assigned_delegates}, confidence={confidence:.3f}, threshold={confidence_threshold}")
                
                # If no delegates assigned or confidence too low, broadcast to all
                if not assigned_delegates or confidence < confidence_threshold:
                    logger.warning(f"⚠️ GROUP CHAT MANAGER (INTELLIGENT): Low confidence ({confidence:.2f}) or no match for {sq_id[:8]}, broadcasting to all {len(delegate_descriptions)} delegates")
                    assigned_delegates = list(delegate_descriptions.keys())
                    confidence = 0.5
                    logger.info(f"📊 DELEGATE ASSIGNMENT: Subquery {sq_id[:8]} broadcast to all delegates: {assigned_delegates}")
                
                # Track assignment counts
                for delegate_name in assigned_delegates:
                    if delegate_name in delegate_assignment_counts:
                        delegate_assignment_counts[delegate_name] += 1
                
                subquery_assignments[sq_id] = {
                    'subquery': subquery,
                    'assigned_delegates': assigned_delegates,
                    'confidence': confidence,
                    'reasoning': reasoning,
                    'status': 'pending'
                }
            except Exception as e:
                logger.error(f"❌ GROUP CHAT MANAGER (INTELLIGENT): Failed to process match result for subquery {sq_id[:8]}: {e}")
                # Fallback: assign to all delegates
                assigned_delegates = list(delegate_descriptions.keys())
                for delegate_name in assigned_delegates:
                    if delegate_name in delegate_assignment_counts:
                        delegate_assignment_counts[delegate_name] += 1
                subquery_assignments[sq_id] = {
                    'subquery': subquery,
                    'assigned_delegates': assigned_delegates,
                    'confidence': 0.5,
                    'reasoning': f'Fallback: assigned to all delegates due to processing error: {str(e)}',
                    'status': 'pending'
                }
        
        # Step 3: Delegate subqueries to assigned delegates (PARALLEL with dependency handling)
        logger.info(f"📨 GROUP CHAT MANAGER (INTELLIGENT): Delegating {len(subquery_assignments)} subqueries to delegates")
        
        delegate_responses = {}  # {subquery_id: {delegate_name: response}}
        conversation_log = []
        delegation_metrics = {
            'total_delegations': 0,
            'successful_delegations': 0,
            'failed_delegations': 0,
            'timeouts': 0,
            'retries': 0,
            'matching_time': matching_time,
            'delegation_start_time': None,
            'delegation_end_time': None
        }
        
        # Group subqueries by dependency level for parallel processing
        dependency_levels = self._group_subqueries_by_dependency_level(subqueries, subquery_assignments)
        
        delegation_start_time = asyncio.get_event_loop().time()
        delegation_metrics['delegation_start_time'] = delegation_start_time
        
        # Process each dependency level sequentially, but subqueries within a level in parallel
        for level_idx, level_subqueries in enumerate(dependency_levels):
            logger.info(f"🔄 GROUP CHAT MANAGER (INTELLIGENT): Processing dependency level {level_idx + 1}/{len(dependency_levels)} with {len(level_subqueries)} subqueries in parallel")
            
            # Create delegation messages for all subqueries in this level
            level_tasks = []
            for sq_id, assignment in level_subqueries:
                subquery = assignment['subquery']
                sq_text = subquery['query']
                
                # Create delegation message
                delegation_message = DelegationMessageProtocol.create_delegation_message(
                    subquery=sq_text,
                    subquery_id=sq_id,
                    priority=subquery.get('priority', 'medium'),
                    original_input=input_text,
                    related_subqueries=[sq['subquery_id'] for sq in subqueries if sq['subquery_id'] != sq_id],
                    iteration=level_idx + 1,
                    delegation_confidence=assignment['confidence']
                )
                
                # Format message for delegate
                formatted_message = DelegationMessageProtocol.format_message_for_delegate(delegation_message)
                
                # Create processing task
                task = self._process_subquery_with_delegates(
                    sq_id=sq_id,
                    assignment=assignment,
                    formatted_message=formatted_message,
                    delegate_name_to_node=delegate_name_to_node,
                    llm_provider=llm_provider,
                    delegation_timeout=delegation_timeout,
                    max_retries=max_retries,
                    project_id=project_id,
                    project=project,
                    delegation_metrics=delegation_metrics
                )
                level_tasks.append((sq_id, task))
            
            # Execute all subqueries in this level in parallel
            logger.info(f"🚀 GROUP CHAT MANAGER (INTELLIGENT): Executing {len(level_tasks)} subqueries in parallel at level {level_idx + 1}")
            level_results = await asyncio.gather(
                *[task for _, task in level_tasks],
                return_exceptions=True
            )
            
            # Process results
            for (sq_id, _), result in zip(level_tasks, level_results):
                if isinstance(result, Exception):
                    logger.error(f"❌ GROUP CHAT MANAGER (INTELLIGENT): Exception processing subquery {sq_id[:8]}: {result}")
                    delegate_responses[sq_id] = {}
                    assignment = subquery_assignments.get(sq_id, {})
                    assignment['status'] = 'error'
                else:
                    delegate_responses[sq_id] = result['delegate_responses']
                    assignment = subquery_assignments.get(sq_id, {})
                    assignment['status'] = 'completed' if result['success'] else 'error'
                    
                    # Add to conversation log
                    for delegate_name, response_data in result['delegate_responses'].items():
                        conversation_log.append(
                            f"[Subquery {sq_id[:8]}] {delegate_name}: {response_data['response'][:200]}..."
                        )
        
        delegation_end_time = asyncio.get_event_loop().time()
        delegation_metrics['delegation_end_time'] = delegation_end_time
        delegation_metrics['delegation_time'] = delegation_end_time - delegation_start_time
        logger.info(f"✅ GROUP CHAT MANAGER (INTELLIGENT): Completed parallel delegation in {delegation_metrics['delegation_time']:.2f}s")
        
        # Step 4: Aggregate responses and generate final synthesis
        logger.info(f"📊 GROUP CHAT MANAGER (INTELLIGENT): Aggregating {len(conversation_log)} delegate responses")
        
        # Calculate performance metrics
        total_time = delegation_metrics.get('delegation_time', 0) + delegation_metrics.get('matching_time', 0)
        avg_delegate_time = delegation_metrics['delegation_time'] / max(delegation_metrics['total_delegations'], 1) if delegation_metrics.get('delegation_time') else 0
        success_rate = (delegation_metrics['successful_delegations'] / max(delegation_metrics['total_delegations'], 1)) * 100
        
        logger.info(f"📊 PERFORMANCE METRICS:")
        logger.info(f"  - Matching time: {delegation_metrics.get('matching_time', 0):.2f}s")
        logger.info(f"  - Delegation time: {delegation_metrics.get('delegation_time', 0):.2f}s")
        logger.info(f"  - Total time: {total_time:.2f}s")
        logger.info(f"  - Average delegate time: {avg_delegate_time:.2f}s")
        logger.info(f"  - Success rate: {success_rate:.1f}%")
        logger.info(f"  - Total delegations: {delegation_metrics['total_delegations']}")
        logger.info(f"  - Successful: {delegation_metrics['successful_delegations']}")
        logger.info(f"  - Failed: {delegation_metrics['failed_delegations']}")
        logger.info(f"  - Retries: {delegation_metrics['retries']}")
        
        # Build aggregation context
        aggregation_context = f"""
Intelligent Delegation Summary:
- Total Subqueries: {len(subqueries)}
- Total Delegations: {delegation_metrics['total_delegations']}
- Successful: {delegation_metrics['successful_delegations']}
- Failed: {delegation_metrics['failed_delegations']}
- Timeouts: {delegation_metrics['timeouts']}
- Performance: Matching {delegation_metrics.get('matching_time', 0):.2f}s, Delegation {delegation_metrics.get('delegation_time', 0):.2f}s, Total {total_time:.2f}s

Subquery Results:
"""
        
        for sq_id, assignment in subquery_assignments.items():
            subquery = assignment['subquery']
            responses = delegate_responses.get(sq_id, {})
            
            aggregation_context += f"\nSubquery {sq_id[:8]} ({subquery['priority']} priority):\n"
            aggregation_context += f"Query: {subquery['query']}\n"
            aggregation_context += f"Assigned to: {', '.join(assignment['assigned_delegates'])} (confidence: {assignment['confidence']:.2f})\n"
            
            for delegate_name, response_data in responses.items():
                status_icon = "✅" if response_data['status'] == 'completed' else "❌"
                aggregation_context += f"{status_icon} {delegate_name}: {response_data['response'][:300]}\n"
        
        # Generate final synthesis
        final_prompt = f"""You are the Group Chat Manager named {manager_name}.

You have used intelligent task delegation to split the input into subqueries and route them to specialized delegate agents based on their capabilities.

Original Input:
{input_text}

{aggregation_context}

Delegate Conversation Log:
{'; '.join(conversation_log[-10:])}  # Last 10 entries

Based on the intelligent delegation results and delegate responses, provide a comprehensive summary and final output.
Synthesize insights from all subquery results into actionable conclusions.
Highlight how the intelligent routing improved the task execution."""
        
        try:
            final_response = await llm_provider.generate_response(
                prompt=final_prompt,
                temperature=manager_data.get('temperature', 0.5),
                max_tokens=2000
            )
            
            if final_response.error:
                raise Exception(f"GroupChatManager intelligent delegation final response error: {final_response.error}")
            
            final_output = f"""GroupChatManager Intelligent Delegation Summary (processed {len(subqueries)} subqueries, {delegation_metrics['successful_delegations']} successful delegations):

{final_response.text.strip()}

Delegation Metrics:
- Total Subqueries: {len(subqueries)}
- Total Delegations: {delegation_metrics['total_delegations']}
- Successful: {delegation_metrics['successful_delegations']}
- Failed: {delegation_metrics['failed_delegations']}
- Timeouts: {delegation_metrics['timeouts']}
- Retries: {delegation_metrics['retries']}
- Performance: Matching {delegation_metrics.get('matching_time', 0):.2f}s, Delegation {delegation_metrics.get('delegation_time', 0):.2f}s, Total {total_time:.2f}s
- Success Rate: {success_rate:.1f}%
"""
            
            logger.info(f"✅ GROUP CHAT MANAGER (INTELLIGENT): Completed intelligent delegation")
            logger.info(f"📊 DELEGATION METRICS: {delegation_metrics}")
            logger.info(f"📊 FINAL STATS: {len(subqueries)} subqueries, {delegation_metrics['successful_delegations']} successful, {delegation_metrics['failed_delegations']} failed, {delegation_metrics['retries']} retries")
            logger.info(f"📊 PERFORMANCE: Total time {total_time:.2f}s (Matching: {delegation_metrics.get('matching_time', 0):.2f}s, Delegation: {delegation_metrics.get('delegation_time', 0):.2f}s)")
            
            # Build delegate status for compatibility
            delegate_status = {}
            for delegate_name in delegate_descriptions.keys():
                assignments_count = sum(1 for sq_id, assignment in subquery_assignments.items() if delegate_name in assignment['assigned_delegates'])
                successful_count = sum(1 for sq_id, responses in delegate_responses.items() 
                                      if delegate_name in responses and responses[delegate_name].get('status') == 'completed')
                
                delegate_status[delegate_name] = {
                    'iterations': assignments_count,
                    'successful_iterations': successful_count,
                    'max_iterations': len(subqueries),
                    'completed': True,
                    'node': delegate_name_to_node[delegate_name],
                    'utilization_rate': assignments_count / len(subqueries) if subqueries else 0.0,
                    'success_rate': successful_count / assignments_count if assignments_count > 0 else 0.0
                }
                
                logger.info(f"📊 DELEGATE STATS: {delegate_name} - {assignments_count} assignments, {successful_count} successful ({delegate_status[delegate_name]['success_rate']:.1%} success rate)")
            
            # Build a flat list of all delegate responses for easier logging
            all_delegate_responses = []
            for sq_id, responses in delegate_responses.items():
                for delegate_name, response_data in responses.items():
                    if isinstance(response_data, dict):
                        response_text = response_data.get('response', response_data.get('text', str(response_data)))
                        status = response_data.get('status', 'completed')
                    else:
                        response_text = str(response_data)
                        status = 'completed'
                    
                    all_delegate_responses.append({
                        'delegate_name': delegate_name,
                        'response': response_text,
                        'status': status,
                        'subquery_id': sq_id
                    })
            
            return {
                'final_response': final_output,
                'delegate_conversations': conversation_log,
                'delegate_status': delegate_status,
                'total_iterations': delegation_metrics['total_delegations'],
                'input_count': aggregated_context.get('input_count', 1),
                'delegation_metrics': delegation_metrics,
                'subquery_assignments': subquery_assignments,
                'delegate_responses_flat': all_delegate_responses  # Add flat list for easier logging
            }
            
        except Exception as e:
            logger.error(f"❌ GROUP CHAT MANAGER (INTELLIGENT): Final synthesis failed: {e}")
            import traceback
            logger.error(f"❌ GROUP CHAT MANAGER (INTELLIGENT): Traceback: {traceback.format_exc()}")
            raise e
    
    async def _execute_delegate_with_retry(
        self,
        delegate_name: str,
        delegate_node: Dict[str, Any],
        llm_provider,
        delegation_message: str,
        subquery_id: str,
        delegation_timeout: int,
        max_retries: int,
        project_id: Optional[str] = None,
        project: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Execute a delegate with retry logic and return structured result
        
        Returns:
            Dict with 'success', 'response', 'status', 'confidence', 'metadata', 'retry_count', 'error'
        """
        retry_count = 0
        last_error = None
        
        while retry_count <= max_retries:
            try:
                if retry_count > 0:
                    # Exponential backoff: 1s, 2s, 4s
                    backoff_delay = min(2 ** retry_count, 10)
                    logger.info(f"🔄 GROUP CHAT MANAGER (INTELLIGENT): Retry {retry_count}/{max_retries} for {delegate_name} after {backoff_delay}s")
                    await asyncio.sleep(backoff_delay)
                
                attempt_number = retry_count + 1
                logger.info(f"📤 GROUP CHAT MANAGER (INTELLIGENT): Sending subquery {subquery_id[:8]} to {delegate_name} (attempt {attempt_number}/{max_retries + 1})")
                
                # Execute delegate with delegation message
                delegate_response = await asyncio.wait_for(
                    self._execute_delegate_with_delegation_message(
                        delegate_node=delegate_node,
                        llm_provider=llm_provider,
                        delegation_message=delegation_message,
                        subquery_id=subquery_id,
                        project_id=project_id,
                        project=project
                    ),
                    timeout=delegation_timeout
                )
                
                # Log successful execution (only on first attempt, not retries)
                if retry_count == 0:
                    logger.info(f"✅ GROUP CHAT MANAGER (INTELLIGENT): {delegate_name} successfully executed subquery {subquery_id[:8]} on first attempt")
                else:
                    logger.info(f"✅ GROUP CHAT MANAGER (INTELLIGENT): {delegate_name} successfully executed subquery {subquery_id[:8]} after {retry_count} retry(ies)")
                
                # Validate response
                if not delegate_response or delegate_response.strip().startswith("ERROR:"):
                    raise Exception(f"Delegate returned error: {delegate_response}")
                
                # Parse response
                parsed_response = DelegationMessageProtocol.parse_delegate_response(delegate_response)
                
                if parsed_response:
                    return {
                        'success': True,
                        'response': parsed_response.get('response', delegate_response),
                        'status': parsed_response.get('status', 'completed'),
                        'confidence': parsed_response.get('confidence', 1.0),
                        'metadata': parsed_response.get('metadata', {}),
                        'retry_count': retry_count,
                        'error': None
                    }
                else:
                    return {
                        'success': True,
                        'response': delegate_response,
                        'status': 'completed',
                        'confidence': 1.0,
                        'metadata': {},
                        'retry_count': retry_count,
                        'error': None
                    }
                    
            except asyncio.TimeoutError:
                last_error = TimeoutError(f"Timeout waiting for {delegate_name} response (>{delegation_timeout}s)")
                logger.error(f"⏱️ GROUP CHAT MANAGER (INTELLIGENT): Timeout for {delegate_name} on attempt {retry_count + 1}")
                
                if retry_count >= max_retries:
                    return {
                        'success': False,
                        'response': f"ERROR: Timeout after {max_retries + 1} attempts",
                        'status': 'error',
                        'confidence': 0.0,
                        'metadata': {'error_type': 'timeout', 'retry_count': retry_count},
                        'retry_count': retry_count,
                        'error': str(last_error)
                    }
                
                retry_count += 1
                
            except Exception as e:
                last_error = e
                error_type = type(e).__name__
                is_retryable = isinstance(e, (ConnectionError, TimeoutError)) or "timeout" in str(e).lower()
                
                logger.error(f"❌ GROUP CHAT MANAGER (INTELLIGENT): Error delegating to {delegate_name} on attempt {retry_count + 1}: {error_type}: {str(e)}")
                
                if not is_retryable or retry_count >= max_retries:
                    import traceback
                    logger.error(f"❌ GROUP CHAT MANAGER (INTELLIGENT): Traceback: {traceback.format_exc()}")
                    
                    return {
                        'success': False,
                        'response': f"ERROR: {str(e)}",
                        'status': 'error',
                        'confidence': 0.0,
                        'metadata': {
                            'error_type': error_type,
                            'retryable': is_retryable,
                            'retry_count': retry_count
                        },
                        'retry_count': retry_count,
                        'error': str(e)
                    }
                
                retry_count += 1
        
        # Should not reach here, but handle it
        return {
            'success': False,
            'response': f"ERROR: Failed after {retry_count} attempts: {str(last_error)}",
            'status': 'error',
            'confidence': 0.0,
            'metadata': {'retry_count': retry_count},
            'retry_count': retry_count,
            'error': str(last_error) if last_error else 'Unknown error'
        }
    
    def _group_subqueries_by_dependency_level(
        self,
        subqueries: List[Dict[str, Any]],
        subquery_assignments: Dict[str, Any]
    ) -> List[List[tuple]]:
        """
        Group subqueries by dependency level for parallel processing
        
        Returns:
            List of levels, where each level is a list of (sq_id, assignment) tuples
            that can be processed in parallel
        """
        # Build dependency map: sq_id -> set of dependent sq_ids
        dependency_map = {}
        sq_id_to_index = {}
        
        for sq in subqueries:
            sq_id = sq['subquery_id']
            sq_index = sq.get('index', 0)
            sq_id_to_index[sq_id] = sq_index
            dependency_map[sq_id] = set()
        
        # Build reverse dependency map: which subqueries depend on this one
        reverse_deps = {sq_id: set() for sq_id in dependency_map.keys()}
        
        for sq in subqueries:
            sq_id = sq['subquery_id']
            dependencies = sq.get('dependencies', [])
            for dep_idx in dependencies:
                # Find the subquery with this index
                for dep_sq in subqueries:
                    if dep_sq.get('index') == dep_idx:
                        dep_sq_id = dep_sq['subquery_id']
                        dependency_map[sq_id].add(dep_sq_id)
                        reverse_deps[dep_sq_id].add(sq_id)
                        break
        
        # Topological sort to group by levels
        levels = []
        processed = set()
        remaining = set(dependency_map.keys())
        
        while remaining:
            # Find all subqueries with no unprocessed dependencies
            current_level = []
            for sq_id in list(remaining):
                deps = dependency_map.get(sq_id, set())
                if deps.issubset(processed):
                    # All dependencies are processed, can add to current level
                    if sq_id in subquery_assignments:
                        current_level.append((sq_id, subquery_assignments[sq_id]))
            
            if not current_level:
                # Circular dependency or error - process remaining anyway
                logger.warning(f"⚠️ GROUP CHAT MANAGER (INTELLIGENT): Circular dependency detected or missing assignments, processing remaining subqueries")
                for sq_id in list(remaining):
                    if sq_id in subquery_assignments:
                        current_level.append((sq_id, subquery_assignments[sq_id]))
            
            if not current_level:
                break
            
            levels.append(current_level)
            for sq_id, _ in current_level:
                processed.add(sq_id)
                remaining.discard(sq_id)
        
        logger.info(f"📊 GROUP CHAT MANAGER (INTELLIGENT): Grouped {len(subqueries)} subqueries into {len(levels)} dependency levels")
        for level_idx, level in enumerate(levels):
            logger.info(f"  Level {level_idx + 1}: {len(level)} subqueries")
        
        return levels
    
    async def _process_subquery_with_delegates(
        self,
        sq_id: str,
        assignment: Dict[str, Any],
        formatted_message: str,
        delegate_name_to_node: Dict[str, Dict[str, Any]],
        llm_provider,
        delegation_timeout: int,
        max_retries: int,
        project_id: Optional[str],
        project: Optional[Any],
        delegation_metrics: Dict[str, int]
    ) -> Dict[str, Any]:
        """
        Process a single subquery by delegating to assigned delegates in parallel
        
        Returns:
            Dict with 'sq_id', 'delegate_responses', 'success'
        """
        assigned_delegates = assignment['assigned_delegates']
        subquery = assignment['subquery']
        
        logger.info(f"📨 GROUP CHAT MANAGER (INTELLIGENT): Processing subquery {sq_id[:8]} with {len(assigned_delegates)} delegate(s) in parallel")
        
        # Create parallel tasks for all delegates
        delegate_tasks = []
        for delegate_name in assigned_delegates:
            if delegate_name not in delegate_name_to_node:
                logger.warning(f"⚠️ GROUP CHAT MANAGER (INTELLIGENT): Delegate {delegate_name} not found, skipping")
                continue
            
            delegate_node = delegate_name_to_node[delegate_name]
            delegation_metrics['total_delegations'] += 1
            
            # Create task for parallel execution
            task = self._execute_delegate_with_retry(
                delegate_name=delegate_name,
                delegate_node=delegate_node,
                llm_provider=llm_provider,
                delegation_message=formatted_message,
                subquery_id=sq_id,
                delegation_timeout=delegation_timeout,
                max_retries=max_retries,
                project_id=project_id,
                project=project
            )
            delegate_tasks.append((delegate_name, task))
        
        if not delegate_tasks:
            logger.warning(f"⚠️ GROUP CHAT MANAGER (INTELLIGENT): No valid delegates for subquery {sq_id[:8]}")
            return {
                'sq_id': sq_id,
                'delegate_responses': {},
                'success': False
            }
        
        # Execute all delegates in parallel
        logger.info(f"🚀 GROUP CHAT MANAGER (INTELLIGENT): Executing {len(delegate_tasks)} delegates in parallel for {sq_id[:8]}")
        delegate_results = await asyncio.gather(
            *[task for _, task in delegate_tasks],
            return_exceptions=True
        )
        
        # Process results
        delegate_responses = {}
        for (delegate_name, _), result in zip(delegate_tasks, delegate_results):
            if isinstance(result, Exception):
                logger.error(f"❌ GROUP CHAT MANAGER (INTELLIGENT): Exception from {delegate_name}: {result}")
                delegate_responses[delegate_name] = {
                    'response': f"ERROR: {str(result)}",
                    'status': 'error',
                    'confidence': 0.0,
                    'metadata': {},
                    'retry_count': 0
                }
                delegation_metrics['failed_delegations'] += 1
            elif result.get('success'):
                delegate_responses[delegate_name] = {
                    'response': result['response'],
                    'status': result['status'],
                    'confidence': result['confidence'],
                    'metadata': result['metadata'],
                    'retry_count': result['retry_count']
                }
                delegation_metrics['successful_delegations'] += 1
                if result.get('retry_count', 0) > 0:
                    delegation_metrics['retries'] += result['retry_count']
                logger.info(f"✅ GROUP CHAT MANAGER (INTELLIGENT): Received response from {delegate_name} for {sq_id[:8]}")
            else:
                delegate_responses[delegate_name] = {
                    'response': result['response'],
                    'status': result['status'],
                    'confidence': result['confidence'],
                    'metadata': result['metadata'],
                    'retry_count': result['retry_count']
                }
                delegation_metrics['failed_delegations'] += 1
                if result.get('error'):
                    logger.error(f"❌ GROUP CHAT MANAGER (INTELLIGENT): Failed to get response from {delegate_name}: {result['error']}")
        
        return {
            'sq_id': sq_id,
            'delegate_responses': delegate_responses,
            'success': any(r.get('status') == 'completed' for r in delegate_responses.values())
        }
    
    async def _execute_delegate_with_delegation_message(
        self,
        delegate_node: Dict[str, Any],
        llm_provider,
        delegation_message: str,
        subquery_id: str,
        project_id: Optional[str] = None,
        project: Optional[Any] = None
    ) -> str:
        """
        Execute a delegate agent with a delegation message
        
        Args:
            delegate_node: The delegate node data
            llm_provider: LLM provider instance (fallback)
            delegation_message: Formatted delegation message
            subquery_id: Subquery ID for tracking
            project_id: Project ID for DocAware
            project: Project instance for API keys
            
        Returns:
            Delegate response text
        """
        delegate_name = delegate_node.get('data', {}).get('name', 'Delegate')
        delegate_data = delegate_node.get('data', {})
        
        logger.info(f"🤝 DELEGATE (INTELLIGENT): Processing delegation for {delegate_name}, subquery {subquery_id[:8]}")
        
        # Create delegate-specific LLM provider
        delegate_config = {
            'llm_provider': delegate_data.get('llm_provider', 'openai'),
            'llm_model': delegate_data.get('llm_model', 'gpt-4')
        }
        
        delegate_llm = None
        try:
            # Safety fallback: Get project if None but project_id exists
            if project is None and project_id:
                from users.models import IntelliDocProject
                from asgiref.sync import sync_to_async
                try:
                    project = await sync_to_async(IntelliDocProject.objects.get)(project_id=project_id)
                    logger.info(f"✅ DELEGATE (INTELLIGENT): Retrieved project {project.name} for {delegate_name} API keys")
                except Exception as e:
                    logger.warning(f"⚠️ DELEGATE (INTELLIGENT): Could not retrieve project {project_id} for {delegate_name}: {e}")
            
            if not project:
                error_msg = f"Project context is required for delegate {delegate_name}. All agents must use project-specific API keys."
                logger.error(f"❌ DELEGATE (INTELLIGENT): {error_msg}")
                delegate_llm = None
            else:
                delegate_llm = await self.llm_provider_manager.get_llm_provider(delegate_config, project)
                if delegate_llm:
                    logger.info(f"✅ DELEGATE (INTELLIGENT): Created LLM provider for {delegate_name} with project {project.name} API keys")
                else:
                    error_msg = f"Failed to create LLM provider for delegate {delegate_name} in project {project.name}. Please configure project-specific API keys in project settings."
                    logger.error(f"❌ DELEGATE (INTELLIGENT): {error_msg}")
        except Exception as e:
            error_msg = f"Failed to create provider for {delegate_name}: {str(e)}"
            if project:
                error_msg += f" (project: {project.name})"
            logger.error(f"❌ DELEGATE (INTELLIGENT): {error_msg}")
            import traceback
            logger.error(f"❌ DELEGATE (INTELLIGENT): Traceback: {traceback.format_exc()}")
        
        # Fallback to provided LLM provider
        if not delegate_llm:
            delegate_llm = llm_provider
        
        if not delegate_llm:
            error_msg = f"No LLM provider available for delegate {delegate_name}"
            logger.error(f"❌ DELEGATE (INTELLIGENT): {error_msg}")
            return f"ERROR: {error_msg}"
        
        # Build delegate prompt with delegation message
        system_message = delegate_data.get('system_message', 'You are a helpful specialized delegate agent.')
        
        delegate_prompt = f"""You are {delegate_name}, a specialized delegate agent.

System Message: {system_message}

{delegation_message}

Instructions:
- Process the delegated subquery carefully
- Provide a clear, actionable response
- If you need clarification, indicate so in your response
- Complete your response with your analysis and recommendations

Your response:"""
        
        try:
            # Enhanced diagnostic logging before LLM call
            logger.info(f"🔍 DELEGATE DEBUG: About to call LLM for {delegate_name} (Intelligent Delegation)")
            logger.info(f"🔍 DELEGATE DEBUG: Provider type: {type(delegate_llm).__name__}")
            logger.info(f"🔍 DELEGATE DEBUG: Has generate_response method: {hasattr(delegate_llm, 'generate_response')}")
            logger.info(f"🔍 DELEGATE DEBUG: LLM Model: {delegate_data.get('llm_model', 'unknown')}")
            logger.info(f"🔍 DELEGATE DEBUG: Temperature: {delegate_data.get('temperature', 0.4)}")
            logger.info(f"🔍 DELEGATE DEBUG: Max Tokens: {delegate_data.get('max_tokens', 1024)}")
            logger.info(f"🤖 DELEGATE (INTELLIGENT): Calling LLM for {delegate_name}")
            
            delegate_response = await delegate_llm.generate_response(
                prompt=delegate_prompt,
                max_tokens=delegate_data.get('max_tokens', 1024),
                temperature=delegate_data.get('temperature', 0.4)
            )
            
            if delegate_response.error:
                logger.error(f"❌ DELEGATE (INTELLIGENT): LLM error for {delegate_name}: {delegate_response.error}")
                logger.error(f"❌ DELEGATE (INTELLIGENT): LLM Provider: {type(delegate_llm).__name__}")
                logger.error(f"❌ DELEGATE (INTELLIGENT): Model: {delegate_data.get('llm_model', 'unknown')}")
                return f"ERROR: {delegate_response.error}"
            
            # Check for text attribute
            if not hasattr(delegate_response, 'text'):
                error_msg = f"Delegate {delegate_name} response missing 'text' attribute. Response type: {type(delegate_response)}"
                logger.error(f"❌ DELEGATE (INTELLIGENT): {error_msg}")
                logger.error(f"❌ DELEGATE (INTELLIGENT): Response object type: {type(delegate_response)}")
                logger.error(f"❌ DELEGATE (INTELLIGENT): Response attributes: {dir(delegate_response)}")
                logger.error(f"❌ DELEGATE (INTELLIGENT): LLM Provider: {type(delegate_llm).__name__}")
                logger.error(f"❌ DELEGATE (INTELLIGENT): Model: {delegate_data.get('llm_model', 'unknown')}")
                return f"ERROR: {error_msg}"
            
            response_text = delegate_response.text.strip()
            
            if not response_text:
                error_msg = f"Delegate {delegate_name} received empty response from LLM"
                logger.error(f"❌ DELEGATE (INTELLIGENT): {error_msg}")
                logger.error(f"❌ DELEGATE (INTELLIGENT): Response object type: {type(delegate_response)}")
                logger.error(f"❌ DELEGATE (INTELLIGENT): Response attributes: {dir(delegate_response)}")
                logger.error(f"❌ DELEGATE (INTELLIGENT): Response error attribute: {getattr(delegate_response, 'error', 'N/A')}")
                logger.error(f"❌ DELEGATE (INTELLIGENT): LLM Provider: {type(delegate_llm).__name__}")
                logger.error(f"❌ DELEGATE (INTELLIGENT): Model: {delegate_data.get('llm_model', 'unknown')}")
                return f"ERROR: {error_msg}"
            
            logger.info(f"✅ DELEGATE (INTELLIGENT): {delegate_name} completed processing ({len(response_text)} chars)")
            return response_text
            
        except Exception as e:
            logger.error(f"❌ DELEGATE (INTELLIGENT): Exception for {delegate_name}: {e}")
            import traceback
            logger.error(f"❌ DELEGATE (INTELLIGENT): Traceback: {traceback.format_exc()}")
            return f"ERROR: Delegate execution failed: {str(e)}"