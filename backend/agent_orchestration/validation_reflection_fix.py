"""
Additional validation method for reflection edge constraints
This should be added to WorkflowGraphValidator class in validation.py
"""

import logging
from typing import Dict, List

logger = logging.getLogger('agent_orchestration.validation')

def _validate_reflection_edge_constraints(nodes: List[Dict], edges: List[Dict]) -> List[str]:
    """
    Validate that ANY agent with reflection input edges has NO outgoing edges
    
    CRITICAL: If any agent (AssistantAgent, UserProxyAgent, GroupChatManager, etc.) 
    is connected to its preceding agent with a Reflection edge, it should have 
    NO outgoing edges. This is because reflection is a feedback loop where the 
    agent provides feedback to the source agent, and the workflow continues from 
    the reflection source position, not from the agent itself.
    
    Applies to: AssistantAgent, UserProxyAgent, GroupChatManager, DelegateAgent, etc.
    Excludes: StartNode, EndNode (they have special roles)
    """
    errors = []
    
    # Build maps for efficient lookup
    node_map = {node.get('id'): node for node in nodes}
    incoming_edges_map = {node.get('id'): [] for node in nodes}
    outgoing_edges_map = {node.get('id'): [] for node in nodes}
    
    for edge in edges:
        source = edge.get('source')
        target = edge.get('target')
        edge_type = edge.get('type', 'sequential')
        
        if source and target:
            # Track all incoming edges (both reflection and sequential)
            if target not in incoming_edges_map:
                incoming_edges_map[target] = []
            incoming_edges_map[target].append(edge)
            
            # Track outgoing edges (only sequential, not reflection)
            if edge_type != 'reflection':
                if source not in outgoing_edges_map:
                    outgoing_edges_map[source] = []
                outgoing_edges_map[source].append(edge)
    
    # Check each agent node (exclude StartNode and EndNode)
    for node in nodes:
        node_type = node.get('type')
        node_id = node.get('id')
        
        # Skip StartNode and EndNode as they have special roles
        if node_type in ['StartNode', 'EndNode']:
            continue
        
        node_name = node.get('data', {}).get('name', node_id)
        
        # Check if this agent has reflection edges as input
        has_reflection_input = False
        reflection_sources = []
        
        for edge in incoming_edges_map.get(node_id, []):
            if edge.get('type') == 'reflection':
                has_reflection_input = True
                source_id = edge.get('source')
                source_node = node_map.get(source_id)
                if source_node:
                    source_name = source_node.get('data', {}).get('name', source_id)
                    reflection_sources.append(source_name)
        
        # If agent has reflection input, check for outgoing edges
        if has_reflection_input:
            outgoing_count = len(outgoing_edges_map.get(node_id, []))
            if outgoing_count > 0:
                error_msg = (
                    f'{node_type} "{node_name}" is connected to its preceding agent(s) '
                    f'({", ".join(reflection_sources)}) with Reflection edge(s), but has {outgoing_count} '
                    f'outgoing edge(s). Agents with reflection input must have NO outgoing edges, '
                    f'as reflection is a feedback loop where the workflow continues from the reflection source position.'
                )
                errors.append(error_msg)
                logger.warning(f"❌ VALIDATION: {error_msg}")
    
    return errors

# Add this call in validate_graph method after flow_errors:
# reflection_errors = WorkflowGraphValidator._validate_reflection_edge_constraints(nodes, edges)
# errors.extend(reflection_errors)

