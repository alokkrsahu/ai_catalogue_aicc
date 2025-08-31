
import logging
from typing import Dict, List, Any
from asgiref.sync import sync_to_async
from django.utils import timezone

from users.models import WorkflowExecutionMessage

logger = logging.getLogger(__name__)

class ReflectionHandler:
    """
    Handles reflection connections and cross-agent reflection for conversation orchestration.
    """
    
    def __init__(self, llm_provider_manager):
        self.llm_provider_manager = llm_provider_manager
        self.human_input_handler = None  # Will be set by orchestrator
    
    def set_human_input_handler(self, human_input_handler):
        """Set the human input handler reference"""
        self.human_input_handler = human_input_handler

    async def handle_reflection_connections(self, agent_node, agent_response, graph_json, llm_provider):
        """
        Handle reflection connections for an agent
        Implements self-review and iteration cycles
        """
        agent_id = agent_node.get('id')
        agent_name = agent_node.get('data', {}).get('name', 'Agent')
        edges = graph_json.get('edges', [])

        # Find reflection connections from this agent
        reflection_connections = []
        for edge in edges:
            if (edge.get('source') == agent_id and
                edge.get('type') == 'reflection'):
                reflection_connections.append(edge)

        if not reflection_connections:
            return agent_response  # No reflection connections

        logger.info(f"🔄 REFLECTION: Found {len(reflection_connections)} reflection connections for {agent_name}")

        # Filter to only self-reflection connections (same agent)
        self_reflection_connections = [conn for conn in reflection_connections
                                     if conn.get('target') == agent_id]
        cross_agent_reflection_connections = [conn for conn in reflection_connections
                                            if conn.get('target') != agent_id]

        logger.info(f"🔄 REFLECTION: Self-reflection connections: {len(self_reflection_connections)}, Cross-agent: {len(cross_agent_reflection_connections)}")
        logger.info(f"🔄 REFLECTION: Cross-agent reflections will be handled separately in workflow execution")

        if not self_reflection_connections:
            return agent_response  # No self-reflection to process

        # Process only self-reflection connections
        current_response = agent_response
        for connection in self_reflection_connections:
            connection_data = connection.get('data', {})
            max_iterations = connection_data.get('max_iterations', 2)
            reflection_prompt = connection_data.get('reflection_prompt',
                'Please review and improve your previous response. Consider if there are any ways to make it better, more accurate, or more helpful.')

            logger.info(f"🔄 REFLECTION: Starting reflection iteration for {agent_name} (max: {max_iterations})")

            # Perform reflection iterations
            for iteration in range(max_iterations - 1):  # -1 because we already have the initial response
                logger.info(f"🔄 REFLECTION: Iteration {iteration + 2}/{max_iterations} for {agent_name}")

                reflection_full_prompt = f"""
Original Response:
{current_response}

{reflection_prompt}

Please provide your improved response:
"""

                # Generate reflected response
                reflected_response = await llm_provider.generate_response(
                    prompt=reflection_full_prompt,
                    temperature=0.5  # Slightly lower temperature for reflection
                )

                if reflected_response.error:
                    logger.error(f"❌ REFLECTION: Error in iteration {iteration + 2}: {reflected_response.error}")
                    break

                current_response = reflected_response.text.strip()
                logger.info(f"✅ REFLECTION: Completed iteration {iteration + 2}/{max_iterations} - response length: {len(current_response)} chars")

        logger.info(f"🎯 SELF-REFLECTION: Completed {len(self_reflection_connections)} self-reflection iterations for {agent_name}")
        return current_response

    async def handle_cross_agent_reflection(self, source_node, source_response, reflection_edge, graph_json, execution_record, conversation_history):
        """
        Handle cross-agent reflection where one agent sends a message to another agent for reflection/feedback

        Flow: Source Agent → Target Agent (reflection) → Source Agent (processes reflection) → Continue workflow
        """
        source_id = source_node.get('id')
        source_name = source_node.get('data', {}).get('name', 'Source Agent')
        target_id = reflection_edge.get('target')

        # Find target node
        target_node = None
        for node in graph_json.get('nodes', []):
            if node.get('id') == target_id:
                target_node = node
                break

    if not target_node:
        logger.error(f"❌ CROSS-AGENT-REFLECTION: Target node {target_id} not found")
        return source_response, conversation_history

    target_name = target_node.get('data', {}).get('name', 'Target Agent')
    target_type = target_node.get('type')

    logger.info(f"🔄 CROSS-AGENT-REFLECTION: {source_name} → {target_name} (reflection)")

    # Get reflection configuration
    connection_data = reflection_edge.get('data', {})
    max_iterations = connection_data.get('max_iterations', 1)
    reflection_prompt = connection_data.get('reflection_prompt',
        f'Please review this message from {source_name} and provide feedback or suggestions:')

    current_conversation = conversation_history
    final_response = source_response
    original_source_response = source_response  # Preserve original for context

    for iteration in range(max_iterations):
        logger.info(f"🔄 CROSS-AGENT-REFLECTION: Iteration {iteration + 1}/{max_iterations}")

        # Step 1: Send message to target agent
        target_prompt = f"""
{reflection_prompt}

Message from {source_name}:
{final_response}

Current conversation context:
{current_conversation[-1000:]}  # Last 1000 chars for context

Please provide your feedback, suggestions, or response:
"""

        # Handle different target agent types
        if target_type == 'UserProxyAgent':
            # Check if UserProxy requires human input
            target_data = target_node.get('data', {})
            if target_data.get('require_human_input', True):
                logger.info(f"👤 CROSS-AGENT-REFLECTION: UserProxy {target_name} requires human input - pausing for human input")
                logger.info(f"🔍 CROSS-AGENT-REFLECTION: Original source response length: {len(original_source_response)} chars")
                logger.info(f"🔍 CROSS-AGENT-REFLECTION: Original source response content: {original_source_response[:500]}...")

                # Prepare context for human input in the format expected by frontend
                human_input_context = {
                    'agent_id': target_node.get('id'),
                    'input_sources': [
                        {
                            'agent_name': source_name,
                            'agent_type': source_node.get('type', 'Agent'),
                            'content': source_response,
                            'priority': 1,
                            'node_id': source_node.get('id')
                        }
                    ],
                    'input_count': 1,
                    'primary_input': original_source_response,
                    # Reflection-specific context
                    'reflection_source': source_name,
                    'source_message': original_source_response,
                    'iteration': iteration + 1,
                    'max_iterations': max_iterations,
                    'prompt': f"Please review this message from {source_name} and provide feedback:"
                }

                # Pause workflow for human input
                await self.human_input_handler.pause_for_human_input_reflection(
                    execution_record, target_node, human_input_context, current_conversation
                )

                # Return special indicator that we're waiting for human input in reflection
                return 'AWAITING_REFLECTION_INPUT', current_conversation
            else:
                # UserProxy without human input - generate automatic response
                target_response = f"Feedback from {target_name}: This looks good, please proceed."
        else:
            # Handle other agent types (AssistantAgent, etc.)
            target_data = target_node.get('data', {})
            target_config = {
                'llm_provider': target_data.get('llm_provider', 'openai'),
                'llm_model': target_data.get('llm_model', 'gpt-3.5-turbo'),
                'temperature': target_data.get('temperature', 0.7),
                'max_tokens': target_data.get('max_tokens', 2048)
            }

            target_llm = self.llm_provider_manager.get_llm_provider(target_config)
            if not target_llm:
                logger.error(f"❌ CROSS-AGENT-REFLECTION: Failed to get LLM provider for {target_name}")
                target_response = f"Error: Could not process reflection from {target_name}"
            else:
                target_llm_response = await target_llm.generate_response(
                    prompt=target_prompt,
                    temperature=target_config.get('temperature', 0.7)
                )

                if target_llm_response.error:
                    logger.error(f"❌ CROSS-AGENT-REFLECTION: Error from {target_name}: {target_llm_response.error}")
                    target_response = f"Error processing reflection from {target_name}"
                else:
                    target_response = target_llm_response.text.strip()

        # Update conversation history
        current_conversation += f"\n{target_name} (Reflection): {target_response}"

        # Step 2: Send reflection back to source agent for processing
        if iteration < max_iterations - 1:  # Only if not the last iteration
            source_reflection_prompt = f"""
            You previously said:
{final_response}

{target_name} provided this feedback:
{target_response}

Please revise your response based on this feedback:
"""

            # Get source agent LLM
            source_data = source_node.get('data', {})
            source_config = {
                'llm_provider': source_data.get('llm_provider', 'openai'),
                'llm_model': source_data.get('llm_model', 'gpt-3.5-turbo'),
                'temperature': source_data.get('temperature', 0.7),
                'max_tokens': source_data.get('max_tokens', 2048)
            }

            source_llm = self.llm_provider_manager.get_llm_provider(source_config)
            if source_llm:
                revised_response = await source_llm.generate_response(
                    prompt=source_reflection_prompt,
                    temperature=source_config.get('temperature', 0.7)
                )

                if not revised_response.error:
                    final_response = revised_response.text.strip()
                    current_conversation += f"\n{source_name} (Revised): {final_response}"
                    logger.info(f"✅ CROSS-AGENT-REFLECTION: {source_name} revised response based on {target_name} feedback")

    logger.info(f"🎯 CROSS-AGENT-REFLECTION: Completed {max_iterations} iterations between {source_name} and {target_name}")
    return final_response, current_conversation

    async def pause_for_human_input_reflection(self, execution_record, target_node, reflection_context, conversation_history):
        """
        Pause workflow execution for human input during cross-agent reflection
        """
        target_name = target_node.get('data', {}).get('name', 'User Proxy Agent')

        logger.info(f"👤 REFLECTION HUMAN INPUT: Pausing for human input from {target_name}")

        # Update execution record for human input during reflection
        execution_record.human_input_required = True
        execution_record.awaiting_human_input_agent = target_name
        execution_record.human_input_agent_id = target_node.get('id')
        execution_record.human_input_context = reflection_context
        execution_record.human_input_requested_at = timezone.now()
        execution_record.conversation_history = conversation_history
        await sync_to_async(execution_record.save)()

        logger.info(f"💾 REFLECTION HUMAN INPUT: Updated execution record for reflection human input")

    async def resume_reflection_workflow_execution(self, execution_record, human_input):
        """
        Resume workflow execution after human input during cross-agent reflection
        """
        logger.info(f"🔄 REFLECTION RESUME: Processing reflection human input for {execution_record.execution_id}")

        # Get reflection context
        reflection_context = execution_record.human_input_context
        source_name = reflection_context.get('reflection_source')
        source_message = reflection_context.get('source_message')
        target_name = execution_record.awaiting_human_input_agent

        logger.info(f"🔄 REFLECTION RESUME: {target_name} provided feedback to {source_name}")

        # Update conversation history with human feedback
        updated_conversation = execution_record.conversation_history + f"\n{target_name} (Reflection): {human_input}"

        # Get workflow and graph
        workflow = await sync_to_async(lambda: execution_record.workflow)()
        graph_json = await sync_to_async(lambda: workflow.graph_json)()

        # Find the source node to send reflection back
        source_node = None
        for node in graph_json.get('nodes', []):
            node_name = node.get('data', {}).get('name')
            if node_name == source_name:
                source_node = node
                break

        if not source_node:
            logger.error(f"❌ REFLECTION RESUME: Could not find source node {source_name}")
            # Continue with regular workflow - this method needs to be implemented
            # For now, return the human input as the final response
            return human_input, updated_conversation

        # Send reflection back to source agent for final processing
        source_data = source_node.get('data', {})
        source_config = {
            'llm_provider': source_data.get('llm_provider', 'openai'),
            'llm_model': source_data.get('llm_model', 'gpt-3.5-turbo'),
            'temperature': source_data.get('temperature', 0.7),
            'max_tokens': source_data.get('max_tokens', 2048)
        }

        source_llm = self.llm_provider_manager.get_llm_provider(source_config)
        if source_llm:
            source_reflection_prompt = f"""
            You previously said:
{source_message}

{target_name} provided this feedback:
{human_input}

Please provide your final response, taking this feedback into account:
"""

            logger.info(f"🔄 REFLECTION RESUME: Sending feedback back to {source_name} for final processing")

            try:
                revised_response = await source_llm.generate_response(
                    prompt=source_reflection_prompt,
                    temperature=source_config.get('temperature', 0.7)
                )

                if not revised_response.error:
                    final_response = revised_response.text.strip()
                    updated_conversation += f"\n{source_name} (Final): {final_response}"
                    logger.info(f"✅ REFLECTION RESUME: {source_name} provided final response based on {target_name} feedback")
                else:
                    logger.error(f"❌ REFLECTION RESUME: Error from {source_name}: {revised_response.error}")
                    final_response = source_message  # Fallback to original
            except Exception as e:
                logger.error(f"❌ REFLECTION RESUME: Exception processing {source_name} reflection: {e}")
                final_response = source_message  # Fallback to original
        else:
            logger.error(f"❌ REFLECTION RESUME: Could not get LLM provider for {source_name}")
            final_response = source_message  # Fallback to original

        # Clear human input requirements
        execution_record.human_input_required = False
        execution_record.awaiting_human_input_agent = ""
        execution_record.human_input_context = {}
        execution_record.conversation_history = updated_conversation

        # MCP FIX: Update executed_nodes with the final response from reflection
        executed_nodes = execution_record.executed_nodes or {}
        if source_node:
            executed_nodes[source_node.get('id')] = final_response
        execution_record.executed_nodes = executed_nodes

        await sync_to_async(execution_record.save)()

        # Return the final response and updated conversation
        return final_response, updated_conversation