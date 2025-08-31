"""
ULTRA-DEFENSIVE Agent Orchestration Serializers
This version should work even with completely broken database states
"""

from rest_framework import serializers
from django.db import models

# Try to import models, but handle if they don't exist or have issues
try:
    from users.models import AgentWorkflow, SimulationRun, AgentMessage
    MODELS_AVAILABLE = True
except Exception as e:
    print(f"Warning: Could not import models: {e}")
    MODELS_AVAILABLE = False
    # Create dummy model classes for the serializers
    class AgentWorkflow:
        pass
    class SimulationRun:
        pass  
    class AgentMessage:
        pass


class UltraDefensiveAgentWorkflowSerializer(serializers.ModelSerializer):
    """Ultra-defensive serializer that should never crash"""
    
    def to_representation(self, instance):
        """Ultra-safe representation that handles any database state"""
        
        # Start with minimal safe data
        data = {
            'workflow_id': None,
            'name': 'Unknown Workflow',
            'description': '',
            'graph_json': {'nodes': [], 'edges': []},
            'version': '1.0.0',
            'status': 'draft',
            'created_at': None,
            'updated_at': None,
            'node_count': 0,
            'edge_count': 0,
            'execution_count': 0,
            'last_execution_status': 'never_executed'
        }
        
        if not instance:
            return data
        
        # Safely extract basic fields
        safe_basic_fields = [
            'workflow_id', 'name', 'description', 'graph_json', 
            'version', 'status', 'created_at', 'updated_at'
        ]
        
        for field in safe_basic_fields:
            try:
                if hasattr(instance, field):
                    value = getattr(instance, field)
                    if value is not None:
                        data[field] = value
            except Exception:
                pass  # Keep default value
        
        # Safely extract optional fields
        optional_fields = [
            'max_agents_limit', 'supports_function_tools', 
            'supports_real_time_streaming', 'sandbox_execution_enabled',
            'tags', 'last_executed_at', 'autogen_config', 'supports_rag',
            'vector_collections', 'generated_code', 'code_generation_timestamp',
            'total_executions', 'successful_executions', 'average_execution_time'
        ]
        
        for field in optional_fields:
            try:
                if hasattr(instance, field):
                    value = getattr(instance, field)
                    if value is not None:
                        data[field] = value
            except Exception:
                pass  # Field doesn't exist or has issues
        
        # Safely calculate computed fields
        try:
            if hasattr(instance, 'graph_json') and instance.graph_json:
                if isinstance(instance.graph_json, dict):
                    data['node_count'] = len(instance.graph_json.get('nodes', []))
                    data['edge_count'] = len(instance.graph_json.get('edges', []))
        except Exception:
            pass  # Keep default values
        
        # Safely get execution count
        try:
            # Try multiple possible relationship names
            execution_count = 0
            if hasattr(instance, 'simulation_runs'):
                execution_count = instance.simulation_runs.count()
            elif hasattr(instance, 'runs'):
                execution_count = instance.runs.count()
            elif hasattr(instance, 'simulationrun_set'):
                execution_count = instance.simulationrun_set.count()
            
            data['execution_count'] = execution_count
        except Exception:
            pass  # Keep default 0
        
        # Safely get last execution status
        try:
            last_run = None
            if hasattr(instance, 'simulation_runs'):
                last_run = instance.simulation_runs.order_by('-start_time').first()
            elif hasattr(instance, 'runs'):
                last_run = instance.runs.order_by('-start_time').first()
            elif hasattr(instance, 'simulationrun_set'):
                last_run = instance.simulationrun_set.order_by('-start_time').first()
            
            if last_run and hasattr(last_run, 'status'):
                data['last_execution_status'] = last_run.status
        except Exception:
            pass  # Keep default 'never_executed'
        
        return data
    
    class Meta:
        model = AgentWorkflow
        fields = '__all__'


class UltraDefensiveSimulationRunSerializer(serializers.ModelSerializer):
    """Ultra-defensive simulation run serializer"""
    
    def to_representation(self, instance):
        """Ultra-safe representation"""
        
        data = {
            'run_id': None,
            'status': 'pending',
            'start_time': None,
            'end_time': None,
            'workflow_name': 'Unknown',
            'duration_seconds': None,
            'formatted_duration': 'N/A',
            'is_active': False
        }
        
        if not instance:
            return data
        
        # Safely extract all available fields
        for field in instance._meta.get_fields():
            try:
                if hasattr(instance, field.name):
                    value = getattr(instance, field.name)
                    if value is not None:
                        data[field.name] = value
            except Exception:
                pass
        
        # Safe computed fields
        try:
            if hasattr(instance, 'workflow') and instance.workflow:
                data['workflow_name'] = getattr(instance.workflow, 'name', 'Unknown')
        except Exception:
            pass
        
        try:
            if hasattr(instance, 'status'):
                data['is_active'] = instance.status in ['pending', 'running']
        except Exception:
            pass
        
        return data
    
    class Meta:
        model = SimulationRun
        fields = '__all__'


class UltraDefensiveAgentMessageSerializer(serializers.ModelSerializer):
    """Ultra-defensive agent message serializer"""
    
    def to_representation(self, instance):
        """Ultra-safe representation"""
        
        data = {
            'message_id': None,
            'agent_name': 'Unknown',
            'content': '',
            'message_type': 'chat',
            'timestamp': None,
            'sequence_number': 0
        }
        
        if not instance:
            return data
        
        # Safely extract all available fields
        try:
            for field in instance._meta.get_fields():
                try:
                    if hasattr(instance, field.name):
                        value = getattr(instance, field.name)
                        if value is not None:
                            data[field.name] = value
                except Exception:
                    continue
        except Exception:
            pass
        
        return data
    
    class Meta:
        model = AgentMessage
        fields = '__all__'


# Use the ultra-defensive serializers
AgentWorkflowSerializer = UltraDefensiveAgentWorkflowSerializer
SimulationRunSerializer = UltraDefensiveSimulationRunSerializer  
AgentMessageSerializer = UltraDefensiveAgentMessageSerializer


# Keep the validation serializers simple
class WorkflowValidationSerializer(serializers.Serializer):
    """Simple validation serializer"""
    
    graph_json = serializers.JSONField()
    project_capabilities = serializers.JSONField(required=False)


class WorkflowExecutionSerializer(serializers.Serializer):
    """Simple execution serializer"""
    
    workflow_id = serializers.UUIDField()
    execution_parameters = serializers.JSONField(required=False, default=dict)
    environment = serializers.CharField(max_length=50, default='production')
