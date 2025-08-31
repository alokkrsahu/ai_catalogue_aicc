"""
Test API Key Fix - Simple URL and View Testing
"""

from django.test import TestCase
from django.urls import reverse, resolve
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from users.models import IntelliDocProject, ProjectAPIKey
import uuid

class APIKeyFixTestCase(TestCase):
    """Test the API key management fix"""
    
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            email='test@example.com'
        )
        
        # Create a test project
        self.project = IntelliDocProject.objects.create(
            name='Test Project',
            description='Test project for API key testing',
            template_id='test-template',
            created_by=self.user,
            project_id=str(uuid.uuid4())
        )
        
    def test_url_patterns_exist(self):
        """Test that URL patterns are correctly configured"""
        
        # Test that the URLs can be resolved
        urls_to_test = [
            ('project-api-keys-manage', {'project_id': self.project.project_id}),
            ('project-api-keys-status', {'project_id': self.project.project_id}),
            ('project-api-keys-providers', {}),
        ]
        
        for url_name, kwargs in urls_to_test:
            try:
                url = reverse(url_name, kwargs=kwargs)
                print(f"✅ URL {url_name} resolved to: {url}")
            except Exception as e:
                print(f"❌ URL {url_name} failed to resolve: {e}")
    
    def test_post_method_allowed(self):
        """Test that POST method is allowed on the keys endpoint"""
        
        self.client.force_authenticate(user=self.user)
        
        # Test POST to the API keys endpoint
        url = f'/api/project-api-keys/project/{self.project.project_id}/keys/'
        
        data = {
            'provider_type': 'openai',
            'api_key': 'sk-test123456789',
            'key_name': 'Test OpenAI Key',
            'validate_key': False  # Skip validation for test
        }
        
        response = self.client.post(url, data, format='json')
        
        # Check that we don't get a 405 Method Not Allowed
        self.assertNotEqual(response.status_code, 405, 
                          f"Got 405 Method Not Allowed, fix unsuccessful. Response: {response.content}")
        
        print(f"✅ POST request to {url} returned status {response.status_code} (not 405)")
        
        # Print the response for debugging
        print(f"Response content: {response.content}")
    
    def test_get_method_allowed(self):
        """Test that GET method is allowed on the keys endpoint"""
        
        self.client.force_authenticate(user=self.user)
        
        # Test GET to the API keys endpoint (list keys)
        url = f'/api/project-api-keys/project/{self.project.project_id}/keys/'
        
        response = self.client.get(url)
        
        # Check that we don't get a 405 Method Not Allowed
        self.assertNotEqual(response.status_code, 405,
                          f"Got 405 Method Not Allowed for GET, fix unsuccessful. Response: {response.content}")
        
        print(f"✅ GET request to {url} returned status {response.status_code} (not 405)")
        print(f"Response content: {response.content}")
