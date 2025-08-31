#!/usr/bin/env python

import os
import sys
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
sys.path.append('/Users/alok/Documents/AICC/ai_catalogue/ai_catalogue/backend')

try:
    django.setup()
    
    # Test imports
    print("🔄 Testing model imports...")
    
    from users.models import AgentWorkflow, WorkflowExecution, WorkflowExecutionMessage, WorkflowExecutionStatus
    print("✅ All models imported successfully!")
    
    # Test basic functionality
    print("🔄 Testing model structure...")
    
    # Check if models have the expected fields
    workflow_fields = [f.name for f in WorkflowExecution._meta.fields]
    message_fields = [f.name for f in WorkflowExecutionMessage._meta.fields]
    
    expected_workflow_fields = ['workflow', 'execution_id', 'status', 'start_time', 'end_time', 'duration_seconds']
    expected_message_fields = ['execution', 'sequence', 'agent_name', 'content', 'message_type']
    
    for field in expected_workflow_fields:
        if field in workflow_fields:
            print(f"  ✅ WorkflowExecution.{field}")
        else:
            print(f"  ❌ WorkflowExecution.{field} missing")
    
    for field in expected_message_fields:
        if field in message_fields:
            print(f"  ✅ WorkflowExecutionMessage.{field}")
        else:
            print(f"  ❌ WorkflowExecutionMessage.{field} missing")
    
    print("🎉 Model structure test completed!")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
