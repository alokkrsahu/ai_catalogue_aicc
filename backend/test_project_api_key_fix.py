#!/usr/bin/env python3
"""
Test script to verify project-specific API key functionality
"""

import os
import sys
import django

# Setup Django
sys.path.append('/Users/alok/Documents/AICC/ai_catalogue/ai_catalogue/backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from users.models import IntelliDocProject, User
from project_api_keys.services import get_project_api_key_service
from agent_orchestration.dynamic_models_service import dynamic_models_service

def test_project_api_key_retrieval():
    """Test project-specific API key retrieval"""
    print("🔧 Testing project-specific API key retrieval...")
    
    try:
        # Get a test user and project
        user = User.objects.first()
        if not user:
            print("❌ No users found in database")
            return
        
        project = IntelliDocProject.objects.filter(created_by=user).first()
        if not project:
            print("❌ No projects found for user")
            return
        
        print(f"📋 Testing with user: {user.username}")
        print(f"📋 Testing with project: {project.name} ({project.project_id})")
        
        # Test project API key service
        project_service = get_project_api_key_service()
        
        # Test getting OpenAI API key
        openai_key = project_service.get_project_api_key(project, 'openai')
        print(f"🔑 OpenAI project key found: {'Yes' if openai_key else 'No'}")
        if openai_key:
            print(f"🔑 OpenAI key starts with: {openai_key[:10]}...")
        
        # Test dynamic models service with project context
        print("\n🔧 Testing dynamic models service with project context...")
        
        # Test provider status with project
        openai_status = dynamic_models_service.get_provider_status('openai', project)
        print(f"🔍 OpenAI status: {openai_status}")
        
        # Test API key retrieval in dynamic service
        api_key = dynamic_models_service.get_api_key_for_provider('openai', project)
        print(f"🔑 Dynamic service API key found: {'Yes' if api_key else 'No'}")
        
        if openai_status['api_key_valid']:
            print("✅ Project-specific API key is working!")
        else:
            print("❌ Project-specific API key validation failed")
            print(f"❌ Error: {openai_status['message']}")
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_project_api_key_retrieval()