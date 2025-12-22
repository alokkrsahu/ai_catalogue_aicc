"""
Workflow Deployment Executor
Optimized execution engine for public-facing workflow deployments
"""
import logging
import copy
import time
from typing import Dict, Any, Optional
from asgiref.sync import sync_to_async

from .conversation_orchestrator import ConversationOrchestrator
from .models import WorkflowDeployment

logger = logging.getLogger('workflow_deployment')


class WorkflowDeploymentExecutor:
    """
    Executor for public-facing workflow deployments
    Optimized for public access (no human input pauses, no reflection delays)
    """
    
    def __init__(self):
        """Initialize the deployment executor"""
        self.orchestrator = ConversationOrchestrator()
        logger.info("🚀 DEPLOYMENT EXECUTOR: Initialized")
    
    async def execute_deployment_workflow(
        self,
        deployment: WorkflowDeployment,
        conversation_history: str,
        session_id: Optional[str] = None,
        execution_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute a deployed workflow with full conversation history
        
        Args:
            deployment: WorkflowDeployment instance
            conversation_history: Full conversation history as formatted string
            session_id: Optional session ID for conversation tracking
            execution_id: Optional execution ID for linking to DeploymentExecution
            
        Returns:
            Dict containing execution results
        """
        start_time = time.time()
        
        try:
            # Safely fetch related objects in async context
            workflow = await sync_to_async(lambda: deployment.workflow)()
            project = await sync_to_async(lambda: deployment.project)()
            workflow_name = await sync_to_async(lambda: workflow.name if workflow else 'Unknown workflow')()
            project_name = await sync_to_async(lambda: project.name if project else 'Unknown project')()
            
            logger.info(f"🚀 DEPLOYMENT: Executing workflow {workflow_name} for project {project_name}")
            
            # Get workflow graph and make a deep copy to avoid modifying original
            graph_json = copy.deepcopy(await sync_to_async(lambda: workflow.graph_json)())
            
            # Find Start node and replace prompt with full conversation history
            start_node_modified = False
            for node in graph_json.get('nodes', []):
                if node.get('type') == 'StartNode':
                    node_data = node.get('data', {})
                    if isinstance(node_data, dict):
                        node_data['prompt'] = conversation_history
                        node['data'] = node_data
                        start_node_modified = True
                        logger.info(f"🔄 DEPLOYMENT: Replaced Start node prompt with conversation history ({len(conversation_history)} chars)")
                        break
            
            if not start_node_modified:
                logger.warning(f"⚠️ DEPLOYMENT: No StartNode found in workflow {workflow.workflow_id}")
                return {
                    'status': 'error',
                    'error': 'Workflow does not contain a Start node',
                    'execution_time_ms': int((time.time() - start_time) * 1000)
                }
            
            # Temporarily set the modified graph
            original_graph = await sync_to_async(lambda: workflow.graph_json)()
            workflow.graph_json = graph_json
            
            try:
                # Execute workflow with modified graph
                # Use a system user or the deployment creator for execution context
                executed_by = await sync_to_async(lambda: deployment.created_by)()
                
                execution_result = await self.orchestrator.execute_workflow(workflow, executed_by)
                
                # Extract End node messages as response
                end_node_output = self._extract_end_node_output(execution_result, graph_json)
                
                execution_time_ms = int((time.time() - start_time) * 1000)
                
                logger.info(f"✅ DEPLOYMENT: Workflow execution completed in {execution_time_ms}ms")
                
                # Get execution_id from execution_result or use provided one
                result_execution_id = execution_result.get('execution_id')
                
                return {
                    'status': 'success',
                    'response': end_node_output,
                    'execution_time_ms': execution_time_ms,
                    'workflow_name': await sync_to_async(lambda: workflow.name)(),
                    'execution_id': result_execution_id,
                    'conversation_history': execution_result.get('conversation_history', '')
                }
            finally:
                # Always restore original graph, even if execution fails
                workflow.graph_json = original_graph
                
        except Exception as e:
            execution_time_ms = int((time.time() - start_time) * 1000)
            logger.error(f"❌ DEPLOYMENT: Workflow execution failed: {e}", exc_info=True)
            return {
                'status': 'error',
                'error': str(e),
                'execution_time_ms': execution_time_ms
            }
    
    def _extract_end_node_output(
        self,
        execution_result: Dict[str, Any],
        workflow_graph: Dict[str, Any]
    ) -> str:
        """
        Extract aggregated output from End nodes
        
        Args:
            execution_result: Result from workflow execution
            workflow_graph: Original workflow graph
            
        Returns:
            Aggregated End node output as string
        """
        try:
            # Use the same approach as evaluation: take the single predecessor of the End node
            messages = execution_result.get('messages', [])
            if not messages:
                logger.warning("⚠️ DEPLOYMENT: No messages in execution result")
                # Try to get from conversation_history as last resort
                conv_history = execution_result.get('conversation_history', '')
                if conv_history:
                    logger.info("✅ DEPLOYMENT: Using conversation_history as fallback")
                    return conv_history
                return ''

            logger.debug(f"🔍 DEPLOYMENT: Processing {len(messages)} messages from execution result")

            # Find End node(s)
            end_nodes = [node for node in workflow_graph.get('nodes', []) if node.get('type') == 'EndNode']
            if not end_nodes:
                logger.warning("⚠️ DEPLOYMENT: No End node found in workflow graph")
                # Fallback: last chat message (preferred over result_summary)
                fallback = self._get_last_chat_message(execution_result)
                if fallback:
                    return fallback
                # Last resort: conversation_history
                conv_history = execution_result.get('conversation_history', '')
                if conv_history:
                    return conv_history
                return ''

            # For now we assume a single End node is used for deployment
            end_node = end_nodes[0]
            end_node_id = end_node.get('id')

            # Find predecessor node IDs (nodes with edges pointing to End node)
            predecessor_node_ids = [
                edge.get('source')
                for edge in workflow_graph.get('edges', [])
                if edge.get('target') == end_node_id
            ]

            # If multiple predecessors, log a warning (UI should prevent this)
            if len(predecessor_node_ids) != 1:
                logger.warning(f"⚠️ DEPLOYMENT: Expected exactly 1 input to End node, found {len(predecessor_node_ids)}. Falling back to last chat message.")
                fallback = self._get_last_chat_message(execution_result)
                if fallback:
                    return fallback
                # Last resort: conversation_history
                conv_history = execution_result.get('conversation_history', '')
                if conv_history:
                    return conv_history
                return ''

            predecessor_id = predecessor_node_ids[0]

            # Map node IDs to names
            node_id_to_name = {
                node['id']: node.get('data', {}).get('name', node.get('id'))
                for node in workflow_graph.get('nodes', [])
            }
            predecessor_name = node_id_to_name.get(predecessor_id, predecessor_id)

            # Find the last message from the predecessor agent
            end_node_messages = []
            logger.info(f"🔍 DEPLOYMENT: Looking for messages from predecessor '{predecessor_name}' (ID: {predecessor_id})")
            logger.info(f"🔍 DEPLOYMENT: Total messages to check: {len(messages)}")
            
            # Log all message agent names and content preview for debugging
            all_agent_names = [msg.get('agent_name', 'N/A') for msg in messages if isinstance(msg, dict)]
            logger.info(f"🔍 DEPLOYMENT: Available agent names in messages: {all_agent_names}")
            
            # Log message details for debugging
            for idx, msg in enumerate(messages):
                if isinstance(msg, dict):
                    agent_name = msg.get('agent_name', 'N/A')
                    content_preview = (msg.get('content', '') or msg.get('message', ''))[:50]
                    logger.debug(f"🔍 DEPLOYMENT: Message {idx}: agent_name='{agent_name}', content_preview='{content_preview}...'")
            
            for msg in messages:
                if not isinstance(msg, dict):
                    continue
                agent_name = msg.get('agent_name', '')
                agent_type = msg.get('agent_type', '')
                content = msg.get('content', '') or msg.get('message', '')
                
                # Match by agent name (exact match first)
                if agent_name == predecessor_name:
                    if content and content.strip():  # Ensure content is not empty
                        end_node_messages.append(content)
                        logger.info(f"✅ DEPLOYMENT: Found message from '{agent_name}': {content[:100]}...")
                
                # Also try case-insensitive matching
                elif agent_name.lower() == predecessor_name.lower():
                    if content and content.strip():
                        end_node_messages.append(content)
                        logger.info(f"✅ DEPLOYMENT: Found message from '{agent_name}' (case-insensitive match): {content[:100]}...")

            if end_node_messages:
                chosen = end_node_messages[-1].strip()
                if chosen:
                    logger.info(f"✅ DEPLOYMENT: Using End node input from predecessor '{predecessor_name}': {chosen[:100]}...")
                    return chosen
                else:
                    logger.warning(f"⚠️ DEPLOYMENT: Found messages but content is empty")

            # As a fallback, try to find the last agent message (before End node)
            logger.warning(f"⚠️ DEPLOYMENT: No messages found for End node predecessor '{predecessor_name}', trying fallback")
            
            # Get all non-End, non-Start messages in reverse order
            agent_messages = [
                msg for msg in reversed(messages)
                if isinstance(msg, dict)
                and msg.get('agent_type') not in ['EndNode', 'StartNode']
                and msg.get('agent_name') not in ['End', 'Start']
                and (msg.get('content') or msg.get('message'))
            ]
            
            logger.info(f"🔍 DEPLOYMENT: Found {len(agent_messages)} agent messages as fallback candidates")
            
            if agent_messages:
                # Try each message until we find one with actual content
                for msg in agent_messages:
                    fallback_content = msg.get('content') or msg.get('message', '')
                    if fallback_content and fallback_content.strip():
                        logger.info(f"✅ DEPLOYMENT: Using agent message from '{msg.get('agent_name', 'unknown')}' as fallback: {fallback_content[:100]}...")
                        return fallback_content.strip()
                
                logger.warning(f"⚠️ DEPLOYMENT: Agent messages found but all have empty content")
            
            # Final fallback: use last chat message
            fallback = self._get_last_chat_message(execution_result)
            if fallback:
                logger.info(f"✅ DEPLOYMENT: Using _get_last_chat_message fallback: {fallback[:100]}...")
                return fallback
            
            # Last resort: try to extract last response from conversation_history
            conv_history = execution_result.get('conversation_history', '')
            if conv_history:
                logger.warning(f"⚠️ DEPLOYMENT: Attempting to extract response from conversation_history")
                # Try to extract the last assistant response from conversation_history
                # Format is typically: "Assistant: ...\nUser: ...\nAssistant: ..."
                last_assistant_response = self._extract_last_assistant_from_history(conv_history)
                if last_assistant_response:
                    logger.info(f"✅ DEPLOYMENT: Extracted last assistant response from conversation_history: {last_assistant_response[:100]}...")
                    return last_assistant_response
                # If extraction fails, return the whole history (better than nothing)
                logger.warning(f"⚠️ DEPLOYMENT: Could not extract response, returning full conversation_history")
                return conv_history
            
            # Only return result_summary if absolutely nothing else is available
            result_summary = execution_result.get('result_summary', '')
            if result_summary:
                logger.error(f"❌ DEPLOYMENT: All extraction methods failed, returning result_summary (this should not happen): {result_summary}")
            return result_summary

        except Exception as e:
            logger.error(f"❌ DEPLOYMENT: Error extracting End node output: {e}", exc_info=True)
            # Fallback to last assistant/chat message
            fallback = self._get_last_chat_message(execution_result)
            if fallback:
                return fallback
            # Try conversation_history
            conv_history = execution_result.get('conversation_history', '')
            if conv_history:
                return conv_history
            # Only use result_summary as absolute last resort
            result_summary = execution_result.get('result_summary', '')
            if result_summary:
                logger.error(f"❌ DEPLOYMENT: Exception fallback returning result_summary (should not happen): {result_summary}")
            return result_summary or 'An error occurred while processing the response.'

    def _get_last_chat_message(self, execution_result: Dict[str, Any]) -> str:
        """
        Extract the last assistant/chat message from execution_result.messages.
        This is used as a robust fallback when End node outputs are not available.
        """
        try:
            messages = execution_result.get('messages') or []
            if not isinstance(messages, list) or not messages:
                logger.warning(f"⚠️ DEPLOYMENT: No messages array or empty in execution_result")
                return ''

            logger.debug(f"🔍 DEPLOYMENT: Checking {len(messages)} messages for chat content")
            
            # Prefer messages explicitly marked as chat (agent responses)
            chat_messages = [
                m for m in messages
                if isinstance(m, dict) and m.get('message_type') == 'chat'
            ]
            
            logger.debug(f"🔍 DEPLOYMENT: Found {len(chat_messages)} chat messages")
            
            # If no chat messages, look for any non-End, non-Start messages
            if not chat_messages:
                candidates = [
                    m for m in messages 
                    if isinstance(m, dict) 
                    and m.get('agent_type') not in ['EndNode', 'StartNode']
                    and m.get('agent_name') not in ['End', 'Start']
                ]
                logger.debug(f"🔍 DEPLOYMENT: Found {len(candidates)} non-End/Start messages as fallback")
            else:
                candidates = chat_messages
            
            if not candidates:
                logger.warning(f"⚠️ DEPLOYMENT: No candidate messages found")
                return ''

            # Get the last candidate message
            last = candidates[-1]
            content = last.get('content', '') or last.get('message', '') or ''
            
            if content:
                logger.info(f"✅ DEPLOYMENT: Extracted chat message from agent '{last.get('agent_name', 'unknown')}': {content[:100]}...")
            else:
                logger.warning(f"⚠️ DEPLOYMENT: Last candidate message has no content: {last}")
            
            return content
        except Exception as e:
            logger.error(f"❌ DEPLOYMENT: Error extracting last chat message: {e}", exc_info=True)
            return ''
    
    def _extract_last_assistant_from_history(self, conversation_history: str) -> str:
        """
        Extract the last assistant response from conversation_history string.
        Format is typically: "Assistant: greeting\nUser: query1\nAssistant: response1\nUser: query2\nAssistant: response2"
        
        Returns the last Assistant: line content, or empty string if not found.
        """
        try:
            if not conversation_history or not isinstance(conversation_history, str):
                return ''
            
            lines = conversation_history.split('\n')
            logger.debug(f"🔍 DEPLOYMENT: Extracting from conversation_history with {len(lines)} lines")
            
            # Look for the last line that starts with "Assistant:" or contains "AI Assistant"
            for line in reversed(lines):
                line = line.strip()
                if not line:
                    continue
                    
                # Check for "Assistant:" prefix
                if line.startswith('Assistant:'):
                    content = line[len('Assistant:'):].strip()
                    if content:
                        logger.debug(f"✅ DEPLOYMENT: Found Assistant: response: {content[:100]}...")
                        return content
                
                # Check for "AI Assistant" or node names like "AI Assistant 1:"
                if ':' in line:
                    parts = line.split(':', 1)
                    if len(parts) == 2:
                        first_part = parts[0].strip().lower()
                        content = parts[1].strip()
                        
                        # Check if it's likely an assistant response (not a user query)
                        if content and ('assistant' in first_part or 'ai' in first_part) and 'user' not in first_part:
                            logger.debug(f"✅ DEPLOYMENT: Found assistant response from '{parts[0]}': {content[:100]}...")
                            return content
            
            logger.warning(f"⚠️ DEPLOYMENT: Could not extract assistant response from conversation_history")
            return ''
        except Exception as e:
            logger.error(f"❌ DEPLOYMENT: Error extracting last assistant from history: {e}", exc_info=True)
            return ''

