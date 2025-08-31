# backend/agent_orchestration/simple_workflow_views.py

from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.utils import timezone
import logging
import uuid
import asyncio

from users.models import IntelliDocProject, AgentWorkflow
from .conversation_orchestrator import conversation_orchestrator

logger = logging.getLogger(__name__)

class SimpleAgentWorkflowViewSet(viewsets.ViewSet):
    """
    Simplified ViewSet for managing agent workflows within projects
    """
    permission_classes = [IsAuthenticated]
    
    def list(self, request, project_id=None):
        """List workflows for a project"""
        try:
            logger.info(f"🔍 SIMPLE: Listing workflows for project {project_id}")
            
            # Get project
            project = get_object_or_404(IntelliDocProject, project_id=project_id)
            
            # Get workflows for this project and user
            workflows = AgentWorkflow.objects.filter(
                project=project, 
                created_by=request.user
            ).order_by('-updated_at')
            
            # Build simple response data
            workflow_data = []
            for workflow in workflows:
                try:
                    workflow_item = {
                        'workflow_id': str(workflow.workflow_id),
                        'name': workflow.name,
                        'description': workflow.description,
                        'status': workflow.status,
                        'created_at': workflow.created_at.isoformat() if workflow.created_at else None,
                        'updated_at': workflow.updated_at.isoformat() if workflow.updated_at else None,
                        'graph_json': workflow.graph_json or {'nodes': [], 'edges': []},
                        'node_count': len(workflow.graph_json.get('nodes', [])) if workflow.graph_json else 0,
                        'edge_count': len(workflow.graph_json.get('edges', [])) if workflow.graph_json else 0
                    }
                    workflow_data.append(workflow_item)
                except Exception as e:
                    logger.error(f"❌ SIMPLE: Error processing workflow {workflow.workflow_id}: {e}")
            
            logger.info(f"✅ SIMPLE: Found {len(workflow_data)} workflows")
            
            return Response({
                'data': workflow_data,
                'count': len(workflow_data),
                'project_id': str(project_id)
            })
            
        except Exception as e:
            logger.error(f"❌ SIMPLE: Error listing workflows: {e}")
            return Response({
                'error': 'Failed to list workflows',
                'detail': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def create(self, request, project_id=None):
        """Create a new workflow"""
        try:
            logger.info(f"🆕 SIMPLE: Creating workflow for project {project_id}")
            
            # Get project
            project = get_object_or_404(IntelliDocProject, project_id=project_id)
            
            # Ensure user has access
            if project.created_by != request.user:
                return Response({
                    'error': 'Permission denied'
                }, status=status.HTTP_403_FORBIDDEN)
            
            # Get data from request
            data = request.data
            name = data.get('name', f'Workflow {timezone.now().strftime("%Y%m%d_%H%M%S")}')
            description = data.get('description', 'New agent orchestration workflow')
            graph_json = data.get('graph_json', {'nodes': [], 'edges': []})
            
            # Create workflow
            workflow = AgentWorkflow.objects.create(
                project=project,
                created_by=request.user,
                name=name,
                description=description,
                graph_json=graph_json,
                status='draft'
            )
            
            logger.info(f"✅ SIMPLE: Created workflow {workflow.workflow_id}")
            
            return Response({
                'workflow_id': str(workflow.workflow_id),
                'name': workflow.name,
                'description': workflow.description,
                'status': workflow.status,
                'created_at': workflow.created_at.isoformat(),
                'graph_json': workflow.graph_json,
                'message': 'Workflow created successfully'
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"❌ SIMPLE: Error creating workflow: {e}")
            return Response({
                'error': 'Failed to create workflow',
                'detail': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def retrieve(self, request, project_id=None, workflow_id=None):
        """Get a specific workflow"""
        try:
            logger.info(f"📄 SIMPLE: Retrieving workflow {workflow_id}")
            
            # Get project and workflow
            project = get_object_or_404(IntelliDocProject, project_id=project_id)
            workflow = get_object_or_404(
                AgentWorkflow, 
                workflow_id=workflow_id, 
                project=project,
                created_by=request.user
            )
            
            return Response({
                'workflow_id': str(workflow.workflow_id),
                'name': workflow.name,
                'description': workflow.description,
                'status': workflow.status,
                'created_at': workflow.created_at.isoformat(),
                'updated_at': workflow.updated_at.isoformat(),
                'graph_json': workflow.graph_json
            })
            
        except Exception as e:
            logger.error(f"❌ SIMPLE: Error retrieving workflow: {e}")
            return Response({
                'error': 'Failed to retrieve workflow',
                'detail': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def partial_update(self, request, project_id=None, workflow_id=None):
        """Update a workflow"""
        try:
            logger.info(f"📝 SIMPLE: Updating workflow {workflow_id}")
            
            # Get project and workflow
            project = get_object_or_404(IntelliDocProject, project_id=project_id)
            workflow = get_object_or_404(
                AgentWorkflow, 
                workflow_id=workflow_id, 
                project=project,
                created_by=request.user
            )
            
            # Update fields
            data = request.data
            if 'name' in data:
                workflow.name = data['name']
            if 'description' in data:
                workflow.description = data['description']
            if 'graph_json' in data:
                workflow.graph_json = data['graph_json']
            if 'status' in data:
                workflow.status = data['status']
            
            workflow.updated_at = timezone.now()
            workflow.save()
            
            logger.info(f"✅ SIMPLE: Updated workflow {workflow.workflow_id}")
            
            return Response({
                'workflow_id': str(workflow.workflow_id),
                'name': workflow.name,
                'description': workflow.description,
                'status': workflow.status,
                'updated_at': workflow.updated_at.isoformat(),
                'graph_json': workflow.graph_json,
                'message': 'Workflow updated successfully'
            })
            
        except Exception as e:
            logger.error(f"❌ SIMPLE: Error updating workflow: {e}")
            return Response({
                'error': 'Failed to update workflow',
                'detail': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def update(self, request, project_id=None, workflow_id=None):
        """Full update of a workflow (PUT method)"""
        return self.partial_update(request, project_id, workflow_id)
    
    def destroy(self, request, project_id=None, workflow_id=None):
        """Delete a workflow"""
        try:
            logger.info(f"🗝 SIMPLE: Deleting workflow {workflow_id}")
            
            # Get project and workflow
            project = get_object_or_404(IntelliDocProject, project_id=project_id)
            workflow = get_object_or_404(
                AgentWorkflow, 
                workflow_id=workflow_id, 
                project=project,
                created_by=request.user
            )
            
            workflow_name = workflow.name
            workflow.delete()
            
            logger.info(f"✅ SIMPLE: Deleted workflow {workflow_id}")
            
            return Response({
                'message': f'Workflow "{workflow_name}" deleted successfully',
                'workflow_id': str(workflow_id)
            }, status=status.HTTP_204_NO_CONTENT)
            
        except Exception as e:
            logger.error(f"❌ SIMPLE: Error deleting workflow: {e}")
            return Response({
                'error': 'Failed to delete workflow',
                'detail': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def execute(self, request, project_id=None, workflow_id=None):
        """
        Execute a workflow with real conversation orchestration
        """
        try:
            logger.info(f"🚀 SIMPLE: Executing workflow {workflow_id} for project {project_id}")
            
            # Get project and workflow
            project = get_object_or_404(IntelliDocProject, project_id=project_id)
            workflow = get_object_or_404(
                AgentWorkflow, 
                workflow_id=workflow_id, 
                project=project,
                created_by=request.user
            )
            
            # Validate workflow has nodes
            if not workflow.graph_json.get('nodes'):
                return Response({
                    'error': 'Workflow has no nodes to execute',
                    'detail': 'Please add agents to your workflow before executing'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            logger.info(f"🤖 SIMPLE: Starting real conversation orchestration for {workflow_id}")
            
            # Execute workflow using conversation orchestrator
            try:
                # Run async orchestration in sync context
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                run = loop.run_until_complete(
                    conversation_orchestrator.execute_workflow(workflow, request.user)
                )
                loop.close()
                
                logger.info(f"✅ SIMPLE: Real workflow execution completed for {workflow_id}")
                
                return Response({
                    'status': 'success',
                    'message': f'Workflow "{workflow.name}" executed successfully with real agent conversations',
                    'workflow_id': str(workflow.workflow_id),
                    'run_id': str(run.run_id),
                    'executed_at': run.start_time.isoformat(),
                    'execution_mode': 'real_conversation_orchestration',
                    'execution_summary': {
                        'total_messages': run.total_messages,
                        'agents_involved': run.total_agents_involved,
                        'average_response_time_ms': run.average_response_time,
                        'duration': run.formatted_duration,
                        'status': run.status
                    },
                    'graph_data': {
                        'nodes': len(workflow.graph_json.get('nodes', [])),
                        'edges': len(workflow.graph_json.get('edges', []))
                    }
                })
                
            except Exception as execution_error:
                logger.error(f"❌ SIMPLE: Workflow execution failed: {execution_error}")
                return Response({
                    'error': 'Workflow execution failed',
                    'detail': str(execution_error),
                    'execution_mode': 'real_conversation_orchestration'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
        except Exception as e:
            logger.error(f"❌ SIMPLE: Error executing workflow: {e}")
            return Response({
                'error': 'Failed to execute workflow',
                'detail': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def history(self, request, project_id=None, workflow_id=None):
        """
        Get execution history for a workflow with real conversation data
        """
        try:
            logger.info(f"📊 SIMPLE: Getting history for workflow {workflow_id}")
            
            # Get project and workflow
            project = get_object_or_404(IntelliDocProject, project_id=project_id)
            workflow = get_object_or_404(
                AgentWorkflow, 
                workflow_id=workflow_id, 
                project=project,
                created_by=request.user
            )
            
            # Get execution summary using conversation orchestrator
            execution_summary = conversation_orchestrator.get_workflow_execution_summary(workflow)
            
            logger.info(f"✅ SIMPLE: Retrieved execution history for {workflow_id}")
            
            return Response(execution_summary)
            
        except Exception as e:
            logger.error(f"❌ SIMPLE: Error getting workflow history: {e}")
            return Response({
                'error': 'Failed to get workflow history',
                'detail': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def validate(self, request, project_id=None, workflow_id=None):
        """
        Validate workflow structure and configuration
        """
        try:
            logger.info(f"✅ SIMPLE: Validating workflow {workflow_id}")
            
            # Get project and workflow
            project = get_object_or_404(IntelliDocProject, project_id=project_id)
            workflow = get_object_or_404(
                AgentWorkflow, 
                workflow_id=workflow_id, 
                project=project,
                created_by=request.user
            )
            
            errors = []
            warnings = []
            
            # Basic validation
            graph_json = workflow.graph_json or {'nodes': [], 'edges': []}
            nodes = graph_json.get('nodes', [])
            edges = graph_json.get('edges', [])
            
            # Check for required nodes
            if not nodes:
                errors.append("Workflow must contain at least one node")
            
            # Check for Start Node
            start_nodes = [n for n in nodes if n.get('type') == 'StartNode']
            if not start_nodes:
                warnings.append("Workflow should contain a Start Node")
            elif len(start_nodes) > 1:
                warnings.append("Workflow should contain only one Start Node")
            
            # Check for End Node
            end_nodes = [n for n in nodes if n.get('type') == 'EndNode']
            if not end_nodes:
                warnings.append("Workflow should contain an End Node")
            
            # Check for orphaned nodes
            if len(nodes) > 1:
                node_ids = set(n['id'] for n in nodes)
                connected_nodes = set()
                for edge in edges:
                    connected_nodes.add(edge['source'])
                    connected_nodes.add(edge['target'])
                
                orphaned_nodes = node_ids - connected_nodes
                if orphaned_nodes:
                    warnings.append(f"Found {len(orphaned_nodes)} disconnected nodes")
            
            # Update workflow status if valid
            if not errors:
                workflow.status = 'validated'
                workflow.save()
            
            return Response({
                'valid': len(errors) == 0,
                'errors': errors,
                'warnings': warnings,
                'status': workflow.status,
                'validated_at': timezone.now().isoformat(),
                'node_count': len(nodes),
                'edge_count': len(edges)
            })
            
        except Exception as e:
            logger.error(f"❌ SIMPLE: Error validating workflow: {e}")
            return Response({
                'error': 'Failed to validate workflow',
                'detail': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def conversation(self, request, project_id=None, workflow_id=None):
        """
        Get detailed conversation history for a specific run
        """
        try:
            run_id = request.GET.get('run_id')
            if not run_id:
                return Response({
                    'error': 'run_id parameter is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            logger.info(f"💬 SIMPLE: Getting conversation for run {run_id}")
            
            # Get project and workflow
            project = get_object_or_404(IntelliDocProject, project_id=project_id)
            workflow = get_object_or_404(
                AgentWorkflow, 
                workflow_id=workflow_id, 
                project=project,
                created_by=request.user
            )
            
            # Get the specific run
            from users.models import SimulationRun
            run = get_object_or_404(
                SimulationRun,
                run_id=run_id,
                workflow=workflow
            )
            
            # Get conversation history using orchestrator
            conversation_history = conversation_orchestrator.get_conversation_history_for_run(run)
            
            logger.info(f"✅ SIMPLE: Retrieved {len(conversation_history)} messages for run {run_id}")
            
            return Response({
                'run_id': str(run.run_id),
                'workflow_id': str(workflow.workflow_id),
                'workflow_name': workflow.name,
                'execution_status': run.status,
                'start_time': run.start_time.isoformat(),
                'end_time': run.end_time.isoformat() if run.end_time else None,
                'duration': run.formatted_duration,
                'total_messages': run.total_messages,
                'conversation_history': conversation_history,
                'execution_summary': {
                    'agents_involved': run.total_agents_involved,
                    'average_response_time_ms': run.average_response_time,
                    'error_message': run.error_message if run.error_message else None
                }
            })
            
        except Exception as e:
            logger.error(f"❌ SIMPLE: Error getting conversation: {e}")
            return Response({
                'error': 'Failed to get conversation history',
                'detail': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
