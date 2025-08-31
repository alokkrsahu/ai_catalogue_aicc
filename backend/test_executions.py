#!/usr/bin/env python3

import os
import sys
import django

# Add the backend directory to Python path
sys.path.append('/Users/alok/Documents/AICC/ai_catalogue/ai_catalogue/backend')

# Set Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ai_catalogue.settings')

# Initialize Django
django.setup()

from users.models import AgentWorkflow, WorkflowExecution, WorkflowExecutionMessage

print("🔍 CHECKING WORKFLOW EXECUTIONS")
print("=" * 50)

# Get all workflows
workflows = AgentWorkflow.objects.all()
print(f"📊 Total workflows: {workflows.count()}")

for workflow in workflows:
    print(f"\n🔧 Workflow: {workflow.name} ({workflow.workflow_id})")
    print(f"   Project: {workflow.project.name}")
    print(f"   Total executions: {workflow.total_executions}")
    print(f"   Successful executions: {workflow.successful_executions}")
    
    # Get executions for this workflow
    executions = WorkflowExecution.objects.filter(workflow=workflow).order_by('-start_time')
    print(f"   Database executions: {executions.count()}")
    
    for execution in executions[:5]:  # Show last 5 executions
        print(f"   📈 Execution {execution.execution_id}: {execution.status}")
        print(f"      Start: {execution.start_time}")
        print(f"      Duration: {execution.duration_seconds}s")
        print(f"      Messages: {execution.total_messages}")
        if execution.error_message:
            print(f"      Error: {execution.error_message}")
        
        # Count messages
        message_count = WorkflowExecutionMessage.objects.filter(execution=execution).count()
        print(f"      Stored messages: {message_count}")

print("\n✅ EXECUTION CHECK COMPLETE")
