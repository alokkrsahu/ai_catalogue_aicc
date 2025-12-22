"""
Workflow Deployment Models
Models for deploying agent workflows as public-facing chatbots
"""
import uuid
from django.db import models
from django.utils import timezone
from users.models import IntelliDocProject, AgentWorkflow, User


class WorkflowDeploymentStatus(models.TextChoices):
    """Status choices for workflow deployments"""
    ACTIVE = 'active', 'Active'
    INACTIVE = 'inactive', 'Inactive'


class WorkflowDeployment(models.Model):
    """Deployment configuration for a workflow as a public chatbot"""
    # Core identification
    project = models.ForeignKey(
        IntelliDocProject,
        on_delete=models.CASCADE,
        related_name='workflow_deployments'
    )
    workflow = models.ForeignKey(
        AgentWorkflow,
        on_delete=models.CASCADE,
        related_name='deployments',
        help_text='The workflow being deployed',
        null=True,
        blank=True
    )
    
    # Deployment configuration
    is_active = models.BooleanField(
        default=False,
        help_text='Whether the deployment is currently active'
    )
    endpoint_path = models.CharField(
        max_length=200,
        editable=False,
        help_text='Auto-generated endpoint path'
    )
    rate_limit_per_minute = models.IntegerField(
        default=10,
        help_text='Default rate limit per minute for origins without specific limits'
    )
    initial_greeting = models.CharField(
        max_length=500,
        default='Hi! I am your AI assistant.',
        help_text='Initial greeting message shown by the embedded chatbot'
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='created_deployments'
    )
    
    class Meta:
        ordering = ['-updated_at']
        # Ensure only one active deployment per project
        constraints = [
            models.UniqueConstraint(
                fields=['project'],
                condition=models.Q(is_active=True),
                name='unique_active_deployment_per_project'
            )
        ]
        indexes = [
            models.Index(fields=['project', 'is_active']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        status = "Active" if self.is_active else "Inactive"
        workflow_name = self.workflow.name if self.workflow else "No workflow"
        return f"{self.project.name} - {workflow_name} ({status})"
    
    def save(self, *args, **kwargs):
        """Auto-generate endpoint path on save"""
        if not self.endpoint_path:
            self.endpoint_path = f"/api/workflow-deploy/{self.project.project_id}/"
        super().save(*args, **kwargs)
    
    @property
    def endpoint_url(self):
        """Get full endpoint URL"""
        # This will be constructed based on the actual domain in views
        return self.endpoint_path


class WorkflowAllowedOrigin(models.Model):
    """Allowed origins (domains) for a workflow deployment"""
    deployment = models.ForeignKey(
        WorkflowDeployment,
        on_delete=models.CASCADE,
        related_name='allowed_origins'
    )
    origin = models.CharField(
        max_length=500,
        help_text='Allowed origin (e.g., https://example.com)'
    )
    rate_limit_per_minute = models.IntegerField(
        default=10,
        help_text='Rate limit per minute for this specific origin'
    )
    is_active = models.BooleanField(
        default=True,
        help_text='Whether this origin is currently allowed'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['origin']
        unique_together = ['deployment', 'origin']
        indexes = [
            models.Index(fields=['deployment', 'is_active']),
            models.Index(fields=['origin']),
        ]
    
    def __str__(self):
        status = "Active" if self.is_active else "Inactive"
        return f"{self.deployment.project.name} - {self.origin} ({status})"


class WorkflowDeploymentRequestStatus(models.TextChoices):
    """Status choices for deployment requests"""
    SUCCESS = 'success', 'Success'
    ERROR = 'error', 'Error'
    RATE_LIMITED = 'rate_limited', 'Rate Limited'
    BLOCKED = 'blocked', 'Blocked'
    CORS_DENIED = 'cors_denied', 'CORS Denied'


class WorkflowDeploymentRequest(models.Model):
    """Track all requests to deployed workflows"""
    deployment = models.ForeignKey(
        WorkflowDeployment,
        on_delete=models.CASCADE,
        related_name='requests'
    )
    origin = models.CharField(
        max_length=500,
        help_text='Origin of the request'
    )
    request_id = models.CharField(
        max_length=100,
        unique=True,
        help_text='Unique request identifier'
    )
    session_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text='Optional session ID for conversation tracking'
    )
    message_preview = models.CharField(
        max_length=100,
        blank=True,
        help_text='Privacy-safe truncated message (first 100 chars)'
    )
    response_generated = models.BooleanField(
        default=False,
        help_text='Whether a response was successfully generated'
    )
    status = models.CharField(
        max_length=20,
        choices=WorkflowDeploymentRequestStatus.choices,
        default=WorkflowDeploymentRequestStatus.SUCCESS
    )
    execution_time_ms = models.IntegerField(
        null=True,
        blank=True,
        help_text='Workflow execution time in milliseconds'
    )
    error_message = models.TextField(
        blank=True,
        help_text='Error message if request failed'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['deployment', 'created_at']),
            models.Index(fields=['origin', 'created_at']),
            models.Index(fields=['status']),
            models.Index(fields=['session_id', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.deployment.project.name} - {self.request_id[:8]} ({self.status})"

