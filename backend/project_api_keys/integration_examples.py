# backend/project_api_keys/integration_examples.py

"""
Example integrations showing how to update existing services to use project-specific API keys.
These examples show the pattern for upgrading services to use project-specific keys.
"""

import logging
from typing import Optional, Dict, Any
from users.models import IntelliDocProject
from .integrations import get_project_api_key_integration

logger = logging.getLogger(__name__)

# Example 1: Updated OpenAI Summarizer using project-specific keys
class ProjectAwareOpenAISummarizer:
    """Enhanced OpenAI Summarizer that uses project-specific API keys"""
    
    def __init__(self, project: IntelliDocProject):
        self.project = project
        self.integration = get_project_api_key_integration()
        self.model = 'gpt-3.5-turbo'
        self.max_tokens = 150
        self.temperature = 0.3
        self.max_input_length = 3000
        
        # Get project-specific OpenAI client
        self.client = self.integration.get_openai_client_for_project(project)
        
        if self.client:
            logger.info(f"✅ PROJECT OPENAI SUMMARIZER: Initialized for project {project.name}")
        else:
            logger.warning(f"⚠️ PROJECT OPENAI SUMMARIZER: No API key configured for project {project.name}")
    
    def generate_summary(self, content: str, document_metadata: Dict[str, Any] = None) -> Optional[str]:
        """Generate summary using project-specific OpenAI API key"""
        if not self.client or not content.strip():
            if not self.client:
                return f"❌ OpenAI API key not configured for project '{self.project.name}'. Please add your OpenAI API key in the project's API Management settings."
            return None
        
        try:
            # Truncate content if too long
            if len(content) > self.max_input_length:
                content = content[:self.max_input_length] + "..."
            
            # Build prompt
            prompt = self._build_summarization_prompt(content, document_metadata)
            
            # Use project-specific client
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a professional document summarizer."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=self.max_tokens,
                temperature=self.temperature
            )
            
            summary = response.choices[0].message.content.strip()
            logger.info(f"✅ Generated summary for project {self.project.name}")
            return summary
            
        except Exception as e:
            logger.error(f"❌ Failed to generate summary for project {self.project.name}: {e}")
            return f"❌ Error generating summary: {str(e)}"
    
    def generate_topic(self, content: str, document_metadata: Dict[str, Any] = None) -> Optional[str]:
        """Generate topic using project-specific OpenAI API key"""
        if not self.client or not content.strip():
            if not self.client:
                return f"❌ OpenAI API key not configured for project '{self.project.name}'"
            return None
        
        try:
            if len(content) > self.max_input_length:
                content = content[:self.max_input_length] + "..."
            
            prompt = self._build_topic_prompt(content, document_metadata)
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert at creating concise topic names."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=30,
                temperature=0.2
            )
            
            topic = response.choices[0].message.content.strip()
            logger.info(f"✅ Generated topic for project {self.project.name}")
            return self._clean_topic(topic)
            
        except Exception as e:
            logger.error(f"❌ Failed to generate topic for project {self.project.name}: {e}")
            return None
    
    def _build_summarization_prompt(self, content: str, metadata: Dict[str, Any] = None) -> str:
        """Build summarization prompt"""
        prompt = ("Create a concise summary (max 200 words, 5 lines). "
                 "Focus on key points and main ideas.\\n\\n")
        
        if metadata:
            file_name = metadata.get('file_name', 'unknown')
            prompt += f"Document: {file_name}\\n\\n"
        
        prompt += f"Content: {content}\\n\\nSummary:"
        return prompt
    
    def _build_topic_prompt(self, content: str, metadata: Dict[str, Any] = None) -> str:
        """Build topic generation prompt"""
        prompt = ("Create a concise topic name (max 8 words, title case). "
                 "Focus on main subject. No quotes or special formatting.\\n\\n")
        
        if metadata:
            file_name = metadata.get('file_name', 'unknown')
            prompt += f"Document: {file_name}\\n\\n"
        
        prompt += f"Content: {content}\\n\\nTopic:"
        return prompt
    
    def _clean_topic(self, topic: str) -> str:
        """Clean and validate topic"""
        if not topic:
            return "Document Content"
        
        # Remove quotes and prefixes
        topic = topic.strip('"\\'')
        prefixes = ['Topic:', 'Title:', 'Subject:']
        for prefix in prefixes:
            if topic.startswith(prefix):
                topic = topic[len(prefix):].strip()
        
        # Limit to 8 words
        words = topic.split()[:8]
        return ' '.join(words).title()
    
    def is_available(self) -> bool:
        """Check if summarizer is available"""
        return self.client is not None


# Example 2: Updated LLM Provider using project-specific keys
class ProjectAwareLLMProvider:
    """Enhanced LLM Provider that uses project-specific API keys"""
    
    def __init__(self, project: IntelliDocProject, provider_type: str):
        self.project = project
        self.provider_type = provider_type
        self.integration = get_project_api_key_integration()
        
        # Check if provider is available for this project
        self.available = self.integration.validate_project_has_provider(
            project, provider_type
        )
        
        if self.available:
            logger.info(f"✅ PROJECT LLM PROVIDER: {provider_type} ready for project {project.name}")
        else:
            logger.warning(f"⚠️ PROJECT LLM PROVIDER: {provider_type} not configured for project {project.name}")
    
    def generate_response(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """Generate response using project-specific API"""
        if not self.available:
            error_msg = self.integration.get_fallback_message(self.project, self.provider_type)
            return {
                'success': False,
                'error': error_msg,
                'response': None
            }
        
        try:
            if self.provider_type == 'openai':
                return self._generate_openai_response(prompt, **kwargs)
            elif self.provider_type == 'google':
                return self._generate_google_response(prompt, **kwargs)
            elif self.provider_type == 'anthropic':
                return self._generate_anthropic_response(prompt, **kwargs)
            else:
                return {
                    'success': False,
                    'error': f'Unsupported provider: {self.provider_type}',
                    'response': None
                }
                
        except Exception as e:
            logger.error(f"❌ Error generating response with {self.provider_type}: {e}")
            return {
                'success': False,
                'error': str(e),
                'response': None
            }
    
    def _generate_openai_response(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """Generate OpenAI response using project-specific key"""
        client = self.integration.get_openai_client_for_project(self.project)
        if not client:
            error_msg = self.integration.get_fallback_message(self.project, 'openai')
            return {'success': False, 'error': error_msg, 'response': None}
        
        response = client.chat.completions.create(
            model=kwargs.get('model', 'gpt-3.5-turbo'),
            messages=[{'role': 'user', 'content': prompt}],
            max_tokens=kwargs.get('max_tokens', 150),
            temperature=kwargs.get('temperature', 0.7)
        )
        
        return {
            'success': True,
            'error': None,
            'response': response.choices[0].message.content
        }
    
    def _generate_google_response(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """Generate Google/Gemini response using project-specific key"""
        config = self.integration.get_google_client_config_for_project(self.project)
        if not config:
            error_msg = self.integration.get_fallback_message(self.project, 'google')
            return {'success': False, 'error': error_msg, 'response': None}
        
        # Implementation would use Google's API with the config
        # This is a placeholder showing the pattern
        return {
            'success': True,
            'error': None,
            'response': f"Google/Gemini response using project API key (placeholder)"
        }
    
    def _generate_anthropic_response(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """Generate Anthropic/Claude response using project-specific key"""
        config = self.integration.get_anthropic_client_config_for_project(self.project)
        if not config:
            error_msg = self.integration.get_fallback_message(self.project, 'anthropic')
            return {'success': False, 'error': error_msg, 'response': None}
        
        # Implementation would use Anthropic's API with the config
        # This is a placeholder showing the pattern
        return {
            'success': True,
            'error': None,
            'response': f"Anthropic/Claude response using project API key (placeholder)"
        }


# Example 3: Factory function for getting project-aware services
def get_project_summarizer(project: IntelliDocProject):
    """Factory function to get the best available summarizer for a project"""
    try:
        # Try to get project-aware OpenAI summarizer
        openai_summarizer = ProjectAwareOpenAISummarizer(project)
        
        if openai_summarizer.is_available():
            logger.info(f"✅ Using project-aware OpenAI summarizer for project {project.name}")
            return openai_summarizer
        else:
            logger.warning(f"⚠️ OpenAI not configured for project {project.name}, using fallback")
            # Fall back to simple summarizer
            from vector_search.summarization.openai_summarizer import SimpleSummarizer
            return SimpleSummarizer()
            
    except Exception as e:
        logger.error(f"❌ Error initializing summarizer for project {project.name}: {e}")
        from vector_search.summarization.openai_summarizer import SimpleSummarizer
        return SimpleSummarizer()


def get_project_llm_provider(project: IntelliDocProject, provider_type: str):
    """Factory function to get project-aware LLM provider"""
    return ProjectAwareLLMProvider(project, provider_type)


# Example 4: Service upgrade utility
def upgrade_service_to_project_aware(service_class, project: IntelliDocProject):
    """
    Utility function to upgrade existing services to use project-specific API keys.
    This is a template/example for upgrading any service.
    """
    integration = get_project_api_key_integration()
    
    # Check what providers are available for the project
    available_providers = integration.get_available_providers_for_project(project)
    
    logger.info(f"📊 Provider availability for project {project.name}: {available_providers}")
    
    # Return configuration for the service
    config = {
        'project': project,
        'available_providers': available_providers,
        'integration': integration,
        'fallback_messages': {
            provider: integration.get_fallback_message(project, provider)
            for provider in ['openai', 'google', 'anthropic']
            if not available_providers.get(provider, False)
        }
    }
    
    return config
