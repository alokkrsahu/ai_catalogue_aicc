"""
Agent Orchestration Tasks - Real AutoGen v2.0 Execution Only

Implements Celery tasks for executing REAL AutoGen v2.0 workflows with real-time streaming.
COMPLETELY REMOVES SIMULATION MODE - Only real AutoGen execution.
"""

from celery import shared_task
from django.utils import timezone
from users.models import SimulationRun, AgentMessage, IntelliDocProject
import asyncio
import logging
import json
import uuid
from typing import Dict, List, Any

logger = logging.getLogger('agent_orchestration')

@shared_task(bind=True)
def execute_agent_workflow(self, run_id: str):
    """
    🚀 REAL AutoGen v2.0 workflow execution - NO SIMULATION
    
    Executes actual AutoGen v2.0 code with real-time message streaming.
    COMPLETELY REMOVES SIMULATION MODE.
    """
    logger.info(f"🚀 REAL AUTOGEN V2: Starting execution for run {run_id}")
    
    try:
        # Load simulation run (template independent)
        run = SimulationRun.objects.get(run_id=run_id)
        run.status = 'running'
        run.start_time = timezone.now()
        run.save()
        
        logger.info(f"📊 REAL AUTOGEN V2: Loaded run for workflow {run.workflow.name}")
        
        # Send execution start status via WebSocket
        send_execution_status(
            run.workflow.project.project_id,
            'running',
            'Starting REAL AutoGen v2.0 workflow execution...',
            0
        )
        
        # Use REAL AutoGen v2.0 executor for execution
        result = asyncio.run(execute_real_autogen_v2_workflow(run))
        
        # Mark as completed
        run.status = 'completed' if result['success'] else 'failed'
        run.end_time = timezone.now()
        run.result_summary = result.get('summary', result.get('result', ''))
        run.total_messages = result.get('message_count', 0)
        if not result['success']:
            run.error_message = result.get('error', 'Unknown error')
        run.save()
        
        # Send completion status via WebSocket
        send_execution_status(
            run.workflow.project.project_id,
            run.status,
            f"REAL AutoGen v2.0 workflow {'completed successfully' if result['success'] else 'failed'}",
            100
        )
        
        logger.info(f"✅ REAL AUTOGEN V2: Execution completed for run {run_id}")
        return {
            'success': result['success'],
            'run_id': run_id,
            'message_count': result.get('message_count', 0),
            'duration_seconds': (run.end_time - run.start_time).total_seconds() if run.end_time else 0,
            'execution_type': result.get('execution_type', 'real_autogen_v2'),
            'error': result.get('error') if not result['success'] else None
        }
        
    except SimulationRun.DoesNotExist:
        logger.error(f"❌ AUTOGEN V2 EXECUTION: Run {run_id} not found")
        return {
            'success': False,
            'error': f'Simulation run {run_id} not found'
        }
        
    except Exception as e:
        logger.error(f"❌ AUTOGEN V2 EXECUTION: Workflow execution failed for run {run_id}: {e}")
        
        # Update run status on failure
        try:
            run = SimulationRun.objects.get(run_id=run_id)
            run.status = 'failed'
            run.error_message = str(e)
            run.end_time = timezone.now()
            run.save()
        except:
            pass
        
        return {
            'success': False,
            'error': str(e),
            'run_id': run_id
        }

def get_initial_message_from_graph(graph_json: Dict[str, Any]) -> str:
    """
    Extract initial message from workflow graph
    
    Args:
        graph_json: Workflow graph with nodes and edges
        
    Returns:
        Initial message for workflow execution
    """
    nodes = graph_json.get('nodes', [])
    
    # Look for StartNode with prompt
    for node in nodes:
        if node['type'] == 'StartNode':
            start_prompt = node.get('data', {}).get('prompt', '')
            if start_prompt.strip():
                return start_prompt.strip()
    
    # Default message if no start node or prompt
    return "Hello! Let's begin our REAL AutoGen v2.0 workflow collaboration."

async def execute_real_autogen_v2_workflow(run: SimulationRun) -> Dict[str, Any]:
    """
    Execute REAL AutoGen v2.0 workflow - NO SIMULATION
    
    Args:
        run: SimulationRun instance
        
    Returns:
        Dictionary with REAL execution results
    """
    logger.info(f"🚀 REAL AUTOGEN V2: Starting execution for run {run.run_id}")
    
    try:
        # Import the REAL AutoGen executor (using simple implementation)
        from agent_orchestration.autogen.simple_executor import SimpleAutoGenExecutor as AutoGenV2Executor
        
        # Create executor instance
        executor = AutoGenV2Executor(
            project_id=str(run.workflow.project.project_id),
            run_id=str(run.run_id)
        )
        
        # Generate AutoGen v2.0 code from workflow graph
        workflow_code = generate_autogen_v2_code_from_graph(run)
        
        # Get initial message
        initial_message = get_initial_message_from_graph(run.graph_snapshot)
        
        # Execute the workflow with REAL AutoGen v2.0
        result = await executor.execute_workflow(
            workflow_code=workflow_code,
            initial_message=initial_message,
            run=run
        )
        
        logger.info(f"✅ REAL AUTOGEN V2: Execution completed for run {run.run_id}")
        return result
        
    except Exception as e:
        logger.error(f"❌ REAL AUTOGEN V2: Execution failed for run {run.run_id}: {e}")
        return {
            'success': False,
            'error': str(e),
            'message_count': 0,
            'execution_type': 'real_autogen_v2_failed'
        }

def generate_autogen_v2_code_from_graph(run: SimulationRun) -> str:
    """
    Generate REAL AutoGen v2.0 Python code from workflow graph
    
    Args:
        run: SimulationRun instance with graph data
        
    Returns:
        Generated REAL AutoGen v2.0 Python code
    """
    logger.info(f"🔧 CODE GENERATION: Generating REAL AutoGen v2.0 code for run {run.run_id}")
    
    try:
        from agent_orchestration.autogen.generator import AutoGenDirectGenerator
        
        # Create generator instance
        generator = AutoGenDirectGenerator(str(run.workflow.project.project_id))
        
        # Get project capabilities
        project_capabilities = run.workflow.project.processing_capabilities or {}
        
        # Generate the REAL workflow code
        workflow_code = generator.generate_workflow_code(
            run.graph_snapshot,
            project_capabilities
        )
        
        logger.info(f"✅ CODE GENERATION: Generated {len(workflow_code)} characters of REAL AutoGen v2.0 code")
        return workflow_code
        
    except Exception as e:
        logger.error(f"❌ CODE GENERATION: Failed to generate REAL code: {e}")
        # Return a minimal REAL AutoGen v2.0 workflow instead of simulation
        return '''
# REAL AutoGen v2.0 Fallback Workflow
import asyncio

async def run_autogen_v2_workflow(initial_message="Hello"):
    """Fallback when REAL AutoGen v2.0 code generation fails"""
    print(f"⚠️ REAL AutoGen v2.0 fallback executed with message: {initial_message}")
    
    # Log the execution attempt
    if "message_handler" in globals():
        await message_handler.capture_message(
            agent_name="System",
            agent_type="system",
            content="⚠️ AutoGen v2.0 code generation failed, using fallback",
            message_type="error"
        )
    
    return "Fallback workflow completed - REAL AutoGen v2.0 code generation failed"

def run_autogen_workflow(initial_message="Hello"):
    """Synchronous wrapper for fallback"""
    return asyncio.run(run_autogen_v2_workflow(initial_message))

if __name__ == "__main__":
    run_autogen_workflow()
'''

def send_execution_status(project_id: str, status: str, message: str, progress: int):
    """
    Send execution status update via WebSocket
    
    Args:
        project_id: Project identifier
        status: Execution status (running, completed, failed)
        message: Status message
        progress: Progress percentage (0-100)
    """
    try:
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        
        channel_layer = get_channel_layer()
        if channel_layer:
            async_to_sync(channel_layer.group_send)(
                f"autogen_workflow_{project_id}",
                {
                    'type': 'execution_status',
                    'status': status,
                    'message': message,
                    'progress': progress,
                    'timestamp': timezone.now().isoformat()
                }
            )
            
            logger.debug(f"📡 STATUS UPDATE: Sent status '{status}' for project {project_id}")
        else:
            logger.warning(f"⚠️ STATUS UPDATE: No channel layer available")
            
    except Exception as e:
        logger.warning(f"⚠️ STATUS UPDATE: Failed to send status: {e}")
