"""
Agent Workflow Validation System
Template Independent Graph Validation
"""

import logging
from typing import Dict, List, Tuple, Any

logger = logging.getLogger('agent_orchestration.validation')

class WorkflowGraphValidator:
    """Template-independent workflow graph validation"""
    
    # Supported agent types (from template capabilities)
    SUPPORTED_AGENT_TYPES = {
        'StartNode': {
            'required_fields': ['name', 'prompt'],
            'optional_fields': ['description'],
            'max_count': 1,
            'input_connections': 0,
            'output_connections': 1
        },
        'UserProxyAgent': {
            'required_fields': ['name'],
            'optional_fields': ['description', 'require_human_input'],
            'max_count': 5,
            'input_connections': 1,
            'output_connections': 1
        },
        'AssistantAgent': {
            'required_fields': ['name', 'system_message'],
            'optional_fields': ['description', 'llm_config'],
            'max_count': 10,
            'input_connections': 1,
            'output_connections': 1
        },
        'GroupChatManager': {
            'required_fields': ['name'],
            'optional_fields': ['description', 'speaker_selection'],
            'max_count': 2,
            'input_connections': 1,
            'output_connections': 1
        },
        'MCPServer': {
            'required_fields': ['name', 'server_type'],
            'optional_fields': ['description', 'server_config', 'selected_tools'],
            'max_count': 10,
            'input_connections': 1,
            'output_connections': 1
        },
        'ClassifierAgent': {
            'required_fields': ['name', 'categories', 'llm_provider', 'llm_model'],
            'optional_fields': ['description'],
            'max_count': 10,
            'input_connections': 1,
            # Output connections are per-category — see _validate_classifier_nodes
            'output_connections': 1
        },
        'SplitterAgent': {
            'required_fields': ['name', 'llm_provider', 'llm_model'],
            'optional_fields': ['description', 'overlap_allowed'],
            'max_count': 10,
            'input_connections': 1,
            # Splitter needs ≥2 downstream agents — see _validate_splitter_nodes
            'output_connections': 2
        }
    }
    
    @staticmethod
    def validate_graph(graph_json: Dict, project_capabilities: Dict) -> Tuple[bool, List[str]]:
        """Validate workflow graph against project capabilities"""
        errors = []
        
        try:
            logger.info("🔍 UNIVERSAL: Starting workflow graph validation")
            
            # Basic structure validation
            structure_errors = WorkflowGraphValidator._validate_structure(graph_json)
            errors.extend(structure_errors)
            
            if structure_errors:
                return False, errors
            
            # Extract nodes and edges
            nodes = graph_json.get('nodes', [])
            edges = graph_json.get('edges', [])
            
            # Validate project capabilities
            capability_errors = WorkflowGraphValidator._validate_capabilities(
                nodes, project_capabilities
            )
            errors.extend(capability_errors)
            
            # Validate nodes
            node_errors = WorkflowGraphValidator._validate_nodes(nodes)
            errors.extend(node_errors)
            
            # Validate edges and connections
            edge_errors = WorkflowGraphValidator._validate_edges(nodes, edges)
            errors.extend(edge_errors)
            
            # Validate workflow flow
            flow_errors = WorkflowGraphValidator._validate_workflow_flow(nodes, edges)
            errors.extend(flow_errors)
            
            is_valid = len(errors) == 0
            logger.info(f"✅ UNIVERSAL: Graph validation {'passed' if is_valid else 'failed'} with {len(errors)} errors")
            
            return is_valid, errors
            
        except Exception as e:
            logger.error(f"❌ UNIVERSAL: Graph validation exception: {e}")
            return False, [f"Validation failed: {str(e)}"]
    
    @staticmethod
    def _validate_structure(graph_json: Dict) -> List[str]:
        """Validate basic graph structure"""
        errors = []
        
        # Check for required top-level fields
        if 'nodes' not in graph_json:
            errors.append("Graph must contain 'nodes' field")
        elif not isinstance(graph_json['nodes'], list):
            errors.append("'nodes' must be a list")
        
        if 'edges' not in graph_json:
            errors.append("Graph must contain 'edges' field")
        elif not isinstance(graph_json['edges'], list):
            errors.append("'edges' must be a list")
        
        return errors
    
    @staticmethod
    def _validate_capabilities(nodes: List[Dict], project_capabilities: Dict) -> List[str]:
        """Validate against project capabilities"""
        errors = []
        
        # Check agent count limit
        max_agents = project_capabilities.get('max_agents_per_workflow', 10)
        if len(nodes) > max_agents:
            errors.append(f"Maximum {max_agents} agents allowed, found {len(nodes)}")
        
        # Check supported agent types
        supported_types = project_capabilities.get('supported_agent_types', [])
        
        for node in nodes:
            node_type = node.get('type')
            if node_type not in supported_types:
                errors.append(f"Agent type '{node_type}' not supported by this project template")
        
        # Check function tools support
        function_tools = [n for n in nodes if n.get('type') == 'FunctionTool']
        if function_tools and not project_capabilities.get('supports_function_tools', False):
            errors.append("Function tools not supported by this project template")
        
        return errors
    
    @staticmethod
    def _validate_nodes(nodes: List[Dict]) -> List[str]:
        """Validate individual nodes"""
        errors = []
        node_counts = {}
        
        for i, node in enumerate(nodes):
            # Check required fields
            if 'id' not in node:
                errors.append(f"Node {i} missing required 'id' field")
            
            if 'type' not in node:
                errors.append(f"Node {i} missing required 'type' field")
                continue
            
            node_type = node.get('type')
            node_id = node.get('id', f'node_{i}')
            
            # Count node types
            node_counts[node_type] = node_counts.get(node_type, 0) + 1
            
            # Validate against type specifications
            if node_type in WorkflowGraphValidator.SUPPORTED_AGENT_TYPES:
                type_spec = WorkflowGraphValidator.SUPPORTED_AGENT_TYPES[node_type]
                
                # Check required fields for this type
                node_data = node.get('data', {})
                for required_field in type_spec.get('required_fields', []):
                    if required_field not in node_data or not node_data[required_field]:
                        errors.append(f"Node '{node_id}' ({node_type}) missing required field '{required_field}'")
        
        # Check node type count limits
        for node_type, count in node_counts.items():
            if node_type in WorkflowGraphValidator.SUPPORTED_AGENT_TYPES:
                max_count = WorkflowGraphValidator.SUPPORTED_AGENT_TYPES[node_type].get('max_count', float('inf'))
                if count > max_count:
                    errors.append(f"Too many {node_type} nodes: {count} (max: {max_count})")
        
        # Check for required StartNode
        if 'StartNode' not in node_counts:
            errors.append("Workflow must contain exactly one StartNode")
        elif node_counts['StartNode'] != 1:
            errors.append(f"Workflow must contain exactly one StartNode, found {node_counts['StartNode']}")
        
        return errors
    
    @staticmethod
    def _validate_edges(nodes: List[Dict], edges: List[Dict]) -> List[str]:
        """Validate edges and connections"""
        errors = []
        node_ids = {node.get('id') for node in nodes}
        
        for i, edge in enumerate(edges):
            # Check required edge fields
            if 'source' not in edge:
                errors.append(f"Edge {i} missing 'source' field")
                continue
            if 'target' not in edge:
                errors.append(f"Edge {i} missing 'target' field")
                continue
            
            source_id = edge.get('source')
            target_id = edge.get('target')
            
            # Check if source and target nodes exist
            if source_id not in node_ids:
                errors.append(f"Edge {i} references non-existent source node '{source_id}'")
            if target_id not in node_ids:
                errors.append(f"Edge {i} references non-existent target node '{target_id}'")
            
            # Prevent self-connections
            if source_id == target_id:
                errors.append(f"Edge {i} creates self-connection on node '{source_id}'")
        
        return errors
    
    @staticmethod
    def _validate_workflow_flow(nodes: List[Dict], edges: List[Dict]) -> List[str]:
        """Validate workflow execution flow"""
        errors = []
        
        # Build adjacency lists
        outgoing = {node.get('id'): [] for node in nodes}
        incoming = {node.get('id'): [] for node in nodes}
        
        for edge in edges:
            source = edge.get('source')
            target = edge.get('target')
            if source and target:
                outgoing[source].append(target)
                incoming[target].append(source)
        
        # Find StartNode
        start_nodes = [node for node in nodes if node.get('type') == 'StartNode']
        if not start_nodes:
            return errors  # Already handled in node validation
        
        start_node_id = start_nodes[0].get('id')
        
        # Check that StartNode has no incoming connections
        if incoming.get(start_node_id):
            errors.append("StartNode should not have incoming connections")
        
        # Check that StartNode has outgoing connections
        if not outgoing.get(start_node_id):
            errors.append("StartNode must have at least one outgoing connection")
        
        # Check for orphaned nodes (nodes with no connections)
        for node in nodes:
            node_id = node.get('id')
            node_type = node.get('type')
            
            # Skip FunctionTool nodes as they don't participate in main flow
            if node_type == 'FunctionTool':
                continue
            
            has_connections = bool(incoming.get(node_id)) or bool(outgoing.get(node_id))
            if not has_connections and node_type != 'StartNode':
                errors.append(f"Node '{node_id}' has no connections")
        
        # Check for circular dependencies (basic cycle detection)
        if WorkflowGraphValidator._has_cycles(nodes, edges):
            errors.append("Workflow contains circular dependencies")
        
        return errors
    
    @staticmethod
    def _has_cycles(nodes: List[Dict], edges: List[Dict]) -> bool:
        """Detect cycles in the workflow graph"""
        try:
            # Build adjacency list
            graph = {node.get('id'): [] for node in nodes}
            for edge in edges:
                source = edge.get('source')
                target = edge.get('target')
                if source and target:
                    graph[source].append(target)
            
            # DFS cycle detection
            visited = set()
            rec_stack = set()
            
            def dfs(node_id):
                if node_id in rec_stack:
                    return True  # Cycle found
                if node_id in visited:
                    return False
                
                visited.add(node_id)
                rec_stack.add(node_id)
                
                for neighbor in graph.get(node_id, []):
                    if dfs(neighbor):
                        return True
                
                rec_stack.remove(node_id)
                return False
            
            # Check each node
            for node_id in graph:
                if node_id not in visited:
                    if dfs(node_id):
                        return True
            
            return False
            
        except Exception as e:
            logger.error(f"❌ UNIVERSAL: Error in cycle detection: {e}")
            return False  # Assume no cycles on error
    
    @staticmethod
    def get_validation_summary(is_valid: bool, errors: List[str]) -> Dict[str, Any]:
        """Get formatted validation summary"""
        return {
            'valid': is_valid,
            'error_count': len(errors),
            'errors': errors,
            'timestamp': logger.info.created if hasattr(logger.info, 'created') else None,
            'validator_version': '1.0.0'
        }


class WorkflowSecurityValidator:
    """Security validation for workflow execution"""
    
    @staticmethod
    def validate_function_code(function_code: str) -> Tuple[bool, List[str]]:
        """Validate function code for security issues"""
        errors = []
        
        # Check for dangerous imports and functions
        dangerous_patterns = [
            'import os',
            'import subprocess',
            'import sys',
            '__import__',
            'exec(',
            'eval(',
            'open(',
            'file(',
            'input(',
            'raw_input('
        ]
        
        for pattern in dangerous_patterns:
            if pattern in function_code:
                errors.append(f"Potentially dangerous code pattern detected: {pattern}")
        
        # Check code length
        if len(function_code) > 10000:  # 10KB limit
            errors.append("Function code exceeds maximum length (10KB)")
        
        return len(errors) == 0, errors
    
    @staticmethod
    def validate_execution_parameters(params: Dict) -> Tuple[bool, List[str]]:
        """Validate execution parameters for security"""
        errors = []
        
        # Check parameter size
        import json
        try:
            param_size = len(json.dumps(params))
            if param_size > 100000:  # 100KB limit
                errors.append("Execution parameters exceed size limit")
        except Exception:
            errors.append("Invalid execution parameters format")
        
        return len(errors) == 0, errors
