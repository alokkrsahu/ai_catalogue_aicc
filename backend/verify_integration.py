#!/usr/bin/env python3
"""
VERIFICATION SCRIPT: Project-Specific API Key Integration
=========================================================

This script verifies that all the fixes have been applied correctly
to integrate project-specific API keys into the LLM Provider system.

Run this script to verify the integration is complete.
"""

import os
import sys

def check_files_exist():
    """Check that all required files exist"""
    files_to_check = [
        '/Users/alok/Documents/AICC/ai_catalogue/ai_catalogue/backend/agent_orchestration/llm_provider_manager.py',
        '/Users/alok/Documents/AICC/ai_catalogue/ai_catalogue/backend/agent_orchestration/workflow_executor.py', 
        '/Users/alok/Documents/AICC/ai_catalogue/ai_catalogue/backend/agent_orchestration/chat_manager.py',
        '/Users/alok/Documents/AICC/ai_catalogue/ai_catalogue/backend/project_api_keys/services.py',
        '/Users/alok/Documents/AICC/ai_catalogue/ai_catalogue/.env'
    ]
    
    print("🔍 CHECKING REQUIRED FILES")
    print("=" * 50)
    
    all_exist = True
    for file_path in files_to_check:
        if os.path.exists(file_path):
            print(f"✅ {file_path}")
        else:
            print(f"❌ {file_path} - MISSING")
            all_exist = False
    
    return all_exist

def check_llm_provider_manager():
    """Check LLM provider manager has been updated"""
    print("\n🔍 CHECKING LLM PROVIDER MANAGER")
    print("=" * 50)
    
    try:
        with open('/Users/alok/Documents/AICC/ai_catalogue/ai_catalogue/backend/agent_orchestration/llm_provider_manager.py', 'r') as f:
            content = f.read()
        
        checks = [
            ('Project import', 'from users.models import IntelliDocProject'),
            ('Project service import', 'from project_api_keys.services import get_project_api_key_service'), 
            ('Project parameter', 'project: Optional[IntelliDocProject] = None'),
            ('Project API key method', '_get_api_key_for_provider'),
            ('Sync method', 'get_llm_provider_sync'),
            ('Project API service', 'self.project_api_service'),
        ]
        
        all_checks_pass = True
        for check_name, check_string in checks:
            if check_string in content:
                print(f"✅ {check_name}: Found")
            else:
                print(f"❌ {check_name}: NOT FOUND")
                all_checks_pass = False
        
        return all_checks_pass
        
    except Exception as e:
        print(f"❌ Error checking LLM Provider Manager: {e}")
        return False

def check_workflow_executor():
    """Check workflow executor has been updated"""
    print("\n🔍 CHECKING WORKFLOW EXECUTOR")
    print("=" * 50)
    
    try:
        with open('/Users/alok/Documents/AICC/ai_catalogue/ai_catalogue/backend/agent_orchestration/workflow_executor.py', 'r') as f:
            content = f.read()
        
        checks = [
            ('Project context', 'project = await sync_to_async(lambda: workflow.project)()'),
            ('Async LLM provider call', 'await self.llm_provider_manager.get_llm_provider(agent_config, project)'),
            ('Updated error message', 'check project API key configuration'),
        ]
        
        all_checks_pass = True
        for check_name, check_string in checks:
            if check_string in content:
                print(f"✅ {check_name}: Found")
            else:
                print(f"❌ {check_name}: NOT FOUND")
                all_checks_pass = False
        
        return all_checks_pass
        
    except Exception as e:
        print(f"❌ Error checking Workflow Executor: {e}")
        return False

def check_chat_manager():
    """Check chat manager has been updated"""
    print("\n🔍 CHECKING CHAT MANAGER")
    print("=" * 50)
    
    try:
        with open('/Users/alok/Documents/AICC/ai_catalogue/ai_catalogue/backend/agent_orchestration/chat_manager.py', 'r') as f:
            content = f.read()
        
        checks = [
            ('Project context delegate', 'await self.llm_provider_manager.get_llm_provider(delegate_config, project)'),
            ('Sync method fallback', 'get_llm_provider_sync'),
            ('Project lookup', 'IntelliDocProject.objects.get)(project_id=project_id)'),
        ]
        
        all_checks_pass = True
        for check_name, check_string in checks:
            if check_string in content:
                print(f"✅ {check_name}: Found")
            else:
                print(f"❌ {check_name}: NOT FOUND")
                all_checks_pass = False
        
        return all_checks_pass
        
    except Exception as e:
        print(f"❌ Error checking Chat Manager: {e}")
        return False

def check_environment():
    """Check environment configuration"""
    print("\n🔍 CHECKING ENVIRONMENT CONFIGURATION")
    print("=" * 50)
    
    try:
        with open('/Users/alok/Documents/AICC/ai_catalogue/ai_catalogue/.env', 'r') as f:
            content = f.read()
        
        has_project_key = 'PROJECT_API_KEY_ENCRYPTION_KEY=' in content and not content.count('PROJECT_API_KEY_ENCRYPTION_KEY=') == content.count('#PROJECT_API_KEY_ENCRYPTION_KEY=')
        
        if has_project_key:
            print("✅ PROJECT_API_KEY_ENCRYPTION_KEY: Set in .env")
            return True
        else:
            print("❌ PROJECT_API_KEY_ENCRYPTION_KEY: NOT SET or commented out")
            print("   Run: python3 generate_project_encryption_key.py")
            return False
            
    except Exception as e:
        print(f"❌ Error checking environment: {e}")
        return False

def main():
    """Run all verification checks"""
    print("🚀 PROJECT-SPECIFIC API KEY INTEGRATION VERIFICATION")
    print("=" * 60)
    
    files_ok = check_files_exist()
    llm_manager_ok = check_llm_provider_manager()
    executor_ok = check_workflow_executor() 
    chat_manager_ok = check_chat_manager()
    env_ok = check_environment()
    
    print("\n" + "=" * 60)
    print("📋 VERIFICATION SUMMARY")
    print("=" * 60)
    
    all_checks = [
        ("Required files exist", files_ok),
        ("LLM Provider Manager updated", llm_manager_ok),
        ("Workflow Executor updated", executor_ok),
        ("Chat Manager updated", chat_manager_ok), 
        ("Environment configured", env_ok),
    ]
    
    all_pass = True
    for check_name, passed in all_checks:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {check_name}")
        if not passed:
            all_pass = False
    
    if all_pass:
        print("\n🎉 ALL CHECKS PASSED!")
        print("✅ Project-specific API key integration is complete")
        print("\n🚀 NEXT STEPS:")
        print("1. Rebuild Docker containers: ./script/start-dev.sh")
        print("2. Test 'Tell me a poem' workflow")
        print("3. Should now use project-specific API keys instead of dummy values")
    else:
        print("\n❌ SOME CHECKS FAILED")
        print("Please fix the failed checks before testing")
    
    return 0 if all_pass else 1

if __name__ == "__main__":
    sys.exit(main())
