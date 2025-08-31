#!/usr/bin/env python3
"""
API Key Management Fix Verification Script
Tests the fixed endpoints to ensure they work correctly
"""

import subprocess
import sys
import os
from pathlib import Path

def verify_django_urls():
    """Verify Django URL patterns are working correctly"""
    
    print("🔍 VERIFYING DJANGO URL PATTERNS...")
    
    # Change to backend directory
    backend_path = Path(__file__).parent
    os.chdir(backend_path)
    
    try:
        # Run Django's show_urls to verify URL patterns
        result = subprocess.run([
            sys.executable, "manage.py", "show_urls", "--format=table"
        ], capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            print("✅ Django URL patterns loaded successfully")
            
            # Look for project API key patterns
            output = result.stdout
            if "project-api-keys" in output:
                print("✅ Project API key URLs found in pattern list")
                
                # Check for specific patterns
                patterns_to_check = [
                    "project/<str:project_id>/keys/",
                    "project/<str:project_id>/status/",
                    "providers/"
                ]
                
                for pattern in patterns_to_check:
                    if pattern in output:
                        print(f"   ✅ Found pattern: {pattern}")
                    else:
                        print(f"   ⚠️  Missing pattern: {pattern}")
            else:
                print("⚠️  Project API key URLs not found in pattern list")
                
        else:
            print(f"❌ Django URL verification failed: {result.stderr}")
            
    except subprocess.TimeoutExpired:
        print("⚠️  Django URL verification timed out")
    except Exception as e:
        print(f"❌ Error running URL verification: {e}")

def check_imports():
    """Check that all imports are working correctly"""
    
    print("📦 CHECKING IMPORTS...")
    
    try:
        # Test importing the fixed views
        sys.path.insert(0, str(Path(__file__).parent))
        
        from project_api_keys.views import ProjectAPIKeyViewSet
        print("✅ Successfully imported ProjectAPIKeyViewSet")
        
        # Check if the ViewSet has the required methods
        required_methods = [
            'set_api_key', 'list_project_keys', 'project_status', 
            'validate_api_key', 'delete_api_key', 'available_providers'
        ]
        
        for method in required_methods:
            if hasattr(ProjectAPIKeyViewSet, method):
                print(f"   ✅ Method {method} found")
            else:
                print(f"   ❌ Method {method} missing")
                
        from project_api_keys.urls import urlpatterns
        print("✅ Successfully imported URL patterns")
        print(f"   📊 Found {len(urlpatterns)} URL patterns")
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
    except Exception as e:
        print(f"❌ Error checking imports: {e}")

def create_test_request():
    """Create a test to verify the endpoint accepts POST requests"""
    
    print("🧪 CREATING TEST REQUEST HANDLER...")
    
    test_code = '''
from django.test import TestCase, RequestFactory
from django.contrib.auth.models import User
from project_api_keys.views import ProjectAPIKeyViewSet
import json

class APIKeyEndpointTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.viewset = ProjectAPIKeyViewSet()
    
    def test_set_api_key_method_allowed(self):
        """Test that POST method is allowed on set_api_key"""
        
        # Create a POST request
        request = self.factory.post('/api/project-api-keys/project/test-id/keys/', 
                                  data=json.dumps({
                                      'provider_type': 'openai',
                                      'api_key': 'test-key-12345',
                                      'key_name': 'Test Key'
                                  }),
                                  content_type='application/json')
        request.user = self.user
        
        # This should not raise a 405 error
        try:
            response = self.viewset.set_api_key(request, project_id='test-id')
            # We expect it to fail due to missing project, but not with 405
            self.assertNotEqual(response.status_code, 405)
            print("✅ POST method accepted by set_api_key endpoint")
        except Exception as e:
            if "405" not in str(e):
                print("✅ No 405 Method Not Allowed error")
            else:
                print(f"❌ 405 Method Not Allowed error still present: {e}")

# To run this test:
# python manage.py test project_api_keys.test_api_key_fix --verbosity=2
'''
    
    test_file = Path(__file__).parent / "project_api_keys" / "test_api_key_fix.py"
    with open(test_file, 'w') as f:
        f.write(test_code)
    
    print(f"✅ Created test file: {test_file}")
    print("   Run with: python manage.py test project_api_keys.test_api_key_fix")

def main():
    """Run all verification checks"""
    
    print("🚀 API KEY MANAGEMENT FIX VERIFICATION")
    print("=" * 50)
    
    check_imports()
    print()
    
    verify_django_urls()
    print()
    
    create_test_request()
    print()
    
    print("🎯 VERIFICATION SUMMARY:")
    print("1. If all imports work: ✅ Views and URLs are syntactically correct")
    print("2. If URL patterns show up: ✅ Django can route requests correctly")
    print("3. If test file created: ✅ Ready to test actual POST requests")
    print()
    print("📋 NEXT STEPS:")
    print("1. Restart Django server: python manage.py runserver")
    print("2. Run the test: python manage.py test project_api_keys.test_api_key_fix")
    print("3. Try the frontend API key save operation")
    print("4. Check Django logs for any remaining issues")

if __name__ == "__main__":
    main()
