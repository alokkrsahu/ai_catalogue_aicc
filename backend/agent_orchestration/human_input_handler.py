"""
Human Input Handler
==================

Handles human input pause/resume functionality for conversation orchestration.
"""

import logging
from typing import Dict, List, Any, Optional
from django.utils import timezone
from asgiref.sync import sync_to_async

from users.models import WorkflowExecution, WorkflowExecutionMessage, WorkflowExecutionStatus, HumanInputInteraction

logger = logging.getLogger('conversation_orchestrator')


class HumanInputHandler:
    """
    Handles workflow pause/resume for human input
    """
    
    def __init__(self, workflow_parser, docaware_handler, llm_provider_manager, reflection_handler):
        self.workflow_parser = workflow_parser
        self.docaware_handler = docaware_handler
        self.llm_provider_manager = llm_provider_manager
        self.reflection_handler = reflection_handler
    
    async def pause_for_human_input(self, workflow, node, executed_nodes, conversation_history, execution_record):
        """
        Pause workflow execution and prepare human input interface data
        
        This is called when a UserProxyAgent with require_human_input=True is encountered
        """
        node_id = node.get('id')
        node_name = node.get('data', {}).get('name', 'User Proxy')
        node_data = node.get('data', {})
        
        logger.info(f"⏸️ HUMAN INPUT: Pausing workflow at {node_name} ({node_id})")
        
        # Find input sources (connected agents that feed into this UserProxyAgent)
        input_sources = self.workflow_parser.find_multiple_inputs_to_node(node_id, workflow.graph_json)
        aggregated_context = self.workflow_parser.aggregate_multiple_inputs(input_sources, executed_nodes)
        
        logger.info(f"📥 HUMAN INPUT: Found {len(input_sources)} input sources for {node_name}")
        
        # Update execution record to paused state
        await sync_to_async(self.update_execution_for_human_input)(
            execution_record, node_id, node_name, aggregated_context
        )
        
        return {
            'status': 'awaiting_human_input',
            'execution_id': execution_record.execution_id,
            'agent_name': node_name,
            'agent_id': node_id,
            'input_context': aggregated_context,
            'conversation_history': conversation_history,
            'message': f'Workflow paused - {node_name} requires human input'
        }
    
    def update_execution_for_human_input(self, execution_record, agent_id, agent_name, context):
        """
        Update execution record to indicate human input required (sync function)
        """
        execution_record.human_input_required = True
        execution_record.awaiting_human_input_agent = agent_name
        execution_record.human_input_agent_id = agent_id
        execution_record.human_input_context = {
            'agent_id': agent_id,
            'input_sources': context['all_inputs'],
            'input_count': context['input_count'],
            'primary_input': context['primary_input']
        }
        execution_record.human_input_requested_at = timezone.now()
        execution_record.save()
        
        logger.info(f"💾 HUMAN INPUT: Updated execution record {execution_record.execution_id} for human input")
    
    async def resume_workflow_with_human_input(self, execution_id: str, human_input: str, user):
        """
        Resume paused workflow with human input
        """
        logger.info(f"▶️ HUMAN INPUT: Resuming workflow {execution_id} with human input")
        
        # Load paused execution
        execution_record = await sync_to_async(WorkflowExecution.objects.get)(
            execution_id=execution_id,
            human_input_required=True
        )
        
        # Record human input interaction
        await sync_to_async(HumanInputInteraction.objects.create)(
            execution=execution_record,
            agent_name=execution_record.awaiting_human_input_agent,
            agent_id=execution_record.human_input_agent_id,
            input_messages=execution_record.human_input_context.get('input_sources', []),
            human_response=human_input,
            conversation_context=execution_record.conversation_history,
            requested_at=execution_record.human_input_requested_at,
            input_sources_count=execution_record.human_input_context.get('input_count', 0),
            workflow_paused_at_sequence=execution_record.total_messages,
            aggregated_input_summary=f"{execution_record.human_input_context.get('input_count', 0)} input sources processed"
        )
        
        # Update execution state
        execution_record.human_input_required = False
        execution_record.human_input_received_at = timezone.now()
        await sync_to_async(execution_record.save)()
        
        logger.info(f"✅ HUMAN INPUT: Recorded interaction and updated execution state")
        
        # Resume workflow execution from where we left off
        return await self.continue_workflow_from_resumed_state(execution_record, human_input)
    
    async def continue_workflow_from_resumed_state(self, execution_record, human_input):
        """
        Continue workflow execution after human input is provided
        """
        logger.info(f"🚀 HUMAN INPUT: Resuming workflow execution for {execution_record.execution_id}")
        
        # Get workflow and rebuild execution state
        workflow = await sync_to_async(lambda: execution_record.workflow)()
        
        # Add human input to conversation history
        updated_conversation = execution_record.conversation_history + f"\n{execution_record.awaiting_human_input_agent}: {human_input}"
        
        # CRITICAL FIX: Add human input message to messages array for proper conversation history display
        messages = execution_record.messages_data or []
        
        # Get the next sequence number
        next_sequence = len(messages)
        
        # Add human input message
        messages.append({
            'sequence': next_sequence,
            'agent_name': execution_record.awaiting_human_input_agent,
            'agent_type': 'UserProxyAgent',
            'content': human_input,
            'message_type': 'human_input',
            'timestamp': timezone.now().isoformat(),
            'response_time_ms': 0,
            'metadata': {
                'input_method': 'reflection_feedback' if execution_record.human_input_context.get('reflection_source') else 'human_input',
                'reflection_source': execution_record.human_input_context.get('reflection_source'),
                'iteration': execution_record.human_input_context.get('iteration')
            }
        })
        
        # Update the execution record with human input in conversation and messages
        execution_record.conversation_history = updated_conversation
        execution_record.messages_data = messages
        await sync_to_async(execution_record.save)()
        
        # Continue workflow execution from the paused state
        try:
            # Check if this is a reflection workflow that needs special handling
            reflection_source = execution_record.human_input_context.get('reflection_source')
            if reflection_source:
                logger.info(f"🔄 WORKFLOW RESUME: This is a reflection workflow, calling reflection handler")
                
                # This is a reflection workflow - call the reflection handler to complete the reflection
                final_response, updated_conversation = await self.reflection_handler.resume_reflection_workflow_execution(
                    execution_record, human_input
                )
                
                logger.info(f"✅ REFLECTION RESUME: Reflection completed with final response length: {len(final_response)} chars")
                
                # CRITICAL FIX: Check if there are remaining agents in the execution sequence
                workflow = await sync_to_async(lambda: execution_record.workflow)()
                graph_json = await sync_to_async(lambda: workflow.graph_json)()
                execution_sequence = self.workflow_parser.parse_workflow_graph(graph_json)
                
                # Find current position in execution sequence based on executed nodes
                executed_nodes = execution_record.executed_nodes or {}
                current_position = 0
                
                # Find the position after reflection source agent
                for i, node in enumerate(execution_sequence):
                    node_name = node.get('data', {}).get('name', f'Node_{node.get("id", "unknown")}')
                    if node_name == reflection_source:
                        current_position = i + 1  # Move to next agent after reflection source
                        break
                
                remaining_agents = execution_sequence[current_position:]
                logger.info(f"🔍 REFLECTION RESUME: Found {len(remaining_agents)} remaining agents after reflection: {[agent.get('data', {}).get('name') for agent in remaining_agents]}")
                
                if remaining_agents:
                    # Continue workflow execution with remaining agents
                    logger.info(f"▶️ REFLECTION RESUME: Continuing workflow execution from position {current_position}")
                    
                    # Import workflow executor to continue execution
                    from .workflow_executor import WorkflowExecutor
                    from .chat_manager import ChatManager
                    
                    # Create chat manager instance (needed for workflow executor)
                    chat_manager = ChatManager(
                        self.llm_provider_manager,
                        self.workflow_parser,
                        self.docaware_handler
                    )
                    
                    # Create workflow executor instance
                    workflow_executor = WorkflowExecutor(
                        self.workflow_parser,
                        self.llm_provider_manager,
                        chat_manager,
                        self.docaware_handler,
                        self,  # human_input_handler
                        self.reflection_handler
                    )
                    
                    # Continue execution from current position
                    continuation_result = await workflow_executor.continue_workflow_execution(
                        workflow, execution_record, execution_sequence, current_position, executed_nodes
                    )
                    
                    return continuation_result
                else:
                    # No remaining agents - mark workflow as completed
                    logger.info(f"🏁 REFLECTION RESUME: No remaining agents, marking workflow as completed")
                    
                    execution_record.status = 'completed'
                    execution_record.end_time = timezone.now()
                    
                    # CRITICAL: Calculate duration_seconds for proper execution time display
                    if execution_record.start_time and execution_record.end_time:
                        duration = (execution_record.end_time - execution_record.start_time).total_seconds()
                        execution_record.duration_seconds = duration
                        logger.info(f"📊 REFLECTION COMPLETE: Calculated duration: {duration:.2f} seconds")
                    
                    execution_record.total_messages = len(execution_record.messages_data or [])
                    execution_record.total_agents_involved = len(set(msg.get('agent_name') for msg in (execution_record.messages_data or []) if msg.get('agent_type') not in ['StartNode', 'EndNode']))
                    execution_record.result_summary = f"Reflection workflow completed: {reflection_source} → {execution_record.awaiting_human_input_agent}"
                    await sync_to_async(execution_record.save)()
                    
                    return {
                        'status': 'success',
                        'message': 'Reflection workflow completed successfully',
                        'execution_id': execution_record.execution_id,
                        'updated_conversation': updated_conversation,
                        'workflow_completed': True,
                        'final_response': final_response
                    }
            else:
                # This is a regular human input workflow - continue with normal workflow execution
                # For now, mark as completed since we don't have the continue_workflow_from_node method
                logger.info(f"🔄 WORKFLOW RESUME: Regular human input workflow - marking as completed")
                
                execution_record.status = 'completed'
                execution_record.end_time = timezone.now()
                
                # CRITICAL: Calculate duration_seconds for proper execution time display
                if execution_record.start_time and execution_record.end_time:
                    duration = (execution_record.end_time - execution_record.start_time).total_seconds()
                    execution_record.duration_seconds = duration
                    logger.info(f"📊 WORKFLOW COMPLETE: Calculated duration: {duration:.2f} seconds")
                
                execution_record.total_messages = len(execution_record.messages_data or [])
                
                # CRITICAL FIX: Calculate total_agents_involved from messages_data
                agent_names = set()
                for msg in (execution_record.messages_data or []):
                    agent_type = msg.get('agent_type', '')
                    # Count only actual agents, not system nodes
                    if agent_type not in ['StartNode', 'EndNode']:
                        agent_names.add(msg.get('agent_name'))
                execution_record.total_agents_involved = len(agent_names)
                logger.info(f"📊 WORKFLOW COMPLETE: Calculated {len(agent_names)} agents involved: {list(agent_names)}")
                
                execution_record.result_summary = f"Human input workflow completed"
                await sync_to_async(execution_record.save)()
                
                return {
                    'status': 'success',
                    'message': 'Human input workflow completed successfully',
                    'execution_id': execution_record.execution_id,
                    'updated_conversation': updated_conversation,
                    'workflow_completed': True
                }
            
        except Exception as e:
            logger.error(f"❌ WORKFLOW RESUME: Failed to continue workflow: {e}")
            import traceback
            logger.error(f"❌ WORKFLOW RESUME: Traceback: {traceback.format_exc()}")
            return {
                'status': 'partial_success',
                'message': f'Human input recorded but workflow continuation failed: {str(e)}',
                'execution_id': execution_record.execution_id,
                'updated_conversation': updated_conversation,
                'error': str(e)
            }
    
    async def pause_for_human_input_reflection(self, execution_record, target_node, reflection_context, conversation_history):
        """
        Pause workflow execution for human input during cross-agent reflection
        """
        target_name = target_node.get('data', {}).get('name', 'User Proxy Agent')
        
        logger.info(f"👤 REFLECTION HUMAN INPUT: Pausing for human input from {target_name}")
        
        # Log pause for internal tracking but don't add to visible messages_data
        # These workflow pause messages should not appear in execution history
        reflection_source = reflection_context.get('reflection_source', 'Unknown')
        iteration_num = reflection_context.get('iteration', 1)
        
        logger.info(f"📝 REFLECTION HUMAN INPUT: Workflow paused for reflection input from {target_name}")
        logger.info(f"📝 REFLECTION HUMAN INPUT: Reflection source: {reflection_source}, Iteration: {iteration_num}")
        
        # Update execution record for human input during reflection
        execution_record.human_input_required = True
        execution_record.awaiting_human_input_agent = target_name
        execution_record.human_input_agent_id = target_node.get('id')
        execution_record.human_input_context = reflection_context
        execution_record.human_input_requested_at = timezone.now()
        execution_record.conversation_history = conversation_history
        await sync_to_async(execution_record.save)()
        
        logger.info(f"💾 REFLECTION HUMAN INPUT: Updated execution record for reflection human input")

    async def process_userproxy_docaware(self, userproxy_node, human_input, project_id, execution_record):
        """
        Process UserProxy agent human input with DocAware functionality
        Uses human input as the query for document search and then summarizes with LLM
        """
        logger.info(f"📚 USERPROXY DOCAWARE: Processing human input '{human_input[:100]}...' for UserProxy agent")
        
        node_data = userproxy_node.get('data', {})
        
        # Get DocAware configuration from the node
        search_method = node_data.get('search_method', 'semantic_search')
        search_parameters = node_data.get('search_parameters', {})
        content_filter = node_data.get('content_filter', '')
        
        # Get LLM configuration for summarization
        llm_provider = node_data.get('llm_provider', 'openai')
        llm_model = node_data.get('llm_model', 'gpt-3.5-turbo')
        system_message = node_data.get('system_message', 'You are a helpful assistant that summarizes retrieved documents to answer user questions.')
        temperature = node_data.get('temperature', 0.3)
        max_tokens = node_data.get('max_tokens', 1024)
        
        logger.info(f"📚 USERPROXY DOCAWARE: Configuration - search_method: {search_method}, llm_provider: {llm_provider}")
        
        try:
            # 1. Perform DocAware search using human input as query
            from .docaware import EnhancedDocAwareAgentService
            docaware_service = EnhancedDocAwareAgentService()
            
            logger.info(f"📚 USERPROXY DOCAWARE: Performing document search with query: {human_input}")
            
            # Execute the document search
            search_results = await sync_to_async(docaware_service.execute_search)(
                project_id=project_id,
                search_method=search_method,
                search_parameters=search_parameters,
                query=human_input,
                content_filter=content_filter
            )
            
            if not search_results or not search_results.get('success'):
                logger.warning(f"⚠️ USERPROXY DOCAWARE: No search results or search failed")
                return f"I searched for information about '{human_input}' but couldn't find relevant documents."
            
            retrieved_documents = search_results.get('results', [])
            logger.info(f"📚 USERPROXY DOCAWARE: Found {len(retrieved_documents)} relevant documents")
            
            if not retrieved_documents:
                return f"I searched for information about '{human_input}' but no relevant documents were found."
            
            # 2. Format retrieved documents for LLM
            context_text = "\n\n=== RETRIEVED DOCUMENTS ===\n"
            for i, doc in enumerate(retrieved_documents[:5], 1):  # Limit to top 5 documents
                source = doc.get('source', 'Unknown source')
                content = doc.get('content_preview', doc.get('content', ''))[:1000]  # Limit content length
                score = doc.get('score', 0)
                
                context_text += f"\nDocument {i} (Source: {source}, Relevance: {score:.2f}):\n{content}\n"
            
            context_text += "\n=== END RETRIEVED DOCUMENTS ===\n"
            
            # 3. Create LLM provider for summarization
            agent_config = {
                'llm_provider': llm_provider,
                'llm_model': llm_model,
                'max_tokens': max_tokens,
                'temperature': temperature
            }
            
            llm_provider_instance = self.llm_provider_manager.get_llm_provider(agent_config)
            if not llm_provider_instance:
                logger.error(f"❌ USERPROXY DOCAWARE: Failed to create LLM provider for summarization")
                return f"I found relevant documents about '{human_input}' but couldn't process them due to LLM configuration issues."
            
            # 4. Create prompt for LLM summarization
            summarization_prompt = f"""{system_message}

The user asked: "{human_input}"

I have retrieved the following relevant documents from the project knowledge base:

{context_text}

Please provide a comprehensive and helpful response to the user's question based on the retrieved documents. If the documents don't contain sufficient information to answer the question, please say so clearly.

Response:"""
            
            logger.info(f"📚 USERPROXY DOCAWARE: Generating LLM summary with {llm_provider} model {llm_model}")
            
            # 5. Generate LLM response
            llm_response = await llm_provider_instance.generate_response(
                prompt=summarization_prompt,
                temperature=temperature
            )
            
            if llm_response.error:
                logger.error(f"❌ USERPROXY DOCAWARE: LLM generation failed: {llm_response.error}")
                return f"I found relevant documents about '{human_input}' but encountered an error while processing them."
            
            summary_result = llm_response.text.strip()
            logger.info(f"✅ USERPROXY DOCAWARE: Successfully generated summary - length: {len(summary_result)} chars")
            
            return summary_result
            
        except Exception as e:
            logger.error(f"❌ USERPROXY DOCAWARE: Processing failed: {e}")
            import traceback
            logger.error(f"❌ USERPROXY DOCAWARE: Traceback: {traceback.format_exc()}")
            return f"I attempted to search for information about '{human_input}' but encountered an error during processing."