"""
Missing Agent Workflow Endpoints for UniversalProjectViewSet
These need to be added to universal_project_views.py
"""

    # ============================================================================
    # AGENT ORCHESTRATION ENDPOINTS (Missing from original file)
    # ============================================================================

    @action(detail=True, methods=['get', 'post'])
    def agent_workflows(self, request, project_id=None):
        """
        Universal agent workflows management
        GET /api/projects/{project_id}/agent_workflows/ - List workflows
        POST /api/projects/{project_id}/agent_workflows/ - Create workflow
        """
        project = self.get_object()
        
        if request.method == 'GET':
            logger.info(f"📋 UNIVERSAL: Getting agent workflows for project {project.name} ({project_id})")
            
            try:
                # Get all workflows for this project
                workflows = AgentWorkflow.objects.filter(project=project).order_by('-updated_at')
                serializer = AgentWorkflowSerializer(workflows, many=True)
                
                # Calculate statistics
                total_workflows = workflows.count()
                active_workflows = workflows.filter(status='active').count()
                draft_workflows = workflows.filter(status='draft').count()
                
                response_data = {
                    'workflows': serializer.data,
                    'total_count': total_workflows,
                    'statistics': {
                        'active_workflows': active_workflows,
                        'draft_workflows': draft_workflows,
                        'archived_workflows': workflows.filter(status='archived').count()
                    },
                    'project_id': project_id,
                    'project_name': project.name,
                    'template_type': project.template_type,
                    'api_version': 'universal_v1',
                    'retrieved_at': timezone.now().isoformat()
                }
                
                logger.info(f"✅ UNIVERSAL: Retrieved {total_workflows} agent workflows for project {project_id}")
                return Response(response_data, status=status.HTTP_200_OK)
                
            except Exception as e:
                logger.error(f"❌ UNIVERSAL: Failed to get agent workflows for project {project_id}: {e}")
                return Response({
                    'error': 'Failed to retrieve agent workflows',
                    'message': str(e),
                    'project_id': project_id,
                    'api_version': 'universal_v1'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        elif request.method == 'POST':
            logger.info(f"🤖 UNIVERSAL: Creating agent workflow for project {project.name} ({project_id})")
            
            try:
                # Add project to workflow data
                workflow_data = {
                    **request.data,
                    'project': project.id
                }
                
                serializer = AgentWorkflowSerializer(data=workflow_data)
                if serializer.is_valid():
                    workflow = serializer.save(created_by=request.user, project=project)
                    
                    response_data = {
                        **serializer.data,
                        'message': 'Agent workflow created successfully',
                        'project_id': project_id,
                        'project_name': project.name,
                        'api_version': 'universal_v1',
                        'created_at': timezone.now().isoformat()
                    }
                    
                    logger.info(f"✅ UNIVERSAL: Created agent workflow {workflow.name} for project {project_id}")
                    return Response(response_data, status=status.HTTP_201_CREATED)
                else:
                    logger.error(f"❌ UNIVERSAL: Agent workflow validation failed: {serializer.errors}")
                    return Response({
                        'error': 'Validation failed',
                        'details': serializer.errors,
                        'project_id': project_id,
                        'api_version': 'universal_v1'
                    }, status=status.HTTP_400_BAD_REQUEST)
                    
            except Exception as e:
                logger.error(f"❌ UNIVERSAL: Failed to create agent workflow for project {project_id}: {e}")
                return Response({
                    'error': 'Failed to create agent workflow',
                    'message': str(e),
                    'project_id': project_id,
                    'api_version': 'universal_v1'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['get', 'put', 'delete'])
    def agent_workflow(self, request, project_id=None):
        """
        Universal single agent workflow management
        GET /api/projects/{project_id}/agent_workflow/?workflow_id={id} - Get workflow
        PUT /api/projects/{project_id}/agent_workflow/?workflow_id={id} - Update workflow  
        DELETE /api/projects/{project_id}/agent_workflow/?workflow_id={id} - Delete workflow
        """
        project = self.get_object()
        workflow_id = request.query_params.get('workflow_id')
        
        if not workflow_id:
            return Response({
                'error': 'workflow_id parameter required',
                'message': 'Please provide workflow_id as query parameter',
                'api_version': 'universal_v1'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            workflow = AgentWorkflow.objects.get(
                workflow_id=workflow_id,
                project=project
            )
        except AgentWorkflow.DoesNotExist:
            return Response({
                'error': 'Agent workflow not found',
                'message': f'Workflow {workflow_id} not found in project {project_id}',
                'api_version': 'universal_v1'
            }, status=status.HTTP_404_NOT_FOUND)
        
        if request.method == 'GET':
            logger.info(f"📄 UNIVERSAL: Getting agent workflow {workflow_id} for project {project_id}")
            
            try:
                serializer = AgentWorkflowSerializer(workflow)
                
                response_data = {
                    **serializer.data,
                    'project_id': project_id,
                    'project_name': project.name,
                    'api_version': 'universal_v1',
                    'retrieved_at': timezone.now().isoformat()
                }
                
                logger.info(f"✅ UNIVERSAL: Retrieved agent workflow {workflow.name}")
                return Response(response_data, status=status.HTTP_200_OK)
                
            except Exception as e:
                logger.error(f"❌ UNIVERSAL: Failed to get agent workflow {workflow_id}: {e}")
                return Response({
                    'error': 'Failed to retrieve agent workflow',
                    'message': str(e),
                    'workflow_id': workflow_id,
                    'project_id': project_id,
                    'api_version': 'universal_v1'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        elif request.method == 'PUT':
            logger.info(f"📝 UNIVERSAL: Updating agent workflow {workflow_id} for project {project_id}")
            
            try:
                serializer = AgentWorkflowSerializer(workflow, data=request.data, partial=True)
                if serializer.is_valid():
                    updated_workflow = serializer.save()
                    
                    response_data = {
                        **serializer.data,
                        'message': 'Agent workflow updated successfully',
                        'project_id': project_id,
                        'project_name': project.name,
                        'api_version': 'universal_v1',
                        'updated_at': timezone.now().isoformat()
                    }
                    
                    logger.info(f"✅ UNIVERSAL: Updated agent workflow {updated_workflow.name}")
                    return Response(response_data, status=status.HTTP_200_OK)
                else:
                    logger.error(f"❌ UNIVERSAL: Agent workflow update validation failed: {serializer.errors}")
                    return Response({
                        'error': 'Validation failed',
                        'details': serializer.errors,
                        'workflow_id': workflow_id,
                        'project_id': project_id,
                        'api_version': 'universal_v1'
                    }, status=status.HTTP_400_BAD_REQUEST)
                    
            except Exception as e:
                logger.error(f"❌ UNIVERSAL: Failed to update agent workflow {workflow_id}: {e}")
                return Response({
                    'error': 'Failed to update agent workflow',
                    'message': str(e),
                    'workflow_id': workflow_id,
                    'project_id': project_id,
                    'api_version': 'universal_v1'  
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        elif request.method == 'DELETE':
            logger.info(f"🗑️ UNIVERSAL: Deleting agent workflow {workflow_id} for project {project_id}")
            
            try:
                workflow_name = workflow.name
                workflow.delete()
                
                response_data = {
                    'message': 'Agent workflow deleted successfully',
                    'workflow_name': workflow_name,
                    'workflow_id': workflow_id,
                    'project_id': project_id,
                    'project_name': project.name,
                    'api_version': 'universal_v1',
                    'deleted_at': timezone.now().isoformat()
                }
                
                logger.info(f"✅ UNIVERSAL: Deleted agent workflow {workflow_name}")
                return Response(response_data, status=status.HTTP_200_OK)
                
            except Exception as e:
                logger.error(f"❌ UNIVERSAL: Failed to delete agent workflow {workflow_id}: {e}")
                return Response({
                    'error': 'Failed to delete agent workflow',
                    'message': str(e),
                    'workflow_id': workflow_id,
                    'project_id': project_id,
                    'api_version': 'universal_v1'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def execute_workflow(self, request, project_id=None):
        """
        Universal workflow execution
        POST /api/projects/{project_id}/execute_workflow/
        """
        project = self.get_object()
        workflow_id = request.data.get('workflow_id')
        execution_parameters = request.data.get('execution_parameters', {})
        
        if not workflow_id:
            return Response({
                'error': 'workflow_id required',
                'message': 'Please provide workflow_id in request body',
                'api_version': 'universal_v1'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            workflow = AgentWorkflow.objects.get(
                workflow_id=workflow_id,
                project=project
            )
        except AgentWorkflow.DoesNotExist:
            return Response({
                'error': 'Agent workflow not found',
                'message': f'Workflow {workflow_id} not found in project {project_id}',
                'api_version': 'universal_v1'
            }, status=status.HTTP_404_NOT_FOUND)
        
        logger.info(f"🚀 UNIVERSAL: Executing agent workflow {workflow.name} for project {project_id}")
        
        try:
            # Create simulation run
            simulation_run = SimulationRun.objects.create(
                workflow=workflow,
                graph_snapshot=workflow.graph_json,
                execution_parameters=execution_parameters,
                executed_by=request.user,
                status='pending'
            )
            
            # Start background task for workflow execution
            from agent_orchestration.tasks import execute_agent_workflow
            celery_task = execute_agent_workflow.delay(str(simulation_run.run_id))
            
            # Update simulation run with task ID
            simulation_run.celery_task_id = celery_task.id
            simulation_run.save()
            
            response_data = {
                'status': 'started',
                'message': 'Agent workflow execution started successfully',
                'run_id': str(simulation_run.run_id),
                'workflow_id': str(workflow_id),
                'workflow_name': workflow.name,
                'project_id': project_id,
                'project_name': project.name,
                'celery_task_id': celery_task.id,
                'execution_parameters': execution_parameters,
                'api_version': 'universal_v1',
                'started_at': timezone.now().isoformat()
            }
            
            logger.info(f"✅ UNIVERSAL: Started execution of workflow {workflow.name} with run ID {simulation_run.run_id}")
            return Response(response_data, status=status.HTTP_202_ACCEPTED)
            
        except Exception as e:
            logger.error(f"❌ UNIVERSAL: Workflow execution failed for project {project_id}: {e}")
            return Response({
                'error': 'Execution failed',
                'message': str(e),
                'project_id': project_id,
                'workflow_id': str(workflow_id),
                'api_version': 'universal_v1'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
