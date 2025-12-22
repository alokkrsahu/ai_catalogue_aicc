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
                return ''

            # Find End node(s)
            end_nodes = [node for node in workflow_graph.get('nodes', []) if node.get('type') == 'EndNode']
            if not end_nodes:
                logger.warning("⚠️ DEPLOYMENT: No End node found in workflow graph")
                # Fallback: last chat message
                fallback = self._get_last_chat_message(execution_result)
                if fallback:
                    return fallback
                return execution_result.get('result_summary', '') or execution_result.get('conversation_history', '')

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
                return execution_result.get('result_summary', '') or execution_result.get('conversation_history', '')

            predecessor_id = predecessor_node_ids[0]

            # Map node IDs to names
            node_id_to_name = {
                node['id']: node.get('data', {}).get('name', node.get('id'))
                for node in workflow_graph.get('nodes', [])
            }
            predecessor_name = node_id_to_name.get(predecessor_id, predecessor_id)

            # Find the last message from the predecessor agent
            end_node_messages = []
            for msg in messages:
                if not isinstance(msg, dict):
                    continue
                agent_name = msg.get('agent_name', '')
                if agent_name == predecessor_name:
                    content = msg.get('content', '') or msg.get('message', '')
                    if content:
                        end_node_messages.append(content)

            if end_node_messages:
                chosen = end_node_messages[-1]
                logger.info(f"✅ DEPLOYMENT: Using End node input from predecessor '{predecessor_name}'")
                return chosen

            # As a final fallback, use last chat message
            logger.warning("⚠️ DEPLOYMENT: No messages found for End node predecessor, using fallback")
            fallback = self._get_last_chat_message(execution_result)
            if fallback:
                return fallback
            return execution_result.get('result_summary', '') or execution_result.get('conversation_history', '')

        except Exception as e:
            logger.error(f"❌ DEPLOYMENT: Error extracting End node output: {e}", exc_info=True)
            # Fallback to last assistant/chat message, then result_summary
            fallback = self._get_last_chat_message(execution_result)
            if fallback:
                return fallback
            return execution_result.get('result_summary', '') or 'An error occurred while processing the response.'

    def _get_last_chat_message(self, execution_result: Dict[str, Any]) -> str:
        """
        Extract the last assistant/chat message from execution_result.messages.
        This is used as a robust fallback when End node outputs are not available.
        """
        try:
            messages = execution_result.get('messages') or []
            if not isinstance(messages, list) or not messages:
                return ''

            # Prefer messages explicitly marked as chat
            chat_messages = [
                m for m in messages
                if isinstance(m, dict) and m.get('message_type') == 'chat'
            ]
            candidates = chat_messages or [
                m for m in messages if isinstance(m, dict)
            ]
            if not candidates:
                return ''

            last = candidates[-1]
            return last.get('content', '') or last.get('message', '') or ''
        except Exception as e:
            logger.error(f"❌ DEPLOYMENT: Error extracting last chat message: {e}", exc_info=True)
            return ''

