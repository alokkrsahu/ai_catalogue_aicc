#!/usr/bin/env python3
# Check and apply agent orchestration migrations

import os
import sys
import django
from django.core.management import execute_from_command_line

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
sys.path.append('/Users/alok/Documents/AICC/ai_catalogue/ai_catalogue/backend')

django.setup()

def check_migrations():
    """Check and apply pending migrations"""
    print("🔍 Checking for pending migrations...")
    
    # Check for unapplied migrations
    from django.core.management.commands.migrate import Command as MigrateCommand
    from django.core.management.base import CommandError
    
    try:
        # First, make migrations if needed
        print("📝 Making migrations...")
        execute_from_command_line(['manage.py', 'makemigrations'])
        
        # Then apply migrations
        print("🚀 Applying migrations...")
        execute_from_command_line(['manage.py', 'migrate'])
        
        print("✅ Migrations completed successfully!")
        
    except Exception as e:
        print(f"❌ Migration error: {e}")
        
    # Check if AgentWorkflow model exists
    try:
        from users.models import AgentWorkflow
        print("✅ AgentWorkflow model is available")
        
        # Check if we can query the model
        workflow_count = AgentWorkflow.objects.count()
        print(f"📊 Current workflow count: {workflow_count}")
        
    except Exception as e:
        print(f"❌ AgentWorkflow model error: {e}")

if __name__ == "__main__":
    check_migrations()
