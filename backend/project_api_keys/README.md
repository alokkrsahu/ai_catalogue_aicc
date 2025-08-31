# Project-Specific API Key Management System

## Overview

The Project-Specific API Key Management system allows each project to have its own API keys for different AI providers (OpenAI, Google, Anthropic). This provides better security, cost management, and project isolation.

## Features

- **Project Isolation**: Each project has its own API keys
- **Multi-Provider Support**: OpenAI, Google (Gemini), and Anthropic (Claude)
- **Encryption**: API keys are encrypted at rest using project-specific encryption
- **Validation**: API keys are validated with their providers during setup
- **Usage Tracking**: Track usage statistics for each API key
- **Fallback Messages**: User-friendly error messages when API keys are missing

## Architecture

### Models
- `ProjectAPIKey`: Stores encrypted API keys for projects
- `ProjectAPIKeyProvider`: Enum for supported providers

### Services
- `ProjectAPIKeyService`: Main service for API key operations
- `ProjectAPIKeyEncryption`: Handles encryption/decryption
- `APIKeyValidator`: Validates keys with providers
- `ProjectAPIKeyIntegration`: Helper for integrating with existing services

## API Endpoints

### Available Providers
```
GET /api/project-api-keys/providers/
```
Returns list of available API providers.

### Project API Key Status
```
GET /api/project-api-keys/project/{project_id}/status/
```
Get comprehensive status of all API keys for a project.

### Set/Update API Key
```
POST /api/project-api-keys/project/{project_id}/keys/
```
Set or update an API key for a project.

**Request Body:**
```json
{
  "provider_type": "openai",
  "api_key": "sk-...",
  "key_name": "Production Key",
  "validate_key": true
}
```

### Validate API Key
```
POST /api/project-api-keys/project/{project_id}/keys/{provider_type}/validate/
```
Validate an existing API key with its provider.

### Delete API Key
```
DELETE /api/project-api-keys/project/{project_id}/keys/{provider_type}/
```
Delete an API key for a project and provider.

### List Project Keys
```
GET /api/project-api-keys/project/{project_id}/keys/
```
List all API keys for a project (returns masked keys for security).

## Frontend Integration

### Project Creation UX
Show API key fields inline with other project fields:

```jsx
<ProjectForm>
  {/* Standard project fields */}
  <input name="name" placeholder="Project Name" />
  <textarea name="description" placeholder="Description" />
  
  {/* API Key Management Section */}
  <div className="api-keys-section">
    <h3>API Keys (Optional)</h3>
    <p>Add your API keys to enable AI-powered features for this project.</p>
    
    <APIKeyField 
      provider="openai" 
      label="OpenAI API Key" 
      placeholder="sk-..." 
      description="For GPT models and summarization"
    />
    
    <APIKeyField 
      provider="google" 
      label="Google API Key" 
      placeholder="AIza..." 
      description="For Gemini models and OCR"
    />
    
    <APIKeyField 
      provider="anthropic" 
      label="Anthropic API Key" 
      placeholder="sk-ant-..." 
      description="For Claude models and analysis"
    />
  </div>
</ProjectForm>
```

### API Management Modal
```jsx
<APIManagementModal project={project}>
  <APIProviderCard 
    provider="openai"
    hasKey={true}
    isValidated={true}
    usageCount={42}
    onUpdate={handleUpdateKey}
    onDelete={handleDeleteKey}
  />
  
  <APIProviderCard 
    provider="google"
    hasKey={false}
    onAdd={handleAddKey}
  />
</APIManagementModal>
```

## Backend Integration

### Updating Existing Services

#### Example: OpenAI Summarizer
```python
# OLD: Using global API key
class OpenAISummarizer:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# NEW: Using project-specific API key
class ProjectAwareOpenAISummarizer:
    def __init__(self, project: IntelliDocProject):
        self.project = project
        integration = get_project_api_key_integration()
        self.client = integration.get_openai_client_for_project(project)
    
    def generate_summary(self, content: str) -> str:
        if not self.client:
            return integration.get_fallback_message(self.project, 'openai')
        
        # Use self.client as normal...
```

#### Example: LLM Provider
```python
# OLD: Using environment variables
def call_openai_api(prompt: str):
    api_key = os.getenv('OPENAI_API_KEY')
    # ... make API call

# NEW: Using project context
def call_openai_api(prompt: str, project: IntelliDocProject):
    integration = get_project_api_key_integration()
    
    if not integration.validate_project_has_provider(project, 'openai'):
        return {'error': integration.get_fallback_message(project, 'openai')}
    
    client = integration.get_openai_client_for_project(project)
    # ... make API call with client
```

### Service Factory Pattern
```python
def get_project_summarizer(project: IntelliDocProject):
    """Factory function to get the best available summarizer for a project"""
    integration = get_project_api_key_integration()
    
    if integration.validate_project_has_provider(project, 'openai'):
        return ProjectAwareOpenAISummarizer(project)
    else:
        return SimpleSummarizer()  # Fallback

def get_project_llm_provider(project: IntelliDocProject, provider_type: str):
    """Factory function to get project-aware LLM provider"""
    return ProjectAwareLLMProvider(project, provider_type)
```

## Environment Variables

Add to your `.env` file:

```bash
# Project-specific API key encryption
PROJECT_API_KEY_ENCRYPTION_KEY=base64-encoded-32-byte-key

# Optional: Fallback to legacy setting if not set
API_KEY_ENCRYPTION_KEY=base64-encoded-32-byte-key
```

### Generating Encryption Key
```python
# Generate a new encryption key (run once)
from cryptography.fernet import Fernet
encryption_key = Fernet.generate_key()
print(f"PROJECT_API_KEY_ENCRYPTION_KEY={encryption_key.decode()}")
```

## Settings Configuration

Add to your Django settings:

```python
# settings.py

INSTALLED_APPS = [
    # ... other apps
    'project_api_keys.apps.ProjectApiKeysConfig',
]

# Project API Key Configuration
PROJECT_API_KEY_SETTINGS = {
    'ENCRYPTION_KEY': os.getenv('PROJECT_API_KEY_ENCRYPTION_KEY'),
    'VALIDATION_ENABLED': True,
    'VALIDATION_TIMEOUT': 10,  # seconds
    'USAGE_TRACKING': True,
}

# Logging for project API keys
LOGGING = {
    'loggers': {
        'project_api_keys': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}
```

## Migration Strategy

### Phase 1: No Migration Required
Since this is a new feature, no existing projects need migration. The system provides these fallback behaviors:

1. **No API Key Set**: Show user-friendly message to add API key
2. **Legacy Environment Variables**: Continue working as before
3. **Gradual Migration**: Users can add project-specific keys at their own pace

### Phase 2: Gradual Migration (Optional)
For users who want to migrate from environment variables:

1. **Detection**: Check if project uses legacy environment variables
2. **Migration Tool**: Provide admin command to migrate keys
3. **Notification**: Suggest migration in project overview

```python
# Management command: migrate_api_keys.py
from django.core.management.base import BaseCommand
from users.models import IntelliDocProject
from project_api_keys.services import get_project_api_key_service

class Command(BaseCommand):
    def handle(self, *args, **options):
        service = get_project_api_key_service()
        
        for project in IntelliDocProject.objects.all():
            # Check if project needs migration
            if not service.get_project_api_keys(project):
                self.stdout.write(f"Project {project.name} can be migrated")
```

## Error Handling

### Graceful Fallbacks
```python
def process_document_with_ai(project, document):
    """Example of graceful fallback handling"""
    integration = get_project_api_key_integration()
    
    # Try project-specific OpenAI first
    if integration.validate_project_has_provider(project, 'openai'):
        try:
            return process_with_openai(project, document)
        except Exception as e:
            logger.warning(f"OpenAI processing failed: {e}")
    
    # Try Google as fallback
    if integration.validate_project_has_provider(project, 'google'):
        try:
            return process_with_google(project, document)
        except Exception as e:
            logger.warning(f"Google processing failed: {e}")
    
    # Final fallback to simple processing
    return process_with_simple_methods(document)
```

### User-Friendly Error Messages
```python
# Good: Helpful error message
"❌ OpenAI API key not configured for project 'Research Project'. Please add your OpenAI API key in the project's API Management settings to use this feature."

# Bad: Technical error message
"Exception: NoneType object has no attribute 'chat'"
```

## Security Considerations

### Encryption at Rest
- API keys are encrypted using Fernet (AES 128)
- Each project uses project-specific encryption context
- Encryption keys are stored in environment variables, never in database

### Access Control
- Only project owners can manage API keys
- API keys are never returned in API responses (only masked versions)
- Django admin access restricted to superusers

### Audit Trail
- Track who added/modified API keys
- Log API key usage with timestamps
- Monitor validation attempts and failures

## Testing

### Unit Tests
```python
# test_project_api_keys.py
from django.test import TestCase
from users.models import IntelliDocProject, User
from project_api_keys.services import get_project_api_key_service

class ProjectAPIKeyTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('test@example.com', 'password')
        self.project = IntelliDocProject.objects.create(
            name='Test Project',
            created_by=self.user
        )
        self.service = get_project_api_key_service()
    
    def test_set_api_key(self):
        """Test setting a new API key"""
        api_key_obj, created = self.service.set_project_api_key(
            project=self.project,
            provider_type='openai',
            api_key='sk-test123',
            user=self.user,
            validate_key=False
        )
        
        self.assertTrue(created)
        self.assertEqual(api_key_obj.provider_type, 'openai')
        self.assertTrue(api_key_obj.is_active)
    
    def test_get_api_key(self):
        """Test retrieving an API key"""
        # Set key first
        self.service.set_project_api_key(
            project=self.project,
            provider_type='openai',
            api_key='sk-test123',
            user=self.user,
            validate_key=False
        )
        
        # Retrieve key
        retrieved_key = self.service.get_project_api_key(
            self.project, 'openai'
        )
        
        self.assertEqual(retrieved_key, 'sk-test123')
```

### Integration Tests
```python
class ProjectAPIKeyIntegrationTests(TestCase):
    def test_openai_client_creation(self):
        """Test OpenAI client creation with project key"""
        integration = get_project_api_key_integration()
        
        # Set up project with OpenAI key
        service = get_project_api_key_service()
        service.set_project_api_key(
            project=self.project,
            provider_type='openai',
            api_key='sk-test123',
            user=self.user,
            validate_key=False
        )
        
        # Test client creation
        client = integration.get_openai_client_for_project(self.project)
        self.assertIsNotNone(client)
```

## Monitoring and Analytics

### Usage Statistics
Track in Django admin:
- API key usage frequency
- Most used providers per project
- Validation success/failure rates
- Cost estimates (if available from providers)

### Health Checks
```python
def check_project_api_keys_health():
    """Health check for project API keys system"""
    from project_api_keys.encryption import get_encryption_service
    
    encryption_service = get_encryption_service()
    
    if not encryption_service.validate_encryption_setup():
        return {'status': 'error', 'message': 'Encryption not working'}
    
    return {'status': 'healthy'}
```

## Troubleshooting

### Common Issues

#### 1. Encryption Key Not Set
**Error**: `ImproperlyConfigured: PROJECT_API_KEY_ENCRYPTION_KEY environment variable must be configured`

**Solution**: 
```bash
# Generate and set encryption key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
export PROJECT_API_KEY_ENCRYPTION_KEY="your-generated-key"
```

#### 2. API Key Validation Fails
**Error**: `Validation timeout - please check your internet connection`

**Solution**:
- Check internet connectivity
- Verify API key format is correct
- Check provider API status
- Increase validation timeout in settings

#### 3. Permission Errors
**Error**: `User does not have permission to manage API keys for this project`

**Solution**: Ensure user is the project owner or has appropriate permissions

### Debug Commands
```python
# Check encryption status
python manage.py shell
>>> from project_api_keys.encryption import get_encryption_service
>>> service = get_encryption_service()
>>> service.validate_encryption_setup()

# List project API keys
python manage.py shell
>>> from users.models import IntelliDocProject
>>> from project_api_keys.services import get_project_api_key_service
>>> project = IntelliDocProject.objects.first()
>>> service = get_project_api_key_service()
>>> service.get_project_api_keys_status(project)
```

## Future Enhancements

### Planned Features
1. **Cost Tracking**: Integration with provider billing APIs
2. **Usage Quotas**: Set spending limits per project
3. **Key Rotation**: Automated API key rotation
4. **Team Sharing**: Share API keys across team members
5. **Provider Templates**: Pre-configured provider settings
6. **Audit Logs**: Detailed audit trail for all API key operations

### Extension Points
The system is designed to be easily extended:

1. **New Providers**: Add new AI providers by extending `ProjectAPIKeyProvider`
2. **Custom Validation**: Implement custom validation logic
3. **Enhanced Encryption**: Add additional encryption layers
4. **Integration Hooks**: Add webhooks for API key events

## Conclusion

The Project-Specific API Key Management system provides a secure, scalable way to manage AI provider credentials at the project level. It enables better cost control, security isolation, and user experience while maintaining backward compatibility with existing implementations.

The system is designed with security-first principles, comprehensive error handling, and easy integration patterns that make it simple to upgrade existing services to use project-specific API keys.
