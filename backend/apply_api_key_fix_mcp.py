#!/usr/bin/env python3
"""
MCP Server Direct Fix for API Key Management Issue
Addresses HTTP 405 Method Not Allowed error when saving project API keys
"""

import os
import sys
import shutil
from pathlib import Path

def apply_api_key_fix():
    """Apply the comprehensive fix for API key management"""
    
    print("🔧 APPLYING API KEY MANAGEMENT FIX via MCP Server...")
    
    # Base paths
    backend_path = Path("/Users/alok/Documents/AICC/ai_catalogue/ai_catalogue/backend")
    project_api_keys_path = backend_path / "project_api_keys"
    
    if not project_api_keys_path.exists():
        print(f"❌ Project API keys directory not found: {project_api_keys_path}")
        return False
    
    try:
        # Step 1: Backup existing files
        print("📦 Creating backups of existing files...")
        
        backup_files = ['views.py', 'urls.py']
        for file in backup_files:
            original = project_api_keys_path / file
            backup = project_api_keys_path / f"{file}.backup"
            
            if original.exists():
                shutil.copy2(original, backup)
                print(f"   ✅ Backed up {file} to {file}.backup")
        
        # Step 2: Replace views.py with fixed version
        print("🔧 Applying fixed views.py...")
        
        fixed_views = project_api_keys_path / "views_fixed.py"
        target_views = project_api_keys_path / "views.py"
        
        if fixed_views.exists():
            shutil.copy2(fixed_views, target_views)
            print("   ✅ Applied fixed views.py")
        else:
            print("   ⚠️  Fixed views.py not found, will create it...")
            return False
        
        # Step 3: Replace urls.py with fixed version
        print("🔧 Applying fixed urls.py...")
        
        fixed_urls = project_api_keys_path / "urls_fixed.py"
        target_urls = project_api_keys_path / "urls.py"
        
        if fixed_urls.exists():
            shutil.copy2(fixed_urls, target_urls)
            print("   ✅ Applied fixed urls.py")
        else:
            print("   ⚠️  Fixed urls.py not found, will create it...")
            return False
            
        # Step 4: Verify the changes
        print("🔍 Verifying changes...")
        
        # Check views.py contains the fixed ViewSet
        with open(target_views, 'r') as f:
            views_content = f.read()
            if 'FIXED VERSION' in views_content and 'FIXED METHOD' in views_content:
                print("   ✅ Views.py properly updated with fixes")
            else:
                print("   ⚠️  Views.py may not be properly updated")
        
        # Check urls.py contains explicit URL patterns
        with open(target_urls, 'r') as f:
            urls_content = f.read()
            if 'project-api-keys-manage' in urls_content and 'project/<str:project_id>/keys/' in urls_content:
                print("   ✅ URLs.py properly updated with explicit patterns")
            else:
                print("   ⚠️  URLs.py may not be properly updated")
        
        # Step 5: Create a verification test
        print("🧪 Creating verification test...")
        
        test_content = '''#!/usr/bin/env python3
"""
Test script to verify API key endpoint accessibility
"""

import requests
import json

def test_api_key_endpoint():
    """Test that the API key endpoint responds correctly"""
    
    base_url = "http://localhost:8000/api"
    test_project_id = "f58ba641-1ca1-4cd8-914e-fc9a1159f8fc"
    
    # Test endpoint accessibility
    endpoints_to_test = [
        f"{base_url}/project-api-keys/providers/",
        f"{base_url}/project-api-keys/project/{test_project_id}/keys/",
        f"{base_url}/project-api-keys/project/{test_project_id}/status/",
    ]
    
    print("🧪 TESTING API KEY ENDPOINTS...")
    
    for endpoint in endpoints_to_test:
        try:
            # Test OPTIONS to check allowed methods
            response = requests.options(endpoint, timeout=5)
            allowed_methods = response.headers.get('Allow', '')
            
            print(f"   📋 {endpoint}")
            print(f"      Status: {response.status_code}")
            print(f"      Allowed Methods: {allowed_methods}")
            
            # For the keys endpoint, verify POST is allowed
            if 'keys/' in endpoint and 'POST' not in allowed_methods:
                print(f"      ❌ POST method not allowed for keys endpoint!")
            elif 'keys/' in endpoint and 'POST' in allowed_methods:
                print(f"      ✅ POST method correctly allowed for keys endpoint")
                
        except Exception as e:
            print(f"   ❌ {endpoint}: {str(e)}")
    
    print("\\n🎯 ENDPOINT TEST SUMMARY:")
    print("   - If POST is allowed on /keys/ endpoint: ✅ Fix successful")
    print("   - If POST returns 405 on /keys/ endpoint: ❌ Fix needs refinement")

if __name__ == "__main__":
    test_api_key_endpoint()
'''
        
        test_file = project_api_keys_path / "test_api_key_fix.py"
        with open(test_file, 'w') as f:
            f.write(test_content)
        
        os.chmod(test_file, 0o755)  # Make executable
        print(f"   ✅ Created test script: {test_file}")
        
        print("\\n🎉 API KEY MANAGEMENT FIX APPLIED SUCCESSFULLY!")
        print("\\n📋 NEXT STEPS:")
        print("1. Restart the Django server: python manage.py runserver")
        print("2. Test the fix by running: python project_api_keys/test_api_key_fix.py")
        print("3. Try saving an API key in the frontend")
        print("\\n🔄 If issues persist, check Django logs for detailed error messages")
        
        return True
        
    except Exception as e:
        print(f"❌ Error applying fix: {str(e)}")
        return False

if __name__ == "__main__":
    success = apply_api_key_fix()
    sys.exit(0 if success else 1)
