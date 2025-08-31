"""
Workflow Parser
==============

Handles workflow graph parsing and multiple input processing for conversation orchestration.
"""

import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger('conversation_orchestrator')


class WorkflowParser:
    """
    Parses workflow graphs and handles multiple input aggregation
    """
    
    def parse_workflow_graph(self, graph_json: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Parse workflow graph into linear execution sequence using TOPOLOGICAL SORT
        This respects the visual flow by processing nodes in dependency order.
        It excludes nodes that are only targets of reflection edges from the main sequence.
        """
        nodes = graph_json.get('nodes', [])
        edges = graph_json.get('edges', [])

        if not nodes:
            logger.warning("⚠️ ORCHESTRATOR: No nodes found in workflow graph")
            return []

        logger.info(f"🔗 ORCHESTRATOR: Parsing workflow with {len(nodes)} nodes and {len(edges)} edges")

        # Identify nodes that are exclusively targets of reflection edges
        reflection_only_targets = set()
        all_targets = {edge['target'] for edge in edges}
        for target_id in all_targets:
            incoming_edges = [edge for edge in edges if edge['target'] == target_id]
            if incoming_edges and all(edge.get('type') == 'reflection' for edge in incoming_edges):
                reflection_only_targets.add(target_id)

        if reflection_only_targets:
            logger.info(f"🔗 ORCHESTRATOR: Excluding reflection-only target nodes from topological sort: {reflection_only_targets}")

        # Filter out nodes that are exclusively reflection targets
        nodes_for_sorting = [node for node in nodes if node['id'] not in reflection_only_targets]
        
        # Create node lookup for fast access
        node_map = {node['id']: node for node in nodes_for_sorting}
        
        # Build adjacency list and calculate in-degrees
        adjacency = {node['id']: [] for node in nodes_for_sorting}
        in_degree = {node['id']: 0 for node in nodes_for_sorting}
        
        # Process edges to build graph structure, ignoring edges related to excluded nodes
        for edge in edges:
            source = edge['source']
            target = edge['target']
            
            if source not in node_map or target not in node_map:
                continue
                
            adjacency[source].append(target)
            in_degree[target] += 1
        
        # KAHN'S ALGORITHM for Topological Sort
        execution_sequence = []
        queue = []
        
        # Find all nodes with in-degree 0 (start nodes)
        for node_id, degree in in_degree.items():
            if degree == 0:
                queue.append(node_id)
                logger.info(f"🚀 ORCHESTRATOR: Found start node: {node_map[node_id].get('data', {}).get('name', node_id)}")
        
        # If no start nodes found, look specifically for StartNode type
        if not queue:
            start_nodes = [n for n in nodes_for_sorting if n.get('type') == 'StartNode']
            if start_nodes:
                queue = [start_nodes[0]['id']]
                logger.warning("⚠️ ORCHESTRATOR: No zero in-degree nodes, using StartNode")
            elif nodes_for_sorting:
                queue = [nodes_for_sorting[0]['id']]
                logger.warning("⚠️ ORCHESTRATOR: No StartNode found, using first node")
        
        # Process nodes in topological order
        processed_count = 0
        while queue:
            queue.sort()
            current_node_id = queue.pop(0)
            
            if current_node_id not in node_map:
                logger.error(f"❌ ORCHESTRATOR: Node {current_node_id} not found in node_map")
                continue
            
            current_node = node_map[current_node_id]
            execution_sequence.append(current_node)
            processed_count += 1
            
            node_name = current_node.get('data', {}).get('name', current_node_id)
            node_type = current_node.get('type', 'Unknown')
            logger.info(f"🎯 ORCHESTRATOR: [{processed_count}] Added to sequence: {node_name} (type: {node_type})")
            
            # Process all neighbors of the current node
            if current_node_id in adjacency:
                for neighbor_id in adjacency[current_node_id]:
                    if neighbor_id in in_degree:
                        in_degree[neighbor_id] -= 1
                        if in_degree[neighbor_id] == 0:
                            queue.append(neighbor_id)
                            neighbor_name = node_map[neighbor_id].get('data', {}).get('name', neighbor_id)
                            logger.info(f"🔗 ORCHESTRATOR: Queued next node: {neighbor_name}")
        
        # Check for cycles
        if len(execution_sequence) < len(nodes_for_sorting):
            unprocessed_ids = set(node_map.keys()) - {node['id'] for node in execution_sequence}
            unprocessed_names = [node_map[uid].get('data', {}).get('name', uid) for uid in unprocessed_ids]
            logger.warning(f"⚠️ ORCHESTRATOR: Possible cycle detected. Unprocessed nodes: {unprocessed_names}")
            
            # Add remaining nodes to avoid execution failure
            for node in nodes_for_sorting:
                if node not in execution_sequence:
                    execution_sequence.append(node)
                    logger.warning(f"⚠️ ORCHESTRATOR: Force-added unprocessed node: {node.get('data', {}).get('name', node['id'])}")
        
        # CRITICAL FIX: Move End nodes to the end of execution sequence
        # This ensures End nodes execute after all other nodes, including UserProxy inputs
        end_nodes = []
        non_end_nodes = []
        
        for node in execution_sequence:
            if node.get('type') == 'EndNode':
                end_nodes.append(node)
            else:
                non_end_nodes.append(node)
        
        # Reconstruct sequence with End nodes at the end
        execution_sequence = non_end_nodes + end_nodes
        
        if end_nodes:
            end_node_names = [node.get('data', {}).get('name', 'Unknown') for node in end_nodes]
            logger.info(f"🔚 ORCHESTRATOR: Moved {len(end_nodes)} End nodes to end of sequence: {', '.join(end_node_names)}")
        
        sequence_names = [f"{node.get('data', {}).get('name', 'Unknown')} ({node.get('type')})" for node in execution_sequence]
        logger.info(f"🔗 ORCHESTRATOR: FINAL execution sequence: {' → '.join(sequence_names)}")
        
        logger.info(f"✅ ORCHESTRATOR: Parsed {len(execution_sequence)} nodes using topological sort with End nodes last")
        return execution_sequence
    
    def find_multiple_inputs_to_node(self, target_node_id: str, graph_json: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Find all nodes that feed into the target node (multiple inputs support)
        Returns list of input node data with metadata
        """
        input_nodes = []
        edges = graph_json.get('edges', [])
        node_map = {node['id']: node for node in graph_json.get('nodes', [])}
        
        logger.info(f"🔍 MULTI-INPUT: Finding input sources for node {target_node_id}")
        
        for edge in edges:
            if edge.get('target') == target_node_id:
                source_id = edge.get('source')
                if source_id in node_map:
                    source_node = node_map[source_id]
                    input_nodes.append({
                        'node': source_node,
                        'edge': edge,
                        'source_id': source_id,
                        'name': source_node.get('data', {}).get('name', source_id),
                        'type': source_node.get('type', 'Unknown')
                    })
                    logger.info(f"🔗 MULTI-INPUT: Found input source: {source_node.get('data', {}).get('name', source_id)} (type: {source_node.get('type')})")
        
        logger.info(f"✅ MULTI-INPUT: Found {len(input_nodes)} input sources for {target_node_id}")
        return input_nodes
    
    def aggregate_multiple_inputs(self, input_sources: List[Dict[str, Any]], executed_nodes: Dict[str, str]) -> Dict[str, Any]:
        """
        Aggregate multiple input sources into structured context
        
        Args:
            input_sources: List of input node metadata
            executed_nodes: Dict mapping node_id to their output/response
        
        Returns:
            Dict with aggregated context information
        """
        logger.info(f"🔄 MULTI-INPUT: Aggregating {len(input_sources)} input sources")
        
        aggregated_context = {
            'primary_input': '',
            'secondary_inputs': [],
            'input_summary': '',
            'all_inputs': [],
            'input_count': len(input_sources)
        }
        
        # Sort inputs by type priority (StartNode first, then others)
        sorted_inputs = sorted(input_sources, key=lambda x: (
            0 if x['type'] == 'StartNode' else
            1 if x['type'] in ['AssistantAgent', 'UserProxyAgent'] else
            2
        ))
        
        input_contexts = []
        
        for i, input_source in enumerate(sorted_inputs):
            input_id = input_source['source_id']
            input_name = input_source['name']
            input_type = input_source['type']
            
            # Get the output/response from this input node
            input_content = executed_nodes.get(input_id, f"[No output from {input_name}]")
            
            input_context = {
                'name': input_name,
                'type': input_type,
                'content': input_content,
                'priority': i + 1
            }
            
            input_contexts.append(input_context)
            aggregated_context['all_inputs'].append(input_context)
            
            logger.info(f"📥 MULTI-INPUT: Processed input {i+1}: {input_name} ({input_type}) - {len(str(input_content))} chars")
        
        # Set primary input (first/highest priority)
        if input_contexts:
            aggregated_context['primary_input'] = input_contexts[0]['content']
            aggregated_context['secondary_inputs'] = input_contexts[1:] if len(input_contexts) > 1 else []
        
        # Create formatted summary
        summary_parts = []
        for ctx in input_contexts:
            summary_parts.append(f"Input {ctx['priority']} ({ctx['type']} - {ctx['name']}): {ctx['content'][:100]}{'...' if len(str(ctx['content'])) > 100 else ''}")
        
        aggregated_context['input_summary'] = "\n".join(summary_parts)
        
        logger.info(f"✅ MULTI-INPUT: Aggregation complete - Primary: {len(str(aggregated_context['primary_input']))} chars, Secondary: {len(aggregated_context['secondary_inputs'])} inputs")
        
        return aggregated_context
    
    def format_multiple_inputs_prompt(self, aggregated_context: Dict[str, Any]) -> str:
        """
        Format multiple inputs into a structured prompt section
        
        Args:
            aggregated_context: Output from aggregate_multiple_inputs
        
        Returns:
            Formatted string for inclusion in prompts
        """
        if aggregated_context['input_count'] <= 1:
            return aggregated_context['primary_input']
        
        prompt_parts = []
        prompt_parts.append(f"Multiple Input Sources ({aggregated_context['input_count']} total):")
        prompt_parts.append("")
        
        # Add primary input
        prompt_parts.append("PRIMARY INPUT:")
        prompt_parts.append(aggregated_context['primary_input'])
        prompt_parts.append("")
        
        # Add secondary inputs
        if aggregated_context['secondary_inputs']:
            prompt_parts.append("ADDITIONAL INPUTS:")
            for i, secondary in enumerate(aggregated_context['secondary_inputs']):
                prompt_parts.append(f"Input {i + 2} ({secondary['type']} - {secondary['name']}):")
                prompt_parts.append(secondary['content'])
                prompt_parts.append("")
        
        return "\n".join(prompt_parts)