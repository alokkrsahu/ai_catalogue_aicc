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

print("🔍 CHECKING EXECUTION HISTORY IN DATABASE")
print("=" * 60)

# Get the specific workflow we know about
workflow_id = "3e3335b5-3754-439f-99b0-95d984aa3354"

try:
    workflow = AgentWorkflow.objects.get(workflow_id=workflow_id)
    print(f"✅ Found workflow: {workflow.name}")
    print(f"   Project: {workflow.project.name}")
    print(f"   Total executions: {workflow.total_executions}")
    print(f"   Successful executions: {workflow.successful_executions}")
    
    # Get all executions from database
    executions = WorkflowExecution.objects.filter(workflow=workflow).order_by('-start_time')
    print(f"   Database executions: {executions.count()}")
    
    for i, execution in enumerate(executions):
        print(f"\n📈 Execution {i+1}: {execution.execution_id}")
        print(f"   Status: {execution.status}")
        print(f"   Start: {execution.start_time}")
        print(f"   End: {execution.end_time}")
        print(f"   Duration: {execution.duration_seconds}s")
        print(f"   Total messages: {execution.total_messages}")
        print(f"   Result: {execution.result_summary}")
        if execution.error_message:
            print(f"   Error: {execution.error_message}")
        
        # Check messages for this execution
        messages = WorkflowExecutionMessage.objects.filter(execution=execution).order_by('sequence')
        print(f"   Stored messages: {messages.count()}")
        
        for msg in messages[:3]:  # Show first 3 messages
            print(f"     - {msg.agent_name}: {msg.content[:50]}...")
    
    print(f"\n📊 SUMMARY:")
    print(f"   Total workflow executions: {workflow.total_executions}")
    print(f"   Database execution records: {executions.count()}")
    print(f"   Latest execution: {executions.first().start_time if executions.exists() else 'None'}")

except AgentWorkflow.DoesNotExist:
    print(f"❌ Workflow {workflow_id} not found")
except Exception as e:
    print(f"❌ Error: {e}")

print("\n" + "=" * 60)
print("✅ DATABASE CHECK COMPLETE")
