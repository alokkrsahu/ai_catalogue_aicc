"""
Conversation Orchestration Engine
=================================

Custom agent orchestration framework that chains conversations between agents
using different LLM providers. Each agent can use a different LLM (OpenAI, Claude, Gemini).
"""

import os
import logging
import asyncio
import time
from typing import Dict, List, Any, Optional, Tuple
from django.utils import timezone
from django.conf import settings

# Import existing LLM infrastructure
from llm_eval.providers.openai_provider import OpenAIProvider
from llm_eval.providers.claude_provider import ClaudeProvider  
from llm_eval.providers.gemini_provider import GeminiProvider
from llm_eval.providers.base import LLMResponse

from users.models import (
    AgentWorkflow, SimulationRun, AgentMessage, 
    SimulationRunStatus, AgentMessageType
)

logger = logging.getLogger('conversation_orchestrator')

class ConversationOrchestrator:
    """
    Custom conversation orchestration engine for agent workflows
    """
    
    def __init__(self):
        self.api_keys = {
            'openai': os.getenv('OPENAI_API_KEY'),
            'anthropic': os.getenv('ANTHROPIC_API_KEY'), 
            'google': os.getenv('GEMINI_API_KEY')
        }
        logger.info("🤖 ORCHESTRATOR: Initialized conversation orchestrator")
        
    def get_llm_provider(self, agent_config: Dict[str, Any]) -> Optional[object]:
        """
        Create LLM provider instance based on agent configuration
        """
        provider_type = agent_config.get('llm_provider', 'openai')
        model = agent_config.get('llm_model', 'gpt-3.5-turbo')
        max_tokens = agent_config.get('max_tokens', 2048)
        
        try:
            if provider_type == 'openai':
                api_key = self.api_keys.get('openai')
                if not api_key:
                    logger.error("❌ ORCHESTRATOR: OpenAI API key not found")
                    return None
                return OpenAIProvider(api_key=api_key, model=model, max_tokens=max_tokens)
                
            elif provider_type in ['anthropic', 'claude']:
                api_key = self.api_keys.get('anthropic')
                if not api_key:
                    logger.error("❌ ORCHESTRATOR: Anthropic API key not found")
                    return None
                return ClaudeProvider(api_key=api_key, model=model, max_tokens=max_tokens)
                
            elif provider_type in ['google', 'gemini']:
                api_key = self.api_keys.get('google')
                if not api_key:
                    logger.error("❌ ORCHESTRATOR: Google API key not found")
                    return None
                return GeminiProvider(api_key=api_key, model=model, max_tokens=max_tokens)
                
            else:
                logger.error(f"❌ ORCHESTRATOR: Unknown provider type: {provider_type}")
                return None
                
        except Exception as e:
            logger.error(f"❌ ORCHESTRATOR: Failed to create LLM provider: {e}")
            return None
    
    def parse_workflow_graph(self, graph_json: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Parse workflow graph into linear execution sequence
        
        Returns:
            List of nodes in execution order: [StartNode, Agent1, Agent2, ..., EndNode]
        """
        nodes = graph_json.get('nodes', [])
        edges = graph_json.get('edges', [])
        
        if not nodes:
            logger.warning("⚠️ ORCHESTRATOR: No nodes found in workflow graph")
            return []
        
        # Create adjacency map for graph traversal
        adjacency = {}
        for edge in edges:
            source = edge['source']
            target = edge['target']
            if source not in adjacency:
                adjacency[source] = []
            adjacency[source].append(target)
        
        # Find start node
        start_nodes = [n for n in nodes if n.get('type') == 'StartNode']
        if not start_nodes:
            logger.warning("⚠️ ORCHESTRATOR: No StartNode found, using first node")
            start_node = nodes[0]
        else:
            start_node = start_nodes[0]
        
        # Build execution sequence using DFS traversal
        execution_sequence = []
        visited = set()
        
        def traverse(node_id):
            if node_id in visited:
                return
            visited.add(node_id)
            
            # Find node data
            node = next((n for n in nodes if n['id'] == node_id), None)
            if node:
                execution_sequence.append(node)
                
                # Continue to connected nodes
                for next_node_id in adjacency.get(node_id, []):
                    traverse(next_node_id)
        
        traverse(start_node['id'])
        
        logger.info(f"🔗 ORCHESTRATOR: Parsed execution sequence: {len(execution_sequence)} nodes")
        return execution_sequence
    
    def craft_conversation_prompt(self, conversation_history: str, agent_node: Dict[str, Any]) -> str:
        """
        Craft conversation prompt for an agent including full conversation history
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
        
        # Add conversation history
        if conversation_history.strip():
            prompt_parts.append("Conversation History:")
            prompt_parts.append(conversation_history)
        
        # Add agent prompt
        prompt_parts.append(f"\n{agent_name}, please provide your response:")
        
        return "\n".join(prompt_parts)
    
    async def execute_workflow(self, workflow: AgentWorkflow, executed_by) -> SimulationRun:
        """
        Execute the complete workflow with real LLM calls and conversation chaining
        """
        logger.info(f"🚀 ORCHESTRATOR: Starting workflow execution for {workflow.workflow_id}")
        
        # Create simulation run record
        run = SimulationRun.objects.create(
            workflow=workflow,
            executed_by=executed_by,
            status=SimulationRunStatus.RUNNING,
            graph_snapshot=workflow.graph_json,
            execution_parameters={
                'execution_mode': 'custom_orchestration',
                'llm_providers_used': [],
                'total_nodes': len(workflow.graph_json.get('nodes', []))
            }
        )
        
        try:
            # Parse workflow into execution sequence
            execution_sequence = self.parse_workflow_graph(workflow.graph_json)
            
            if not execution_sequence:
                raise Exception("No execution sequence could be built from workflow graph")
            
            # Initialize conversation history
            conversation_history = ""
            message_sequence = 0
            agents_involved = set()
            total_response_time = 0
            
            # Execute each node in sequence
            for node in execution_sequence:
                node_type = node.get('type')
                node_data = node.get('data', {})
                node_name = node_data.get('name', f'Node_{node.get("id", "unknown")}')
                
                logger.info(f"🎯 ORCHESTRATOR: Executing node {node_name} (type: {node_type})")
                
                if node_type == 'StartNode':
                    # Handle start node
                    start_prompt = node_data.get('prompt', 'Please begin the conversation.')
                    conversation_history = f"Start Node: {start_prompt}"
                    
                    # Store start message
                    AgentMessage.objects.create(
                        run=run,
                        agent_name='Start',
                        agent_type='StartNode',
                        content=start_prompt,
                        message_type=AgentMessageType.WORKFLOW_START,
                        sequence_number=message_sequence,
                        response_time_ms=0
                    )
                    message_sequence += 1
                    
                elif node_type in ['AssistantAgent', 'UserProxyAgent', 'GroupChatManager']:
                    # Handle agent nodes with real LLM calls
                    agent_config = {
                        'llm_provider': node_data.get('llm_provider', 'openai'),
                        'llm_model': node_data.get('llm_model', 'gpt-3.5-turbo'),
                        'max_tokens': node_data.get('max_tokens', 2048),
                        'temperature': node_data.get('temperature', 0.7)
                    }
                    
                    # Get LLM provider for this agent
                    llm_provider = self.get_llm_provider(agent_config)
                    if not llm_provider:
                        raise Exception(f"Failed to create LLM provider for agent {node_name}")
                    
                    # Craft conversation prompt with history
                    prompt = self.craft_conversation_prompt(conversation_history, node)
                    
                    logger.info(f"🤖 ORCHESTRATOR: Calling {agent_config['llm_provider']}/{agent_config['llm_model']} for {node_name}")
                    
                    # Make LLM call
                    llm_response: LLMResponse = await llm_provider.generate_response(
                        prompt=prompt,
                        temperature=agent_config.get('temperature', 0.7)
                    )
                    
                    if llm_response.error:
                        raise Exception(f"LLM error for {node_name}: {llm_response.error}")
                    
                    # Add response to conversation history
                    agent_response = llm_response.text.strip()
                    conversation_history += f"\n{node_name}: {agent_response}"
                    
                    # Store agent message in database
                    AgentMessage.objects.create(
                        run=run,
                        agent_name=node_name,
                        agent_type=node_type,
                        content=agent_response,
                        message_type=AgentMessageType.CHAT,
                        sequence_number=message_sequence,
                        response_time_ms=llm_response.response_time_ms,
                        token_count=llm_response.token_count,
                        metadata={
                            'llm_provider': agent_config['llm_provider'],
                            'llm_model': agent_config['llm_model'],
                            'temperature': agent_config['temperature'],
                            'cost_estimate': llm_response.cost_estimate
                        }
                    )
                    message_sequence += 1
                    agents_involved.add(node_name)
                    total_response_time += llm_response.response_time_ms
                    
                    # Track provider usage
                    providers_used = run.execution_parameters.get('llm_providers_used', [])
                    if agent_config['llm_provider'] not in providers_used:
                        providers_used.append(agent_config['llm_provider'])
                        run.execution_parameters['llm_providers_used'] = providers_used
                    
                elif node_type == 'EndNode':
                    # Handle end node
                    end_message = node_data.get('message', 'Workflow completed successfully.')
                    
                    AgentMessage.objects.create(
                        run=run,
                        agent_name='End',
                        agent_type='EndNode',
                        content=end_message,
                        message_type=AgentMessageType.WORKFLOW_END,
                        sequence_number=message_sequence,
                        response_time_ms=0
                    )
                    message_sequence += 1
                    
                else:
                    logger.warning(f"⚠️ ORCHESTRATOR: Unknown node type {node_type}, skipping")
            
            # Mark run as completed
            run.status = SimulationRunStatus.COMPLETED
            run.end_time = timezone.now()
            run.total_messages = message_sequence
            run.total_agents_involved = len(agents_involved)
            run.average_response_time = total_response_time / len(agents_involved) if agents_involved else 0
            run.result_summary = f"Successfully executed {len(execution_sequence)} nodes with {len(agents_involved)} agents"
            
            # Update workflow execution stats
            workflow.total_executions += 1
            workflow.successful_executions += 1
            workflow.last_executed_at = timezone.now()
            
            # Update average execution time
            if run.duration_seconds:
                if workflow.average_execution_time:
                    workflow.average_execution_time = (
                        (workflow.average_execution_time * (workflow.total_executions - 1) + run.duration_seconds) 
                        / workflow.total_executions
                    )
                else:
                    workflow.average_execution_time = run.duration_seconds
            
            workflow.save()
            run.save()
            
            logger.info(f"✅ ORCHESTRATOR: Workflow execution completed successfully")
            return run
            
        except Exception as e:
            logger.error(f"❌ ORCHESTRATOR: Workflow execution failed: {e}")
            
            # Mark run as failed
            run.status = SimulationRunStatus.FAILED
            run.end_time = timezone.now()
            run.error_message = str(e)
            run.result_summary = f"Execution failed: {str(e)}"
            
            # Update workflow stats
            workflow.total_executions += 1
            workflow.last_executed_at = timezone.now()
            workflow.save()
            run.save()
            
            raise e
    
    def get_conversation_history_for_run(self, run: SimulationRun) -> List[Dict[str, Any]]:
        """
        Get formatted conversation history for a simulation run
        """
        messages = run.messages.order_by('sequence_number')
        
        conversation = []
        for message in messages:
            conversation.append({
                'agent_name': message.agent_name,
                'agent_type': message.agent_type,
                'content': message.content,
                'message_type': message.message_type,
                'timestamp': message.timestamp.isoformat(),
                'sequence_number': message.sequence_number,
                'response_time_ms': message.response_time_ms,
                'token_count': message.token_count,
                'metadata': message.metadata
            })
        
        return conversation
    
    def get_workflow_execution_summary(self, workflow: AgentWorkflow) -> Dict[str, Any]:
        """
        Get execution summary for a workflow
        """
        recent_runs = workflow.simulation_runs.order_by('-start_time')[:10]
        
        return {
            'workflow_id': str(workflow.workflow_id),
            'workflow_name': workflow.name,
            'total_executions': workflow.total_executions,
            'successful_executions': workflow.successful_executions,
            'success_rate': workflow.success_rate,
            'average_execution_time': workflow.average_execution_time,
            'last_executed': workflow.last_executed_at.isoformat() if workflow.last_executed_at else None,
            'recent_runs': [
                {
                    'run_id': str(run.run_id),
                    'status': run.status,
                    'start_time': run.start_time.isoformat(),
                    'end_time': run.end_time.isoformat() if run.end_time else None,
                    'duration': run.formatted_duration,
                    'total_messages': run.total_messages,
                    'total_agents': run.total_agents_involved,
                    'error_message': run.error_message if run.status == SimulationRunStatus.FAILED else None
                }
                for run in recent_runs
            ]
        }

# Create singleton instance
conversation_orchestrator = ConversationOrchestrator()
