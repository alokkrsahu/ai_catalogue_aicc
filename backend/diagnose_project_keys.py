#!/usr/bin/env python3
"""
Comprehensive diagnostic script to check:
1. Environment variables (API keys and encryption keys)
2. Project API key encryption system
3. LLM provider initialization
4. Project API key status

Run this inside the Docker container to diagnose issues.
"""

import os
import sys
import django
from pathlib import Path

# Add the backend directory to Python path
backend_dir = Path(__file__).parent
sys.path.append(str(backend_dir))

# Set Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ai_catalogue.settings')

# Initialize Django
try:
    django.setup()
    print("✅ Django initialized successfully")
except Exception as e:
    print(f"❌ Django initialization failed: {e}")
    sys.exit(1)

def check_environment_variables():
    """Check critical environment variables"""
    print("\n" + "="*60)
    print("🔍 CHECKING ENVIRONMENT VARIABLES")
    print("="*60)
    
    # API Keys
    api_keys = {
        'OPENAI_API_KEY': 'OpenAI API Key',
        'GOOGLE_API_KEY': 'Google Gemini API Key', 
        'ANTHROPIC_API_KEY': 'Anthropic Claude API Key'
    }
    
    for key, description in api_keys.items():
        value = os.getenv(key)
        if value:
            if value == 'Dummy-Key':
                print(f"⚠️  {description}: DUMMY VALUE - needs real key")
            elif len(value) < 10:
                print(f"⚠️  {description}: Too short ({len(value)} chars)")
            else:
                masked = f"{value[:6]}...{value[-4:]}" if len(value) > 10 else "***"
                print(f"✅ {description}: Loaded ({masked}, {len(value)} chars)")
        else:
            print(f"❌ {description}: NOT SET")
    
    # Encryption Keys
    print("\n🔐 ENCRYPTION KEYS:")
    encryption_keys = {
        'PROJECT_API_KEY_ENCRYPTION_KEY': 'Project API Key Encryption',
        'API_KEY_ENCRYPTION_KEY': 'General API Key Encryption'
    }
    
    for key, description in encryption_keys.items():
        value = os.getenv(key)
        if value:
            print(f"✅ {description}: Set ({len(value)} chars)")
        else:
            print(f"❌ {description}: NOT SET")
    
    return bool(os.getenv('PROJECT_API_KEY_ENCRYPTION_KEY'))

def test_project_encryption():
    """Test the project API key encryption system"""
    print("\n" + "="*60)
    print("🔐 TESTING PROJECT API KEY ENCRYPTION")
    print("="*60)
    
    try:
        from project_api_keys.encryption import encryption_service
        
        # Test encryption/decryption
        test_project_id = "test-project-12345"
        test_api_key = "sk-test-api-key-67890"
        
        print("🔧 Testing encryption service...")
        
        # Encrypt
        try:
            encrypted = encryption_service.encrypt_api_key(test_project_id, test_api_key)
            print(f"✅ Encryption successful: {len(encrypted)} characters")
        except Exception as e:
            print(f"❌ Encryption failed: {e}")
            return False
        
        # Decrypt
        try:
            decrypted = encryption_service.decrypt_api_key(test_project_id, encrypted)
            if decrypted == test_api_key:
                print("✅ Decryption successful: Keys match")
                return True
            else:
                print("❌ Decryption failed: Keys don't match")
                return False
        except Exception as e:
            print(f"❌ Decryption failed: {e}")
            return False
            
    except ImportError as e:
        print(f"❌ Cannot import encryption service: {e}")
        return False
    except Exception as e:
        print(f"❌ Encryption system error: {e}")
        return False

def test_llm_providers():
    """Test LLM provider initialization"""
    print("\n" + "="*60)
    print("🤖 TESTING LLM PROVIDERS")
    print("="*60)
    
    try:
        from agent_orchestration.llm_provider_manager import LLMProviderManager
        
        manager = LLMProviderManager()
        print("✅ LLM Provider Manager initialized")
        
        # Test different provider configurations
        providers_to_test = [
            {'llm_provider': 'openai', 'llm_model': 'gpt-4'},
            {'llm_provider': 'google', 'llm_model': 'gemini-pro'},
            {'llm_provider': 'anthropic', 'llm_model': 'claude-3-sonnet'}
        ]
        
        for config in providers_to_test:
            provider_type = config['llm_provider']
            try:
                provider = manager.get_llm_provider(config)
                if provider:
                    print(f"✅ {provider_type.title()} provider: Created successfully")
                else:
                    print(f"❌ {provider_type.title()} provider: Failed to create (likely missing API key)")
            except Exception as e:
                print(f"❌ {provider_type.title()} provider: Error - {e}")
                
    except ImportError as e:
        print(f"❌ Cannot import LLM Provider Manager: {e}")
    except Exception as e:
        print(f"❌ LLM Provider Manager error: {e}")

def check_project_api_keys():
    """Check existing project API keys"""
    print("\n" + "="*60)
    print("🔑 CHECKING PROJECT API KEYS")
    print("="*60)
    
    try:
        from users.models import IntelliDocProject, ProjectAPIKey
        
        projects = IntelliDocProject.objects.all()[:5]  # Check first 5 projects
        print(f"📊 Found {IntelliDocProject.objects.count()} total projects")
        
        if not projects:
            print("ℹ️  No projects found in database")
            return
        
        api_keys = ProjectAPIKey.objects.all()
        print(f"📊 Found {api_keys.count()} total project API keys")
        
        for project in projects:
            print(f"\n🔹 Project: {project.name} ({project.project_id})")
            
            project_keys = ProjectAPIKey.objects.filter(project=project)
            if project_keys:
                for key in project_keys:
                    status = "✅ Active" if key.is_active else "❌ Inactive"
                    validated = "✅ Validated" if key.is_validated else "⚠️ Not validated"
                    print(f"   {key.get_provider_type_display()}: {status}, {validated}")
                    if key.validation_error:
                        print(f"     Error: {key.validation_error}")
            else:
                print("   No API keys configured")
                
    except Exception as e:
        print(f"❌ Error checking project API keys: {e}")

def main():
    """Run all diagnostic checks"""
    print("🚀 PROJECT API KEY DIAGNOSTIC TOOL")
    print("="*60)
    print(f"📍 Running from: {Path(__file__).parent}")
    print(f"🐍 Python version: {sys.version}")
    print(f"📦 Django version: {django.get_version()}")
    
    # Run checks
    has_encryption_key = check_environment_variables()
    
    if has_encryption_key:
        encryption_works = test_project_encryption()
    else:
        print("\n⚠️  PROJECT_API_KEY_ENCRYPTION_KEY not set - skipping encryption tests")
        encryption_works = False
    
    test_llm_providers()
    check_project_api_keys()
    
    # Summary
    print("\n" + "="*60)
    print("📋 DIAGNOSTIC SUMMARY")
    print("="*60)
    
    if not has_encryption_key:
        print("❌ CRITICAL: PROJECT_API_KEY_ENCRYPTION_KEY not set")
        print("   Fix: Run 'python3 generate_encryption_key.py' and add to .env")
    elif not encryption_works:
        print("❌ CRITICAL: Encryption system not working")
        print("   Check: PROJECT_API_KEY_ENCRYPTION_KEY value in environment")
    else:
        print("✅ Encryption system working correctly")
    
    # Check if any real API keys are set
    has_real_keys = False
    for key in ['OPENAI_API_KEY', 'GOOGLE_API_KEY', 'ANTHROPIC_API_KEY']:
        value = os.getenv(key)
        if value and value != 'Dummy-Key' and len(value) > 10:
            has_real_keys = True
            break
    
    if not has_real_keys:
        print("⚠️  WARNING: No real API keys detected (all dummy values)")
        print("   This will cause workflow executions to fail")
    else:
        print("✅ At least one real API key is configured")
    
    print("\n🏁 Diagnostic complete!")

if __name__ == "__main__":
    main()
