"""
Workflow Executor
================

Main workflow execution engine for conversation orchestration.
"""

import logging
import time
import asyncio
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from django.utils import timezone
from asgiref.sync import sync_to_async

from users.models import WorkflowExecution, WorkflowExecutionMessage, WorkflowExecutionStatus, AgentWorkflow
from llm_eval.providers.base import LLMResponse

logger = logging.getLogger('conversation_orchestrator')


class MessageSequenceManager:
    """
    Manages message sequencing to prevent duplicate sequence numbers
    """
    
    def __init__(self, existing_messages=None):
        self.messages = existing_messages or []
        self.sequence_counter = len(self.messages)
    
    def add_message(self, agent_name, agent_type, content, message_type, **kwargs):
        """Add message with auto-incrementing sequence number"""
        message = {
            'sequence': self.sequence_counter,
            'agent_name': agent_name,
            'agent_type': agent_type,
            'content': content,
            'message_type': message_type,
            'timestamp': timezone.now().isoformat(),
            'response_time_ms': kwargs.get('response_time_ms', 0),
            'token_count': kwargs.get('token_count', None),
            'metadata': kwargs.get('metadata', {})
        }
        
        self.messages.append(message)
        self.sequence_counter += 1
        
        return message, self.sequence_counter - 1  # Return message and its sequence
    
    def get_messages(self):
        return self.messages
    
    def get_next_sequence(self):
        return self.sequence_counter


class WorkflowExecutor:
    """
    Main workflow execution engine
    """
    
    def __init__(self, workflow_parser, llm_provider_manager, chat_manager, docaware_handler, human_input_handler, reflection_handler):
        self.workflow_parser = workflow_parser
        self.llm_provider_manager = llm_provider_manager
        self.chat_manager = chat_manager
        self.docaware_handler = docaware_handler
        self.human_input_handler = human_input_handler
        self.reflection_handler = reflection_handler
    
    async def execute_workflow(self, workflow: AgentWorkflow, executed_by) -> Dict[str, Any]:
        """
        Execute the complete workflow with REAL LLM calls and conversation chaining
        Returns execution results as dictionary instead of database records
        """
        # Get workflow data using sync_to_async to avoid async context issues
        workflow_id = await sync_to_async(lambda: workflow.workflow_id)()
        graph_json = await sync_to_async(lambda: workflow.graph_json)()
        workflow_name = await sync_to_async(lambda: workflow.name)()
        project_id = await sync_to_async(lambda: workflow.project.project_id)()
        
        logger.info(f"🚀 ORCHESTRATOR: Starting REAL workflow execution for {workflow_id}")
        
        start_time = timezone.now()
        execution_id = f"exec_{int(time.time() * 1000)}" # Added milliseconds for uniqueness
        
        # CRITICAL FIX: Create execution record IMMEDIATELY so it's available for human input pausing
        execution_record = await sync_to_async(WorkflowExecution.objects.create)(
            workflow=workflow,
            execution_id=execution_id,
            start_time=start_time,
            status=WorkflowExecutionStatus.RUNNING,
            executed_by=executed_by,
            conversation_history="",
            total_messages=0,
            total_agents_involved=0,
            providers_used=[],
            result_summary=""
        )
        logger.info(f"💾 ORCHESTRATOR: Created execution record {execution_id}")
        
        try:
            # Parse workflow into execution sequence
            execution_sequence = self.workflow_parser.parse_workflow_graph(graph_json)
            
            if not execution_sequence:
                raise Exception("No execution sequence could be built from workflow graph")
            
            # CRITICAL FIX: Validate execution sequence before starting
            # Check that all nodes from graph are in sequence (except reflection-only targets)
            graph_node_ids = {node['id'] for node in graph_json.get('nodes', [])}
            sequence_node_ids = {node['id'] for node in execution_sequence}
            
            # Find nodes missing from sequence (excluding reflection-only targets which are intentionally excluded)
            missing_nodes = graph_node_ids - sequence_node_ids
            if missing_nodes:
                missing_node_names = [next((n.get('data', {}).get('name', nid) for n in graph_json.get('nodes', []) if n['id'] == nid), nid) for nid in missing_nodes]
                logger.warning(f"⚠️ ORCHESTRATOR: {len(missing_nodes)} nodes not in execution sequence: {missing_node_names}")
                # Don't fail here - reflection-only targets are intentionally excluded
                # But log for debugging
            
            # Validate sequence order: check that dependencies are satisfied
            sequence_node_map = {node['id']: node for node in execution_sequence}
            for i, node in enumerate(execution_sequence):
                node_id = node['id']
                # Check all incoming sequential edges
                for edge in graph_json.get('edges', []):
                    if edge.get('target') == node_id and edge.get('type') == 'sequential':
                        source_id = edge.get('source')
                        if source_id in sequence_node_map:
                            # Source should appear before target in sequence
                            source_index = next((idx for idx, n in enumerate(execution_sequence) if n['id'] == source_id), -1)
                            if source_index >= i:
                                source_name = sequence_node_map[source_id].get('data', {}).get('name', source_id)
                                target_name = node.get('data', {}).get('name', node_id)
                                logger.error(f"❌ ORCHESTRATOR: Dependency violation: {target_name} (position {i}) depends on {source_name} (position {source_index})")
                                raise Exception(f"Execution sequence violation: {target_name} appears before dependency {source_name}")
            
            logger.info(f"✅ ORCHESTRATOR: Execution sequence validated - {len(execution_sequence)} nodes in correct dependency order")
            
            # Initialize conversation tracking
            conversation_history = ""
            messages = execution_record.messages_data or [] # Load existing messages
            agents_involved = set()
            total_response_time = 0
            providers_used = []
            executed_nodes = execution_record.executed_nodes or {} # Load existing executed nodes
            
            # CRITICAL FIX: Use separate message sequence counter for chronological ordering
            # This ensures messages are logged in actual execution order, not graph parsing order
            message_sequence = len(messages)  # Continue from existing messages
            
            # Execute nodes with parallel execution support
            node_index = 0
            
            # CRITICAL FIX: Handle StartNode first (it's skipped by _find_ready_nodes)
            if node_index < len(execution_sequence):
                start_node = execution_sequence[node_index]
                if start_node.get('type') == 'StartNode':
                    start_node_data = start_node.get('data', {})
                    start_node_id = start_node.get('id')
                    start_prompt = start_node_data.get('prompt', 'Please begin the conversation.')
                    conversation_history = f"Start Node: {start_prompt}"
                    
                    # Store node output for multi-input support
                    executed_nodes[start_node_id] = f"Start Node: {start_prompt}"
                    
                    # Track start message
                    messages.append({
                        'sequence': message_sequence,
                        'agent_name': 'Start',
                        'agent_type': 'StartNode',
                        'content': start_prompt,
                        'message_type': 'workflow_start',
                        'timestamp': timezone.now().isoformat(),
                        'response_time_ms': 0
                    })
                    message_sequence += 1
                    
                    # Save conversation history to execution record
                    execution_record.conversation_history = conversation_history
                    execution_record.executed_nodes = executed_nodes
                    await sync_to_async(execution_record.save)(update_fields=['conversation_history', 'executed_nodes'])
                    
                    logger.info(f"✅ ORCHESTRATOR: StartNode executed - prompt: '{start_prompt[:100]}...'")
                    node_index += 1  # Move past StartNode
            
            while node_index < len(execution_sequence):
                # Check if execution has been stopped
                await sync_to_async(execution_record.refresh_from_db)()
                if execution_record.status == WorkflowExecutionStatus.STOPPED:
                    logger.info(f"🛑 ORCHESTRATOR: Execution {execution_id} has been stopped, terminating workflow")
                    return {
                        'status': 'stopped',
                        'message': 'Workflow execution was stopped by user',
                        'execution_id': execution_id
                    }
                
                # PARALLEL EXECUTION: Find all nodes ready to execute in parallel
                ready_nodes = self._find_ready_nodes(execution_sequence, executed_nodes, graph_json, node_index)
                
                if not ready_nodes:
                    # No ready nodes, move to next
                    node_index += 1
                    continue
                
                # If only one node is ready, execute it sequentially
                if len(ready_nodes) == 1:
                    node_index, node = ready_nodes[0]
                    node_index += 1  # Move to next after execution
                else:
                    # Multiple nodes ready - execute in parallel
                    logger.info(f"🔀 PARALLEL: Executing {len(ready_nodes)} nodes in parallel")
                    node_names = [n[1].get('data', {}).get('name', n[1].get('id')) for n in ready_nodes]
                    logger.info(f"🔀 PARALLEL: Nodes: {', '.join(node_names)}")
                    
                    # CRITICAL FIX: Check if UserProxyAgent's dependencies are actually satisfied
                    # Build dependency map to check UserProxyAgent dependencies
                    edges = graph_json.get('edges', [])
                    nodes = graph_json.get('nodes', [])
                    node_map = {node.get('id'): node for node in nodes}
                    dependency_map = {}
                    for edge in edges:
                        edge_type = edge.get('type', 'sequential')
                        source_id = edge.get('source')
                        target_id = edge.get('target')
                        target_node = node_map.get(target_id)
                        is_user_proxy = (target_node and 
                                        target_node.get('type') == 'UserProxyAgent' and
                                        target_node.get('data', {}).get('require_human_input', True))
                        if edge_type == 'sequential' or (edge_type == 'reflection' and is_user_proxy):
                            if target_id not in dependency_map:
                                dependency_map[target_id] = set()
                            dependency_map[target_id].add(source_id)
                    
                    # Separate UserProxyAgent nodes from other nodes
                    ready_user_proxy_nodes = []
                    other_ready_nodes = []
                    
                    for idx, node in ready_nodes:
                        if node.get('type') == 'UserProxyAgent' and node.get('data', {}).get('require_human_input', True):
                            node_id = node.get('id')
                            dependencies = dependency_map.get(node_id, set())
                            # Check if all dependencies (including reflection edges) are satisfied
                            if all(dep_id in executed_nodes for dep_id in dependencies):
                                ready_user_proxy_nodes.append((idx, node))
                                logger.info(f"✅ PARALLEL: UserProxyAgent {node.get('data', {}).get('name')} dependencies satisfied")
                            else:
                                # Dependencies not satisfied - don't execute yet
                                missing_deps = [dep_id for dep_id in dependencies if dep_id not in executed_nodes]
                                logger.info(f"⏳ PARALLEL: UserProxyAgent {node.get('data', {}).get('name')} waiting for dependencies: {missing_deps}")
                        else:
                            other_ready_nodes.append((idx, node))
                    
                    # CRITICAL FIX: Always execute other nodes first if available
                    # This ensures parallel execution happens before UserProxyAgent pauses
                    if other_ready_nodes:
                        # Execute other nodes in parallel first, UserProxyAgent will wait
                        parallel_results = await self._execute_nodes_in_parallel(
                            other_ready_nodes, workflow, graph_json, executed_nodes, conversation_history,
                            execution_record, messages, message_sequence, agents_involved,
                            total_response_time, providers_used, project_id
                        )
                        
                        # Update state from parallel execution results
                        for result in parallel_results:
                            if result.get('executed'):
                                executed_nodes[result['node_id']] = result['output']
                                conversation_history += f"\n{result['node_name']}: {result['output']}"
                                agents_involved.update(result.get('agents_involved', []))
                                total_response_time += result.get('response_time_ms', 0)
                                for provider in result.get('providers_used', []):
                                    if provider not in providers_used:
                                        providers_used.append(provider)
                        
                        # Update message sequence
                        executed_count = sum(1 for r in parallel_results if r.get('executed'))
                        message_sequence += executed_count
                        
                        # Save updated state
                        execution_record.executed_nodes = executed_nodes
                        execution_record.conversation_history = conversation_history
                        execution_record.messages_data = messages
                        await sync_to_async(execution_record.save)(update_fields=['executed_nodes', 'conversation_history', 'messages_data'])
                        
                        # Move past all executed nodes
                        max_index = max(idx for idx, _ in other_ready_nodes)
                        node_index = max_index + 1
                        # Continue loop to check UserProxyAgent again after parallel execution
                        continue
                    elif ready_user_proxy_nodes:
                        # Only UserProxyAgent nodes ready (dependencies satisfied) - execute sequentially to pause
                        node_index, node = ready_user_proxy_nodes[0]
                        # Will be handled in single node execution below
                    else:
                        # No ready nodes (shouldn't happen)
                        node_index += 1
                        continue
                
                # Single node execution - node is already set from ready_nodes[0] or ready_user_proxy_nodes[0]
                node_type = node.get('type')
                node_data = node.get('data', {})
                node_name = node_data.get('name', f'Node_{node.get("id", "unknown")}')
                node_id = node.get('id')
                
                logger.info(f"🎯 ORCHESTRATOR: Executing node {node_name} (type: {node_type}) [SEQUENTIAL]")
                
                if node_type == 'StartNode':
                    # Handle start node
                    start_prompt = node_data.get('prompt', 'Please begin the conversation.')
                    conversation_history = f"Start Node: {start_prompt}"
                    
                    # 🔍 DEBUG: Log StartNode details
                    logger.info(f"📝 STARTNODE DEBUG: Raw node_data: {node_data}")
                    logger.info(f"📝 STARTNODE DEBUG: Extracted prompt: '{start_prompt}'")
                    logger.info(f"📝 STARTNODE DEBUG: Conversation history set to: '{conversation_history}'")
                    
                    # CRITICAL: Validate StartNode prompt is not hardcoded test query
                    if start_prompt.lower().strip() in ['test query', 'test query for document search', 'sample query', 'example query']:
                        logger.error(f"❌ STARTNODE ERROR: StartNode contains forbidden hardcoded query: '{start_prompt}'")
                        logger.error(f"❌ STARTNODE ERROR: This should never happen! Check frontend/workflow definition.")
                        # Force replace with a valid query to prevent system failure
                        start_prompt = "Please provide information about the requested topic."
                        conversation_history = f"Start Node: {start_prompt}"
                        logger.info(f"🔧 STARTNODE FIX: Replaced with safe prompt: '{start_prompt}'")
                    
                    # Store node output for multi-input support
                    executed_nodes[node_id] = f"Start Node: {start_prompt}"
                    
                    # Track start message
                    messages.append({
                        'sequence': message_sequence,
                        'agent_name': 'Start',
                        'agent_type': 'StartNode',
                        'content': start_prompt,
                        'message_type': 'workflow_start',
                        'timestamp': timezone.now().isoformat(),
                        'response_time_ms': 0
                    })
                    message_sequence += 1  # Increment for chronological ordering
                    
                    # CRITICAL FIX: Save conversation history to execution record after each node
                    execution_record.conversation_history = conversation_history
                    await sync_to_async(execution_record.save)()
                    
                elif node_type in ['AssistantAgent', 'UserProxyAgent', 'GroupChatManager', 'DelegateAgent']:
                    # ============================================================================
                    # PHASE 2: USERPROXYAGENT HUMAN INPUT DETECTION AND DOCAWARE PROCESSING
                    # ============================================================================
                    if node_type == 'UserProxyAgent' and node_data.get('require_human_input', True):
                        logger.info(f"👤 HUMAN INPUT: UserProxyAgent {node_name} requires human input")
                        
                        # PAUSE WORKFLOW - NEW IMPLEMENTATION
                        human_input_data = await self.human_input_handler.pause_for_human_input(
                            workflow, node, executed_nodes, conversation_history, execution_record
                        )
                        return human_input_data  # Return paused state
                    
                    # Handle agent nodes with real LLM calls
                    agent_config = {
                        'llm_provider': node_data.get('llm_provider', 'openai'),
                        'llm_model': node_data.get('llm_model', 'gpt-3.5-turbo')
                    }
                    
                    # Get LLM provider for this agent with project context for API keys
                    project = await sync_to_async(lambda: workflow.project)()
                    llm_provider = await self.llm_provider_manager.get_llm_provider(agent_config, project)
                    if not llm_provider:
                        raise Exception(f"Failed to create LLM provider for agent {node_name} - check project API key configuration")
                    
                    # Special handling for GroupChatManager with multiple inputs support
                    if node_type == 'GroupChatManager':
                        logger.info(f"👥 ORCHESTRATOR: Executing GroupChatManager {node_name}")
                        
                        # Check for multiple inputs to this GroupChatManager
                        input_sources = self.workflow_parser.find_multiple_inputs_to_node(node_id, graph_json)
                        
                        try:
                            if len(input_sources) > 1:
                                # Use enhanced multi-input version
                                logger.info(f"📥 ORCHESTRATOR: GroupChatManager {node_name} has {len(input_sources)} input sources - using multi-input mode")
                                chat_result = await self.chat_manager.execute_group_chat_manager_with_multiple_inputs(
                                    node, llm_provider, input_sources, executed_nodes, execution_sequence, graph_json, str(project_id)
                                )
                            else:
                                # Use traditional single-input version for backward compatibility
                                logger.info(f"📥 ORCHESTRATOR: GroupChatManager {node_name} has {len(input_sources)} input source - using single-input mode")
                                chat_result = await self.chat_manager.execute_group_chat_manager(
                                    node, llm_provider, conversation_history, execution_sequence, graph_json
                                )
                            
                            logger.info(f"✅ ORCHESTRATOR: GroupChatManager {node_name} completed successfully")
                            
                            # Extract final response and delegate details
                            agent_response_text = chat_result['final_response']
                            delegate_conversations = chat_result['delegate_conversations']
                            delegate_status = chat_result['delegate_status']
                            total_iterations = chat_result['total_iterations']
                            
                            # CRITICAL FIX: Log GroupChatManager message with delegate details in metadata
                            messages.append({
                                'sequence': message_sequence,
                                'agent_name': node_name,
                                'agent_type': node_type,
                                'content': agent_response_text,
                                'message_type': 'group_chat_summary',
                                'timestamp': timezone.now().isoformat(),
                                'response_time_ms': 0,  # GroupChatManager doesn't have direct response time
                                'token_count': None,
                                'metadata': {
                                    'llm_provider': agent_config['llm_provider'],
                                    'llm_model': agent_config['llm_model'],
                                    'is_group_chat_manager': True,
                                    'total_iterations': total_iterations,
                                    'delegate_count': len(delegate_status),
                                    'expandable': True,
                                    'delegate_conversations': delegate_conversations,  # Full delegate conversation log for expand
                                    'delegate_status': delegate_status  # Delegate execution status for expand
                                }
                            })
                            message_sequence += 1  # Increment for chronological ordering
                            
                            # Save messages to execution record
                            execution_record.messages_data = messages
                            await sync_to_async(execution_record.save)()
                            logger.info(f"💾 ORCHESTRATOR: Saved GroupChatManager {node_name} message with {len(delegate_conversations)} delegate conversations in metadata")
                            
                            # CRITICAL FIX: Update conversation history with agent response
                            conversation_history += f"\n{node_name}: {agent_response_text}"
                            
                            # Store node output for multi-input support
                            executed_nodes[node_id] = agent_response_text
                            
                            # CRITICAL FIX: Track agent involvement for GroupChatManager
                            agents_involved.add(node_name)
                            if agent_config['llm_provider'] not in providers_used:
                                providers_used.append(agent_config['llm_provider'])
                            
                            # CRITICAL FIX: Save updated conversation history to database
                            execution_record.conversation_history = conversation_history
                            await sync_to_async(execution_record.save)()
                        except Exception as gcm_error:
                            logger.error(f"❌ ORCHESTRATOR: GroupChatManager {node_name} failed: {gcm_error}")
                            raise gcm_error
                    else:
                        # Handle regular agents (AssistantAgent, UserProxyAgent, and standalone DelegateAgent)
                        # Note: DelegateAgent can run standalone OR be coordinated by GroupChatManager
                        
                        # Handle regular agents (AssistantAgent, UserProxyAgent, DelegateAgent)
                        logger.info(f"🤖 ORCHESTRATOR: Executing agent {node_name} (type: {node_type})")
                        
                        # Check for multiple inputs to this agent
                        input_sources = self.workflow_parser.find_multiple_inputs_to_node(node_id, graph_json)
                        
                        # CRITICAL FIX: Validate all required inputs are available before executing
                        if len(input_sources) > 0:
                            missing_inputs = []
                            for input_source in input_sources:
                                source_id = input_source.get('source_id')
                                source_name = input_source.get('name', source_id)
                                if source_id not in executed_nodes:
                                    missing_inputs.append(f"{source_name} (node_id: {source_id})")
                            
                            if missing_inputs:
                                error_msg = f"Cannot execute {node_name}: Missing required inputs from {', '.join(missing_inputs)}. Available inputs: {list(executed_nodes.keys())}"
                                logger.error(f"❌ ORCHESTRATOR: {error_msg}")
                                raise Exception(error_msg)
                        
                        try:
                            if len(input_sources) > 1:
                                # Use multi-input processing
                                logger.info(f"📥 ORCHESTRATOR: Agent {node_name} has {len(input_sources)} input sources - using multi-input mode")
                                aggregated_context = self.workflow_parser.aggregate_multiple_inputs(input_sources, executed_nodes)
                                prompt = await self.chat_manager.craft_conversation_prompt_with_docaware(
                                    aggregated_context, node, str(project_id), conversation_history
                                )
                            else:
                                # Use traditional single-input processing
                                logger.info(f"📥 ORCHESTRATOR: Agent {node_name} has {len(input_sources)} input source - using single-input mode")
                                prompt = await self.chat_manager.craft_conversation_prompt(
                                    conversation_history, node, str(project_id)
                                )
                            
                            # Execute the agent
                            agent_response = await llm_provider.generate_response(
                                prompt=prompt
                            )
                            
                            if agent_response.error:
                                raise Exception(f"Agent {node_name} error: {agent_response.error}")
                            
                            agent_response_text = agent_response.text.strip()
                            
                            # Check for empty response - this is an error condition
                            if not agent_response_text:
                                error_msg = f"Agent {node_name} returned an empty response. This indicates an LLM error or configuration issue."
                                logger.error(f"❌ ORCHESTRATOR: {error_msg}")
                                logger.error(f"❌ ORCHESTRATOR: LLM Provider: {type(llm_provider).__name__}, Model: {agent_config.get('llm_model', 'unknown')}")
                                raise Exception(error_msg)
                            
                            logger.info(f"✅ ORCHESTRATOR: Agent {node_name} completed successfully - response length: {len(agent_response_text)} chars")
                            logger.info(f"🔍 DEBUG: Raw agent response for {node_name}: {agent_response_text[:200]}...")
                            
                            # CRITICAL FIX: Save agent message BEFORE reflection processing
                            # This ensures the message is recorded even if workflow pauses for reflection
                            messages.append({
                                'sequence': message_sequence,
                                'agent_name': node_name,
                                'agent_type': node_type,
                                'content': agent_response_text,
                                'message_type': 'chat',
                                'timestamp': timezone.now().isoformat(),
                                'response_time_ms': getattr(agent_response, 'response_time_ms', 0) if hasattr(agent_response, 'response_time_ms') else 0,
                                'token_count': getattr(agent_response, 'token_count', None) if hasattr(agent_response, 'token_count') else None,
                                'metadata': {
                                    'llm_provider': agent_config['llm_provider'],
                                    'llm_model': agent_config['llm_model'],
                                    'cost_estimate': getattr(agent_response, 'cost_estimate', None) if hasattr(agent_response, 'cost_estimate') else None
                                }
                            })
                            message_sequence += 1  # Increment for chronological ordering
                            
                            # Save messages to execution record
                            execution_record.messages_data = messages
                            await sync_to_async(execution_record.save)()
                            logger.info(f"💾 ORCHESTRATOR: Saved {node_name} message before reflection processing")
                            
                            # Track agent involvement and provider usage
                            agents_involved.add(node_name)
                            if hasattr(agent_response, 'response_time_ms'):
                                total_response_time += agent_response.response_time_ms
                            
                            # Track provider usage
                            if agent_config['llm_provider'] not in providers_used:
                                providers_used.append(agent_config['llm_provider'])
                            
                            # Handle reflection connections if present
                            try:
                                # Preserve original response before any reflection processing
                                original_agent_response = agent_response_text
                                
                                # First handle self-reflection
                                self_reflected_response = await self.reflection_handler.handle_reflection_connections(
                                    node, agent_response_text, graph_json, llm_provider
                                )
                                if self_reflected_response != agent_response_text:
                                    logger.info(f"🔄 SELF-REFLECTION: {node_name} response updated through self-reflection - new length: {len(self_reflected_response)} chars")
                                    agent_response_text = self_reflected_response
                                
                                # Check for cross-agent reflection connections
                                node_id = node.get('id')
                                
                                cross_agent_reflection_edges = []
                                for edge in graph_json.get('edges', []):
                                    if (edge.get('source') == node_id and 
                                        edge.get('type') == 'reflection' and 
                                        edge.get('target') != node_id):  # Cross-agent reflection
                                        cross_agent_reflection_edges.append(edge)
                                
                                # Process cross-agent reflections using original response
                                for reflection_edge in cross_agent_reflection_edges:
                                    logger.info(f"🔄 CROSS-AGENT-REFLECTION: Processing cross-agent reflection from {node_name}")
                                    
                                    reflection_result, updated_conversation = await self.reflection_handler.handle_cross_agent_reflection(
                                        node, original_agent_response, reflection_edge, graph_json, execution_record, conversation_history
                                    )
                                    
                                    # Check if we're waiting for human input in reflection
                                    if reflection_result == 'AWAITING_REFLECTION_INPUT':
                                        logger.info(f"👤 CROSS-AGENT-REFLECTION: Pausing workflow - awaiting human input for reflection")
                                        return {
                                            'status': 'paused_for_reflection_input',
                                            'conversation_history': updated_conversation,
                                            'message': f'Workflow paused - {execution_record.awaiting_human_input_agent} needs to provide reflection feedback',
                                            'execution_id': execution_record.execution_id
                                        }
                                    else:
                                        # Reflection completed successfully
                                        agent_response_text = reflection_result
                                        conversation_history = updated_conversation
                                        logger.info(f"✅ CROSS-AGENT-REFLECTION: Completed cross-agent reflection - final response length: {len(agent_response_text)} chars")
                                
                            except Exception as reflection_error:
                                logger.error(f"❌ REFLECTION: Error processing reflection for {node_name}: {reflection_error}")
                                import traceback
                                logger.error(f"❌ REFLECTION: Traceback: {traceback.format_exc()}")
                                # Continue with original response if reflection fails
                            
                            # CRITICAL FIX: Update conversation history with agent response
                            conversation_history += f"\n{node_name}: {agent_response_text}"
                            
                            # Store node output for multi-input support
                            executed_nodes[node_id] = agent_response_text
                            
                            # CRITICAL FIX: Save executed_nodes immediately to prevent duplicate execution
                            execution_record.executed_nodes = executed_nodes
                            
                            # CRITICAL FIX: Save updated conversation history to database
                            execution_record.conversation_history = conversation_history
                            await sync_to_async(execution_record.save)(update_fields=['executed_nodes', 'conversation_history'])
                            logger.info(f"💾 ORCHESTRATOR: Saved executed_nodes and conversation_history for {node_name} (node_id: {node_id})")
                            
                        except Exception as agent_error:
                            logger.error(f"❌ ORCHESTRATOR: Agent {node_name} failed: {agent_error}")
                            raise agent_error
                    
                elif node_type == 'EndNode':
                    # Handle end node
                    end_message = node_data.get('message', 'Workflow completed successfully.')
                    
                    # Store node output for completeness
                    executed_nodes[node_id] = end_message
                    
                    messages.append({
                        'sequence': message_sequence,
                        'agent_name': 'End',
                        'agent_type': 'EndNode',
                        'content': end_message,
                        'message_type': 'workflow_end',
                        'timestamp': timezone.now().isoformat(),
                        'response_time_ms': 0
                    })
                    message_sequence += 1  # Increment for chronological ordering
                    
                else:
                    logger.warning(f"⚠️ ORCHESTRATOR: Unknown node type {node_type}, skipping")
            
            # Calculate execution metrics
            end_time = timezone.now()
            duration = (end_time - start_time).total_seconds()
            
            # Update workflow execution stats using sync_to_async
            def update_workflow_stats():
                workflow.total_executions += 1
                workflow.successful_executions += 1
                workflow.last_executed_at = timezone.now()
                
                # Update average execution time
                if workflow.average_execution_time:
                    workflow.average_execution_time = (
                        (workflow.average_execution_time * (workflow.total_executions - 1) + duration) 
                        / workflow.total_executions
                    )
                else:
                    workflow.average_execution_time = duration
                
                workflow.save()
            
            await sync_to_async(update_workflow_stats)()
            
            # CRITICAL FIX: Get the latest messages_data from database first
            await sync_to_async(execution_record.refresh_from_db)()
            stored_messages = execution_record.messages_data or []
            logger.info(f"🔍 ORCHESTRATOR: Retrieved {len(stored_messages)} stored messages from database")
            
            # Find the highest sequence number in stored messages
            max_stored_sequence = max([msg.get('sequence', -1) for msg in stored_messages], default=-1)
            logger.info(f"🔍 ORCHESTRATOR: Max stored sequence: {max_stored_sequence}")
            
            # Merge messages: Start with stored messages, then add any new messages with updated sequences
            final_messages = stored_messages.copy()
            
            # Add workflow messages that aren't already stored, updating their sequences if needed
            for message in messages:
                message_sequence = message.get('sequence', -1)
                
                # Check if this message already exists in stored messages
                already_stored = any(
                    stored_msg.get('sequence') == message_sequence and 
                    stored_msg.get('agent_name') == message.get('agent_name') and
                    stored_msg.get('message_type') == message.get('message_type')
                    for stored_msg in stored_messages
                )
                
                if not already_stored:
                    # If this is a workflow message (like EndNode) that needs to be added after reflection
                    if message_sequence <= max_stored_sequence:
                        # Update sequence to come after all stored messages
                        message['sequence'] = max_stored_sequence + 1
                        max_stored_sequence += 1
                        logger.info(f"➕ ORCHESTRATOR: Updated sequence for {message.get('agent_name')} to {message['sequence']}")
                    
                    final_messages.append(message)
                    logger.info(f"➕ ORCHESTRATOR: Added missing message: {message.get('agent_name')} ({message.get('message_type')}) seq:{message.get('sequence')}")
            
            # Sort by sequence to maintain chronological order
            final_messages.sort(key=lambda x: x.get('sequence', 0))
            
            execution_record.messages_data = final_messages
            logger.info(f"✅ ORCHESTRATOR: Merged messages - final count: {len(final_messages)} messages")
            
            # Update execution record with final details
            execution_record.status = WorkflowExecutionStatus.COMPLETED
            execution_record.end_time = end_time
            execution_record.duration_seconds = duration
            execution_record.total_messages = len(final_messages)
            execution_record.total_agents_involved = len(agents_involved)
            execution_record.average_response_time_ms = total_response_time / len(agents_involved) if agents_involved else 0
            execution_record.providers_used = providers_used
            execution_record.conversation_history = conversation_history
            execution_record.result_summary = f"Successfully executed {len(execution_sequence)} nodes with {len(agents_involved)} agents"
            
            # Debug logging for execution completion
            logger.info(f"🔍 ORCHESTRATOR: Final execution stats - Messages: {len(final_messages)}, Agents: {len(agents_involved)}, Status: {execution_record.status}")
            logger.info(f"🔍 ORCHESTRATOR: Agents involved: {list(agents_involved)}")
            
            await sync_to_async(execution_record.save)()
            logger.info(f"✅ ORCHESTRATOR: Execution record saved with status: {execution_record.status}")
            logger.info(f"💾 ORCHESTRATOR: Saved final {len(final_messages)} messages to execution record")
            
            # ✅ SAVE MESSAGES TO DATABASE
            await self._save_messages_to_database(final_messages, execution_record)
            
            # Return execution results
            execution_result = {
                'execution_id': execution_id,
                'workflow_id': str(workflow_id),
                'workflow_name': workflow_name,
                'status': 'completed',
                'start_time': start_time.isoformat(),
                'end_time': end_time.isoformat(),
                'duration_seconds': duration,
                'total_messages': len(final_messages),
                'total_agents_involved': len(agents_involved),
                'average_response_time_ms': total_response_time / len(agents_involved) if agents_involved else 0,
                'providers_used': providers_used,
                'conversation_history': conversation_history,
                'messages': final_messages,
                'result_summary': f"Successfully executed {len(execution_sequence)} nodes with {len(agents_involved)} agents"
            }
            
            logger.info(f"✅ ORCHESTRATOR: REAL workflow execution completed successfully - {len(final_messages)} total messages logged")
            logger.info(f"📊 MESSAGE COUNT VERIFICATION: Expected ~{len(execution_sequence)} nodes, logged {len(final_messages)} messages")
            
            # Debug: Log all message types for verification
            message_types = [msg['message_type'] for msg in final_messages]
            agent_names = [msg['agent_name'] for msg in final_messages]
            logger.info(f"📋 MESSAGE TYPES: {message_types}")
            logger.info(f"👥 AGENT NAMES: {agent_names}")
            
            return execution_result
            
        except Exception as e:
            logger.error(f"❌ ORCHESTRATOR: REAL workflow execution failed: {e}")
            
            # Update workflow stats for failed execution using sync_to_async
            def update_failed_stats():
                workflow.total_executions += 1
                workflow.last_executed_at = timezone.now()
                workflow.save()
            
            await sync_to_async(update_failed_stats)()
            
            # Update existing execution record for failure
            end_time = timezone.now()
            duration = (end_time - start_time).total_seconds()
            
            execution_record.status = 'failed'
            execution_record.end_time = end_time
            execution_record.duration_seconds = duration
            execution_record.error_message = str(e)
            await sync_to_async(execution_record.save)()
            
            return {
                'execution_id': execution_id,
                'workflow_id': str(workflow_id),
                'workflow_name': workflow_name,
                'status': 'failed',
                'start_time': start_time.isoformat(),
                'end_time': end_time.isoformat(),
                'duration_seconds': duration,
                'total_messages': 0,
                'total_agents_involved': 0,
                'average_response_time_ms': 0,
                'providers_used': [],
                'conversation_history': '',
                'messages': [],
                'error_message': str(e),
                'result_summary': f"Execution failed: {str(e)}"
            }
    
    async def continue_workflow_execution(self, workflow, execution_record, execution_sequence, start_position, executed_nodes):
        """
        Continue workflow execution from a specific position (used after reflection completion)
        """
        logger.info(f"▶️ CONTINUE WORKFLOW: Resuming from position {start_position} with {len(execution_sequence) - start_position} remaining nodes")
        
        # Get workflow data
        workflow_id = await sync_to_async(lambda: workflow.workflow_id)()
        graph_json = await sync_to_async(lambda: workflow.graph_json)()
        project = await sync_to_async(lambda: workflow.project)()
        
        # Load existing state from execution record
        conversation_history = execution_record.conversation_history or ""
        messages = execution_record.messages_data or []
        agents_involved = set()
        total_response_time = 0
        providers_used = []
        
        # Initialize message sequence manager
        message_manager = MessageSequenceManager(messages)
        
        try:
            # Execute remaining nodes in sequence
            for node_index in range(start_position, len(execution_sequence)):
                # Check if execution has been stopped
                await sync_to_async(execution_record.refresh_from_db)()
                if execution_record.status == WorkflowExecutionStatus.STOPPED:
                    logger.info(f"🛑 CONTINUE WORKFLOW: Execution {execution_record.execution_id} has been stopped, terminating")
                    return {
                        'status': 'stopped',
                        'message': 'Workflow execution was stopped by user',
                        'execution_id': execution_record.execution_id
                    }
                
                node = execution_sequence[node_index]
                node_type = node.get('type')
                node_data = node.get('data', {})
                node_name = node_data.get('name', f'Node_{node.get("id", "unknown")}')
                node_id = node.get('id')
                
                # CRITICAL FIX: Refresh executed_nodes from database to get latest state
                executed_nodes = execution_record.executed_nodes or {}
                
                # CRITICAL FIX: Check if node has already been executed
                # Skip StartNode and EndNode as they don't have outputs in executed_nodes
                if node_type not in ['StartNode', 'EndNode'] and node_id in executed_nodes:
                    logger.info(f"⏭️ CONTINUE WORKFLOW: Skipping {node_name} (node_id: {node_id}) - already executed")
                    continue
                
                logger.info(f"🎯 CONTINUE WORKFLOW: Executing node {node_name} (type: {node_type}) at position {node_index}")
                
                if node_type in ['AssistantAgent', 'UserProxyAgent', 'GroupChatManager', 'DelegateAgent']:
                    # CRITICAL FIX: Only skip the specific UserProxyAgent that was just processed
                    # Check if this is the UserProxyAgent that just provided human input
                    if node_type == 'UserProxyAgent' and node_data.get('require_human_input', True):
                        # Refresh execution record to get latest state
                        await sync_to_async(execution_record.refresh_from_db)()
                        
                        # Check if this UserProxyAgent was the one that just provided input
                        awaiting_agent = execution_record.awaiting_human_input_agent or ""
                        human_input_context = execution_record.human_input_context or {}
                        reflection_source = human_input_context.get('reflection_source')
                        
                        # CRITICAL FIX: Only skip if:
                        # 1. This is a regular UserProxyAgent (not reflection) AND it matches the awaiting agent AND awaiting_agent is not empty
                        # 2. We should NOT skip UserProxyAgent nodes that are in the main workflow sequence after reflection completes
                        #    because the reflection context has been cleared
                        # ROOT CAUSE FIX: Use node_id instead of node_name for accurate matching
                        user_proxy_agent_id_from_context = execution_record.human_input_agent_id
                        should_skip = False
                        if not reflection_source and awaiting_agent and user_proxy_agent_id_from_context:
                            # Regular UserProxyAgent - skip only if it's the one that just provided input
                            # AND we're still in a regular human input context (not after reflection)
                            # CRITICAL FIX: Use node_id for matching, not node_name
                            if node_id == user_proxy_agent_id_from_context:
                                should_skip = True
                                logger.info(f"⏭️ CONTINUE WORKFLOW: Skipping UserProxyAgent {node_name} (node_id: {node_id}) - just processed regular human input")
                        elif reflection_source and awaiting_agent and user_proxy_agent_id_from_context:
                            # Reflection workflow - but if context is cleared, don't skip
                            # Only skip if we're still in the reflection context
                            # CRITICAL FIX: Use node_id for matching, not node_name
                            if node_id == user_proxy_agent_id_from_context:
                                # Check if this is still an active reflection context
                                # If human_input_context is empty or cleared, don't skip
                                if human_input_context and human_input_context.get('reflection_source'):
                                    should_skip = True
                                    logger.info(f"⏭️ CONTINUE WORKFLOW: Skipping UserProxyAgent {node_name} (node_id: {node_id}) - just processed reflection input")
                                else:
                                    # CRITICAL FIX: Check if UserProxyAgent was already executed via reflection
                                    # If it's in executed_nodes, skip it even if context is cleared
                                    if node_id in executed_nodes:
                                        should_skip = True
                                        logger.info(f"⏭️ CONTINUE WORKFLOW: Skipping UserProxyAgent {node_name} (node_id: {node_id}) - already executed via reflection")
                                    else:
                                        logger.info(f"✅ CONTINUE WORKFLOW: UserProxyAgent {node_name} (node_id: {node_id}) was in reflection but context cleared - will execute in main workflow")
                        
                        if should_skip:
                            continue
                        else:
                            # CRITICAL FIX: Check if this UserProxyAgent requires human input
                            # If it does, pause for human input instead of executing as regular agent
                            if node_data.get('require_human_input', True):
                                logger.info(f"👤 CONTINUE WORKFLOW: UserProxyAgent {node_name} requires human input - pausing workflow")
                                
                                # PAUSE WORKFLOW - Same as in execute_workflow
                                human_input_data = await self.human_input_handler.pause_for_human_input(
                                    workflow, node, executed_nodes, conversation_history, execution_record
                                )
                                return human_input_data  # Return paused state
                            else:
                                logger.info(f"✅ CONTINUE WORKFLOW: Processing UserProxyAgent {node_name} - not the one that was just processed, and doesn't require human input")
                    
                    # Handle agent nodes with real LLM calls
                    agent_config = {
                        'llm_provider': node_data.get('llm_provider', 'openai'),
                        'llm_model': node_data.get('llm_model', 'gpt-3.5-turbo'),
                        'temperature': node_data.get('temperature', 0.7)  # CRITICAL FIX: Include temperature to avoid KeyError
                    }
                    
                    # Get LLM provider for this agent
                    llm_provider = await self.llm_provider_manager.get_llm_provider(agent_config, project)
                    if not llm_provider:
                        raise Exception(f"Failed to create LLM provider for agent {node_name}")
                    
                    # Execute regular agent
                    logger.info(f"🤖 CONTINUE WORKFLOW: Executing regular agent {node_name} (type: {node_type})")
                    
                    # Find input sources
                    input_sources = self.workflow_parser.find_multiple_inputs_to_node(node_id, graph_json)
                    
                    # CRITICAL FIX: Validate all required inputs are available before executing
                    # This includes checking if reflection responses are in executed_nodes
                    if len(input_sources) > 0:
                        missing_inputs = []
                        for input_source in input_sources:
                            source_id = input_source.get('source_id')
                            source_name = input_source.get('name', source_id)
                            if source_id not in executed_nodes:
                                missing_inputs.append(f"{source_name} (node_id: {source_id})")
                        
                        if missing_inputs:
                            error_msg = f"Cannot execute {node_name}: Missing required inputs from {', '.join(missing_inputs)}. Available inputs: {list(executed_nodes.keys())}"
                            logger.warning(f"⏳ CONTINUE WORKFLOW: {error_msg} - waiting for dependencies")
                            # CRITICAL FIX: Don't raise exception, skip this node and continue
                            # It will be checked again in the next iteration when dependencies are satisfied
                            continue
                    
                    if len(input_sources) > 1:
                        # Multi-input mode
                        logger.info(f"📥 CONTINUE WORKFLOW: Agent {node_name} has {len(input_sources)} input sources - using multi-input mode")
                        aggregated_context = self.workflow_parser.aggregate_multiple_inputs(input_sources, executed_nodes)
                        # CRITICAL FIX: Use craft_conversation_prompt_with_docaware for multi-input (same as main execution)
                        combined_prompt = await self.chat_manager.craft_conversation_prompt_with_docaware(
                            aggregated_context, node, str(project.project_id), conversation_history
                        )
                    else:
                        # Single-input mode - CRITICAL FIX: Use proper prompt crafting
                        logger.info(f"📥 CONTINUE WORKFLOW: Agent {node_name} has {len(input_sources)} input source - using single-input mode")
                        combined_prompt = await self.chat_manager.craft_conversation_prompt(
                            conversation_history, node, str(project.project_id)
                        )
                    
                    # DEBUG: Log prompt content for troubleshooting
                    logger.info(f"🔍 CONTINUE WORKFLOW: Agent {node_name} prompt preview: {combined_prompt[:300]}...")
                    
                    # Make LLM call
                    start_time = timezone.now()
                    llm_response = await llm_provider.generate_response(prompt=combined_prompt)
                    end_time = timezone.now()
                    
                    if llm_response.error:
                        raise Exception(f"LLM error for agent {node_name}: {llm_response.error}")
                    
                    agent_response_text = llm_response.text.strip()
                    response_time_ms = int((end_time - start_time).total_seconds() * 1000)
                    
                    logger.info(f"✅ CONTINUE WORKFLOW: Agent {node_name} completed successfully - response length: {len(agent_response_text)} chars")
                    
                    # Track metrics
                    agents_involved.add(node_name)
                    total_response_time += response_time_ms
                    if agent_config['llm_provider'] not in providers_used:
                        providers_used.append(agent_config['llm_provider'])
                    
                    # Add message with proper sequence
                    message, sequence = message_manager.add_message(
                        agent_name=node_name,
                        agent_type=node_type,
                        content=agent_response_text,
                        message_type='assistant_response',
                        response_time_ms=response_time_ms,
                        token_count=llm_response.token_count,
                        metadata={
                            'llm_provider': agent_config['llm_provider'],
                            'llm_model': agent_config['llm_model'],
                            'temperature': agent_config.get('temperature', 0.7)  # CRITICAL FIX: Use .get() with default for safety
                        }
                    )
                    
                    # Store original response before any reflection processing
                    original_agent_response = agent_response_text
                    
                    # CRITICAL FIX: Check for cross-agent reflection connections
                    # This was missing from continue_workflow_execution, causing AI Assistant 2's
                    # reflection to User Proxy 2 to be skipped
                    try:
                        cross_agent_reflection_edges = []
                        for edge in graph_json.get('edges', []):
                            if (edge.get('source') == node_id and 
                                edge.get('type') == 'reflection' and 
                                edge.get('target') != node_id):  # Cross-agent reflection
                                cross_agent_reflection_edges.append(edge)
                        
                        if cross_agent_reflection_edges:
                            logger.info(f"🔄 CONTINUE WORKFLOW REFLECTION: Found {len(cross_agent_reflection_edges)} cross-agent reflection edges from {node_name}")
                        
                        # Process cross-agent reflections using original response
                        for reflection_edge in cross_agent_reflection_edges:
                            logger.info(f"🔄 CONTINUE WORKFLOW REFLECTION: Processing cross-agent reflection from {node_name}")
                            
                            reflection_result, updated_conversation = await self.reflection_handler.handle_cross_agent_reflection(
                                node, original_agent_response, reflection_edge, graph_json, execution_record, conversation_history
                            )
                            
                            # Check if we're waiting for human input in reflection
                            if reflection_result == 'AWAITING_REFLECTION_INPUT':
                                logger.info(f"👤 CONTINUE WORKFLOW REFLECTION: Pausing workflow - awaiting human input for reflection")
                                # Save current state before returning
                                execution_record.executed_nodes = executed_nodes
                                execution_record.messages_data = message_manager.get_messages()
                                execution_record.conversation_history = conversation_history
                                await sync_to_async(execution_record.save)()
                                return {
                                    'status': 'paused_for_reflection_input',
                                    'conversation_history': updated_conversation,
                                    'message': f'Workflow paused - {execution_record.awaiting_human_input_agent} needs to provide reflection feedback',
                                    'execution_id': execution_record.execution_id
                                }
                            else:
                                # Reflection completed successfully (no human input required)
                                agent_response_text = reflection_result
                                conversation_history = updated_conversation
                                logger.info(f"✅ CONTINUE WORKFLOW REFLECTION: Completed cross-agent reflection - final response length: {len(agent_response_text)} chars")
                    
                    except Exception as reflection_error:
                        logger.error(f"❌ CONTINUE WORKFLOW REFLECTION: Error processing reflection for {node_name}: {reflection_error}")
                        import traceback
                        logger.error(f"❌ CONTINUE WORKFLOW REFLECTION: Traceback: {traceback.format_exc()}")
                        # Continue with original response if reflection fails
                    
                    # Update conversation history and executed nodes
                    conversation_history += f"\n{node_name}: {agent_response_text}"
                    executed_nodes[node_id] = agent_response_text
                    
                    # CRITICAL FIX: Save executed_nodes to database after each agent execution
                    # This ensures downstream agents can access the output immediately
                    execution_record.executed_nodes = executed_nodes
                    await sync_to_async(execution_record.save)(update_fields=['executed_nodes'])
                    logger.info(f"💾 CONTINUE WORKFLOW: Saved executed_nodes for {node_name} (node_id: {node_id}) to database")
                    
                    # CRITICAL FIX: Save messages_data to database after each agent execution
                    # This ensures messages are persisted even if the workflow pauses or encounters an error
                    execution_record.messages_data = message_manager.get_messages()
                    execution_record.conversation_history = conversation_history
                    await sync_to_async(execution_record.save)(update_fields=['messages_data', 'conversation_history'])
                    logger.info(f"💾 CONTINUE WORKFLOW: Saved messages_data for {node_name} to database")
                    
                elif node_type == 'EndNode':
                    # Handle end node
                    end_message = node_data.get('message', 'Workflow completed successfully.')
                    executed_nodes[node_id] = end_message
                    
                    message, sequence = message_manager.add_message(
                        agent_name='End',
                        agent_type='EndNode',
                        content=end_message,
                        message_type='workflow_end'
                    )
            
            # Calculate final metrics
            end_time = timezone.now()
            duration = (end_time - execution_record.start_time).total_seconds()
            
            # Update execution record with completion
            execution_record.status = 'completed'
            execution_record.end_time = end_time
            execution_record.duration_seconds = duration
            execution_record.conversation_history = conversation_history
            execution_record.messages_data = message_manager.get_messages()
            execution_record.total_messages = len(message_manager.get_messages())
            execution_record.total_agents_involved = len(agents_involved)
            execution_record.providers_used = providers_used
            execution_record.executed_nodes = executed_nodes
            execution_record.result_summary = f"Continued workflow execution completed with {len(agents_involved)} agents"
            await sync_to_async(execution_record.save)()
            
            logger.info(f"✅ CONTINUE WORKFLOW: Execution completed successfully - {len(message_manager.get_messages())} total messages")
            
            return {
                'status': 'success',
                'message': 'Workflow execution continued and completed successfully',
                'execution_id': execution_record.execution_id,
                'updated_conversation': conversation_history,
                'workflow_completed': True,
                'total_agents': len(agents_involved),
                'final_response': agent_response_text if agents_involved else "Workflow completed"
            }
            
        except Exception as e:
            logger.error(f"❌ CONTINUE WORKFLOW: Continuation failed: {e}")
            
            # Update execution record for failure
            execution_record.status = 'failed'
            execution_record.end_time = timezone.now()
            execution_record.duration_seconds = (execution_record.end_time - execution_record.start_time).total_seconds()
            execution_record.error_message = str(e)
            execution_record.result_summary = f"Workflow continuation failed: {str(e)}"
            await sync_to_async(execution_record.save)()
            
            return {
                'status': 'failed',
                'message': f'Workflow continuation failed: {str(e)}',
                'execution_id': execution_record.execution_id,
                'error': str(e)
            }
    
    async def _save_messages_to_database(self, messages, execution_record):
        """
        Save messages to database with proper error handling and duplicate prevention
        """
        # Get existing message sequences to prevent duplicates
        from users.models import WorkflowExecutionMessage
        
        try:
            existing_sequences = await sync_to_async(set)(
                WorkflowExecutionMessage.objects.filter(
                    execution=execution_record
                ).values_list('sequence', flat=True)
            )
        except Exception as e:
            logger.error(f"❌ SAVE MESSAGE: Error getting existing sequences: {e}")
            existing_sequences = set()
        
        logger.info(f"💾 SAVE MESSAGE: Found {len(existing_sequences)} existing message sequences in database")
        
        saved_count = 0
        skipped_count = 0
        
        for message in messages:
            # Skip messages that already exist in database
            if message['sequence'] in existing_sequences:
                skipped_count += 1
                logger.debug(f"⏭️ SAVE MESSAGE: Skipping duplicate sequence {message['sequence']} ({message['agent_name']})")
                continue
                
            # Parse timestamp from message
            try:
                message_timestamp = datetime.fromisoformat(message['timestamp'].replace('Z', '+00:00'))
                if message_timestamp.tzinfo is None:
                    message_timestamp = timezone.make_aware(message_timestamp)
            except (KeyError, ValueError):
                message_timestamp = timezone.now()
            
            try:
                await sync_to_async(WorkflowExecutionMessage.objects.create)(
                    execution=execution_record,
                    sequence=message['sequence'],
                    agent_name=message['agent_name'],
                    agent_type=message['agent_type'],
                    content=message['content'],
                    message_type=message['message_type'],
                    timestamp=message_timestamp,
                    response_time_ms=message['response_time_ms'],
                    token_count=message.get('token_count'),
                    metadata=message.get('metadata', {})
                )
                saved_count += 1
                logger.debug(f"💾 SAVE MESSAGE: Saved sequence {message['sequence']} ({message['agent_name']})")
            except Exception as save_error:
                logger.error(f"❌ SAVE MESSAGE: Failed to save message {message['sequence']}: {save_error}")
        
        logger.info(f"💾 SAVE MESSAGE: Saved {saved_count} new messages, skipped {skipped_count} duplicates")
    
    def _find_ready_nodes(self, execution_sequence: List[Dict[str, Any]], executed_nodes: Dict[str, str],
                         graph_json: Dict[str, Any], current_index: int) -> List[Tuple[int, Dict[str, Any]]]:
        """
        Find all nodes that are ready to execute in parallel (all dependencies satisfied)
        
        Args:
            execution_sequence: Full execution sequence
            executed_nodes: Dictionary of executed node outputs
            graph_json: Full workflow graph
            current_index: Current position in execution sequence
            
        Returns:
            List of (index, node) tuples for nodes ready to execute in parallel
        """
        ready_nodes = []
        edges = graph_json.get('edges', [])
        
        # Build dependency map: node_id -> set of source node_ids it depends on
        dependency_map = {}
        nodes = graph_json.get('nodes', [])
        node_map = {node.get('id'): node for node in nodes}  # Create lookup for fast access
        
        for edge in edges:
            edge_type = edge.get('type', 'sequential')
            source_id = edge.get('source')
            target_id = edge.get('target')
            
            # Get target node to check if it's a UserProxyAgent
            target_node = node_map.get(target_id)
            is_user_proxy = (target_node and 
                            target_node.get('type') == 'UserProxyAgent' and
                            target_node.get('data', {}).get('require_human_input', True))
            
            # Include sequential edges for all nodes
            # Include reflection edges ONLY for UserProxyAgent nodes (they depend on reflection sources)
            if edge_type == 'sequential' or (edge_type == 'reflection' and is_user_proxy):
                if target_id not in dependency_map:
                    dependency_map[target_id] = set()
                dependency_map[target_id].add(source_id)
        
        # Check nodes from current_index onwards
        for i in range(current_index, len(execution_sequence)):
            node = execution_sequence[i]
            node_id = node.get('id')
            node_type = node.get('type')
            
            # Skip if already executed
            if node_id in executed_nodes:
                continue
            
            # Skip StartNode and EndNode (handled separately)
            if node_type in ['StartNode', 'EndNode']:
                continue
            
            # Check if all dependencies are satisfied
            dependencies = dependency_map.get(node_id, set())
            all_dependencies_satisfied = all(dep_id in executed_nodes for dep_id in dependencies)
            
            if all_dependencies_satisfied:
                # CRITICAL FIX: Check if this node depends on any node that's currently executing in parallel
                # If a dependency is in the current ready_nodes batch, this node should wait
                depends_on_parallel_node = False
                node_name = node.get('data', {}).get('name', node_id)
                for dep_id in dependencies:
                    # Check if this dependency is in the ready_nodes we're about to execute
                    # (This prevents nodes from being ready if their dependency is executing in parallel)
                    for ready_idx, ready_node in ready_nodes:
                        if ready_node.get('id') == dep_id:
                            depends_on_parallel_node = True
                            dep_name = ready_node.get('data', {}).get('name', dep_id)
                            logger.info(f"⏳ PARALLEL: Node {node_name} depends on {dep_name} which is executing in parallel - will wait")
                            break
                    if depends_on_parallel_node:
                        break
                
                if not depends_on_parallel_node:
                    ready_nodes.append((i, node))
                else:
                    # This node depends on a node that's executing in parallel, so it must wait
                    break
            else:
                # If this node's dependencies aren't satisfied, no nodes after it can be ready either
                # (due to topological sort ordering)
                break
        
        return ready_nodes
    
    async def _execute_nodes_in_parallel(self, ready_nodes: List[Tuple[int, Dict[str, Any]]],
                                        workflow, graph_json, executed_nodes, conversation_history,
                                        execution_record, messages, message_sequence, agents_involved,
                                        total_response_time, providers_used, project_id) -> List[Dict[str, Any]]:
        """
        Execute multiple nodes in parallel using asyncio.gather
        
        Args:
            ready_nodes: List of (index, node) tuples to execute
            workflow: Workflow instance
            graph_json: Full workflow graph
            executed_nodes: Current executed nodes state
            conversation_history: Current conversation history
            execution_record: Execution record
            messages: Current messages list
            message_sequence: Current message sequence number
            agents_involved: Set of agents involved
            total_response_time: Total response time so far
            providers_used: List of providers used
            project_id: Project ID
            
        Returns:
            List of execution results for each node
        """
        async def execute_single_node(node_tuple):
            """Execute a single node and return result"""
            idx, node = node_tuple
            node_id = node.get('id')
            node_type = node.get('type')
            node_data = node.get('data', {})
            node_name = node_data.get('name', f'Node_{node_id}')
            
            try:
                logger.info(f"🔀 PARALLEL: Executing {node_name} (type: {node_type})")
                
                # Handle UserProxyAgent separately (can't parallelize if requires human input)
                if node_type == 'UserProxyAgent' and node_data.get('require_human_input', True):
                    return {
                        'node_id': node_id,
                        'node_name': node_name,
                        'executed': False,
                        'paused': True,
                        'index': idx
                    }
                
                # Get LLM provider
                agent_config = {
                    'llm_provider': node_data.get('llm_provider', 'openai'),
                    'llm_model': node_data.get('llm_model', 'gpt-3.5-turbo')
                }
                
                project = await sync_to_async(lambda: workflow.project)()
                llm_provider = await self.llm_provider_manager.get_llm_provider(agent_config, project)
                if not llm_provider:
                    raise Exception(f"Failed to create LLM provider for agent {node_name}")
                
                # Get input sources - use a snapshot of executed_nodes to avoid race conditions
                # Each parallel execution gets its own snapshot
                input_sources = self.workflow_parser.find_multiple_inputs_to_node(node_id, graph_json)
                
                # Validate inputs
                if len(input_sources) > 0:
                    missing_inputs = []
                    for input_source in input_sources:
                        source_id = input_source.get('source_id')
                        if source_id not in executed_nodes:
                            missing_inputs.append(source_id)
                    if missing_inputs:
                        raise Exception(f"Missing required inputs: {missing_inputs}")
                
                # Craft prompt - use conversation_history snapshot
                # Note: In parallel execution, conversation_history may not include other parallel nodes yet
                # This is correct - each node sees the state before parallel execution started
                if len(input_sources) > 1:
                    aggregated_context = self.workflow_parser.aggregate_multiple_inputs(input_sources, executed_nodes)
                    prompt = await self.chat_manager.craft_conversation_prompt_with_docaware(
                        aggregated_context, node, str(project_id), conversation_history
                    )
                else:
                    prompt = await self.chat_manager.craft_conversation_prompt(
                        conversation_history, node, str(project_id)
                    )
                
                # Execute LLM call
                agent_response = await llm_provider.generate_response(prompt=prompt)
                
                if agent_response.error:
                    raise Exception(f"Agent {node_name} error: {agent_response.error}")
                
                agent_response_text = agent_response.text.strip()
                response_time_ms = getattr(agent_response, 'response_time_ms', 0) if hasattr(agent_response, 'response_time_ms') else 0
                
                logger.info(f"✅ PARALLEL: {node_name} completed - {len(agent_response_text)} chars, {response_time_ms}ms")
                
                return {
                    'node_id': node_id,
                    'node_name': node_name,
                    'executed': True,
                    'output': agent_response_text,
                    'response_time_ms': response_time_ms,
                    'token_count': getattr(agent_response, 'token_count', None),
                    'agents_involved': {node_name},
                    'providers_used': [agent_config['llm_provider']],
                    'metadata': {
                        'llm_provider': agent_config['llm_provider'],
                        'llm_model': agent_config['llm_model'],
                        'cost_estimate': getattr(agent_response, 'cost_estimate', None)
                    },
                    'index': idx
                }
            except Exception as e:
                logger.error(f"❌ PARALLEL: {node_name} failed: {e}")
                return {
                    'node_id': node_id,
                    'node_name': node_name,
                    'executed': False,
                    'error': str(e),
                    'index': idx
                }
        
        # Execute all nodes in parallel
        results = await asyncio.gather(*[execute_single_node(node_tuple) for node_tuple in ready_nodes])
        
        # Process results and create messages (in order of execution sequence)
        results.sort(key=lambda r: r['index'])
        next_sequence = message_sequence
        new_messages = []
        
        for result in results:
            if result.get('executed'):
                # Get node type from original node
                node_idx = result['index']
                node_type = next((n[1].get('type', 'AssistantAgent') for n in ready_nodes if n[0] == node_idx), 'AssistantAgent')
                
                # Create message for this node
                new_messages.append({
                    'sequence': next_sequence,
                    'agent_name': result['node_name'],
                    'agent_type': node_type,
                    'content': result['output'],
                    'message_type': 'chat',
                    'timestamp': timezone.now().isoformat(),
                    'response_time_ms': result.get('response_time_ms', 0),
                    'token_count': result.get('token_count'),
                    'metadata': result.get('metadata', {})
                })
                next_sequence += 1
        
        # Append new messages to existing messages list
        messages.extend(new_messages)
        
        # Update execution record with all messages
        execution_record.messages_data = messages
        await sync_to_async(execution_record.save)(update_fields=['messages_data'])
        
        logger.info(f"💾 PARALLEL: Saved {len(new_messages)} messages from parallel execution")
        
        return results
    
    def get_workflow_execution_summary(self, workflow: AgentWorkflow) -> Dict[str, Any]:
        """
        Get execution summary with recent execution history and messages
        """
        # Get recent executions from database
        recent_executions = WorkflowExecution.objects.filter(
            workflow=workflow
        ).order_by('-start_time')[:10]
        
        execution_history = []
        for execution in recent_executions:
            # Get messages for this execution
            messages = WorkflowExecutionMessage.objects.filter(
                execution=execution
            ).order_by('sequence')
            
            execution_data = {
                'execution_id': execution.execution_id,
                'status': execution.status,
                'start_time': execution.start_time.isoformat(),
                'end_time': execution.end_time.isoformat() if execution.end_time else None,
                'duration_seconds': execution.duration_seconds,
                'total_messages': execution.total_messages,
                'total_agents_involved': execution.total_agents_involved,
                'providers_used': execution.providers_used,
                'result_summary': execution.result_summary,
                'conversation_history': execution.conversation_history,
                'messages': [
                    {
                        'sequence': msg.sequence,
                        'agent_name': msg.agent_name,
                        'agent_type': msg.agent_type,
                        'content': msg.content,
                        'message_type': msg.message_type,
                        'timestamp': msg.timestamp.isoformat(),
                        'response_time_ms': msg.response_time_ms,
                        'token_count': msg.token_count,
                        'metadata': msg.metadata
                    }
                    for msg in messages
                ]
            }
            execution_history.append(execution_data)
        
        return {
            'workflow_id': str(workflow.workflow_id),
            'workflow_name': workflow.name,
            'total_executions': workflow.total_executions,
            'successful_executions': workflow.successful_executions,
            'average_execution_time': workflow.average_execution_time,
            'last_executed_at': workflow.last_executed_at.isoformat() if workflow.last_executed_at else None,
            'recent_executions': execution_history
        }