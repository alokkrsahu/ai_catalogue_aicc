# Universal Project API System - Phase 3 CLEAN VERSION (AutoGen Removed)
# backend/api/universal_project_views.py

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db import transaction
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from users.models import IntelliDocProject, ProjectDocument, AgentWorkflow, SimulationRun, AgentMessage
from templates.discovery import TemplateDiscoverySystem
from .serializers import IntelliDocProjectSerializer, ProjectDocumentSerializer
from agent_orchestration.serializers import (
    AgentWorkflowSerializer, SimulationRunSerializer, AgentMessageSerializer,
    WorkflowValidationSerializer, WorkflowExecutionSerializer
)
import logging
import uuid
import os
import json
import zipfile
import tempfile
from typing import Dict, Any, List, Tuple

# Try to import our custom schema validator, but don't fail if jsonschema isn't installed
try:
    from schemas.workflow_validator import AgentWorkflowValidator
    SCHEMA_VALIDATOR_AVAILABLE = True
except ImportError as e:
    SCHEMA_VALIDATOR_AVAILABLE = False
    print(f"⚠️  Schema validator not available: {e}")

logger = logging.getLogger(__name__)

class UniversalProjectViewSet(viewsets.ModelViewSet):
    """
    Universal Project API - Phase 3 (CUSTOM Agent Implementation)
    
    Single API for ALL project operations regardless of template type.
    Uses CUSTOM agent orchestration system with JSON schema validation.
    AutoGen has been completely removed and replaced with our own implementation.
    """
    serializer_class = IntelliDocProjectSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'project_id'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if SCHEMA_VALIDATOR_AVAILABLE:
            self.workflow_validator = AgentWorkflowValidator()
        else:
            self.workflow_validator = None
    
    def get_queryset(self):
        """Get projects accessible to current user based on permissions"""
        user = self.request.user
        
        # Admin users can see all projects
        if user.is_admin:
            return IntelliDocProject.objects.all()
        
        # Regular users see projects they created + projects they have permission to access
        from django.db.models import Q
        
        # Get projects where user is creator
        created_projects = Q(created_by=user)
        
        # Get projects with direct user permissions
        user_permissions = Q(user_permissions__user=user)
        
        # Get projects with group permissions
        user_groups = user.groups.all()
        group_permissions = Q(group_permissions__group__in=user_groups)
        
        # Combine all conditions with OR
        return IntelliDocProject.objects.filter(
            created_projects | user_permissions | group_permissions
        ).distinct()
    
    def list(self, request, *args, **kwargs):
        """
        List all projects for current user
        GET /api/projects/
        """
        logger.info(f"📋 UNIVERSAL: Listing projects for user {request.user.email}")
        
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        
        # Enhanced response with metadata
        response_data = {
            'projects': serializer.data,
            'total_count': queryset.count(),
            'user_email': request.user.email,
            'templates_used': list(queryset.values_list('template_name', flat=True).distinct()),
            'project_types': list(queryset.values_list('template_type', flat=True).distinct()),
            'api_version': 'universal_v1',
            'agent_system': 'custom_aicc_schema' if SCHEMA_VALIDATOR_AVAILABLE else 'basic',
            'schema_validator_available': SCHEMA_VALIDATOR_AVAILABLE,
            'timestamp': timezone.now().isoformat()
        }
        
        logger.info(f"📊 UNIVERSAL: Returning {len(serializer.data)} projects")
        return Response(response_data)
    
    def retrieve(self, request, *args, **kwargs):
        """
        Get single project details
        GET /api/projects/{project_id}/
        """
        project = self.get_object()
        logger.info(f"📄 UNIVERSAL: Retrieving project {project.name} ({project.project_id})")
        
        serializer = self.get_serializer(project)
        
        # Enhanced response with additional metadata
        response_data = {
            **serializer.data,
            'documents_count': project.documents.count(),
            'ready_documents_count': project.documents.filter(upload_status='ready').count(),
            'processing_documents_count': project.documents.filter(upload_status='processing').count(),
            'api_version': 'universal_v1',
            'agent_system': 'custom_aicc_schema' if SCHEMA_VALIDATOR_AVAILABLE else 'basic',
            'schema_validator_available': SCHEMA_VALIDATOR_AVAILABLE,
            'retrieved_at': timezone.now().isoformat(),
            'template_independence': True,
            'universal_interface': True
        }
        
        return Response(response_data)
    
    def create(self, request, *args, **kwargs):
        """
        Create new project from template
        POST /api/projects/
        """
        logger.info(f"🏗️ UNIVERSAL: Creating project for user {request.user.email}")
        
        # Only admin users can create projects
        if not request.user.is_admin:
            logger.warning(f"🚫 UNIVERSAL: Non-admin user {request.user.email} attempted to create project")
            return Response({
                'error': 'Permission denied. Only admin users can create projects.',
                'detail': 'Project creation is restricted to administrators only.'
            }, status=status.HTTP_403_FORBIDDEN)
        
        template_id = request.data.get('template_id')
        if not template_id:
            return Response({
                'error': 'template_id is required',
                'message': 'Please specify which template to use for project creation'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            template_data = TemplateDiscoverySystem.get_template_configuration(template_id)
            if not template_data:
                return Response({
                    'error': 'Template not found',
                    'message': f'Template with ID {template_id} does not exist'
                }, status=status.HTTP_404_NOT_FOUND)
            
            template_config = template_data.get('configuration', {})
            template_metadata = template_data.get('metadata', {})
            
            template_name = template_config.get('name') or template_metadata.get('name') or template_id.title()
            template_type = template_config.get('template_type') or template_metadata.get('template_type') or template_id
            
            project_data = {
                **request.data,
                'project_id': str(uuid.uuid4()),
                'template_name': template_name,
                'template_type': template_type,
                'instructions': template_config.get('instructions', ''),
                'suggested_questions': template_config.get('suggested_questions', []),
                'analysis_focus': template_config.get('analysis_focus', 'Document analysis'),
                'icon_class': template_config.get('icon_class') or template_metadata.get('ui_assets', {}).get('icon', 'fa-file-alt'),
                'color_theme': template_config.get('color_theme', 'oxford-blue'),
                'has_navigation': template_config.get('has_navigation', False),
                'total_pages': template_config.get('total_pages', 1),
                'navigation_pages': template_config.get('navigation_pages', []),
                'processing_capabilities': template_config.get('processing_capabilities', {}),
                'validation_rules': template_config.get('validation_rules', {}),
                'ui_configuration': template_config.get('ui_configuration', {})
            }
            
            serializer = self.get_serializer(data=project_data)
            serializer.is_valid(raise_exception=True)
            project = serializer.save(created_by=request.user)
            
            response_data = {
                **serializer.data,
                'template_info': {
                    'template_id': template_id,
                    'template_name': template_name,
                    'template_type': template_type,
                    'template_version': template_metadata.get('version', '1.0.0'),
                    'cloned_at': timezone.now().isoformat()
                },
                'project_capabilities': {
                    'processing_mode': 'enhanced_hierarchical' if template_type == 'aicc-intellidoc' else 'enhanced',
                    'supports_navigation': project.has_navigation,
                    'supports_multi_page': project.total_pages > 1,
                    'processing_capabilities': project.processing_capabilities,
                    'agent_orchestration': 'custom_aicc_schema' if SCHEMA_VALIDATOR_AVAILABLE else 'basic'
                },
                'api_version': 'universal_v1',
                'agent_system': 'custom_aicc_schema' if SCHEMA_VALIDATOR_AVAILABLE else 'basic',
                'schema_validator_available': SCHEMA_VALIDATOR_AVAILABLE,
                'created_at': timezone.now().isoformat(),
                'template_independence': True,
                'universal_interface': True
            }
            
            logger.info(f"✅ UNIVERSAL: Created project {project.name} ({project.project_id})")
            return Response(response_data, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"❌ UNIVERSAL: Project creation failed: {e}")
            return Response({
                'error': str(e),
                'message': 'Failed to create project'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def documents(self, request, project_id=None):
        """Get project documents"""
        project = self.get_object()
        documents = project.documents.all().order_by('-uploaded_at')
        serializer = ProjectDocumentSerializer(documents, many=True)
        
        return Response({
            'documents': serializer.data,
            'total_count': documents.count(),
            'project_id': project.project_id,
            'api_version': 'universal_v1'
        })
    
    @action(detail=True, methods=['post'])
    def upload_document(self, request, project_id=None):
        """Upload document to project"""
        project = self.get_object()
        
        if 'file' not in request.FILES:
            return Response({'error': 'No file provided'}, status=status.HTTP_400_BAD_REQUEST)
        
        uploaded_file = request.FILES['file']
        
        try:
            with transaction.atomic():
                document = ProjectDocument.objects.create(
                    project=project,
                    original_filename=uploaded_file.name,
                    file_size=uploaded_file.size,
                    file_type=uploaded_file.content_type,
                    file_extension=os.path.splitext(uploaded_file.name)[1].lower(),
                    upload_status='processing',
                    uploaded_by=request.user
                )
                
                file_path = document.get_storage_path()
                saved_path = default_storage.save(file_path, ContentFile(uploaded_file.read()))
                document.file_path = saved_path
                document.upload_status = 'ready'
                document.save()
                
                serializer = ProjectDocumentSerializer(document)
                return Response({
                    **serializer.data,
                    'message': 'Document uploaded successfully',
                    'api_version': 'universal_v1'
                }, status=status.HTTP_201_CREATED)
                
        except Exception as e:
            return Response({'error': 'Upload failed', 'detail': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def upload_bulk_files(self, request, project_id=None):
        """Upload multiple files in a single request"""
        project = self.get_object()
        
        if not request.FILES:
            return Response({'error': 'No files provided'}, status=status.HTTP_400_BAD_REQUEST)
        
        uploaded_documents = []
        failed_uploads = []
        
        try:
            with transaction.atomic():
                for file_key, uploaded_file in request.FILES.items():
                    try:
                        document = ProjectDocument.objects.create(
                            project=project,
                            original_filename=uploaded_file.name,
                            file_size=uploaded_file.size,
                            file_type=uploaded_file.content_type,
                            file_extension=os.path.splitext(uploaded_file.name)[1].lower(),
                            upload_status='processing',
                            uploaded_by=request.user
                        )
                        
                        file_path = document.get_storage_path()
                        saved_path = default_storage.save(file_path, ContentFile(uploaded_file.read()))
                        document.file_path = saved_path
                        document.upload_status = 'ready'
                        document.save()
                        
                        uploaded_documents.append(ProjectDocumentSerializer(document).data)
                        
                    except Exception as e:
                        failed_uploads.append({
                            'filename': uploaded_file.name,
                            'error': str(e)
                        })
                        logger.error(f"Failed to upload {uploaded_file.name}: {e}")
                
                return Response({
                    'uploaded_documents': uploaded_documents,
                    'failed_uploads': failed_uploads,
                    'total_attempted': len(request.FILES),
                    'total_successful': len(uploaded_documents),
                    'total_failed': len(failed_uploads),
                    'message': f'Bulk upload completed: {len(uploaded_documents)} successful, {len(failed_uploads)} failed',
                    'api_version': 'universal_v1'
                }, status=status.HTTP_201_CREATED if uploaded_documents else status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            return Response({'error': 'Bulk upload failed', 'detail': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def upload_zip_file(self, request, project_id=None):
        """Upload and extract a zip file containing documents"""
        project = self.get_object()
        
        if 'file' not in request.FILES:
            return Response({'error': 'No zip file provided'}, status=status.HTTP_400_BAD_REQUEST)
        
        uploaded_file = request.FILES['file']
        
        # Validate it's a zip file
        if not uploaded_file.name.lower().endswith('.zip'):
            return Response({'error': 'File must be a zip archive'}, status=status.HTTP_400_BAD_REQUEST)
        
        uploaded_documents = []
        failed_extractions = []
        extracted_files_info = []
        
        try:
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                # Save uploaded zip to temporary file
                for chunk in uploaded_file.chunks():
                    temp_file.write(chunk)
                temp_file_path = temp_file.name
            
            try:
                with zipfile.ZipFile(temp_file_path, 'r') as zip_ref:
                    # Get list of all files in zip
                    file_list = zip_ref.namelist()
                    
                    # Filter out directories and system files more comprehensively
                    valid_files = []
                    for f in file_list:
                        # Skip directories
                        if f.endswith('/'):
                            continue
                        # Skip system files and directories
                        if (f.startswith('__MACOSX/') or 
                            f.startswith('.DS_Store') or
                            '/.DS_Store' in f or
                            f.endswith('.tmp') or
                            '/.git/' in f or
                            f.startswith('.git/')):
                            continue
                        # Clean up path separators
                        clean_path = f.replace('\\', '/').strip('/')
                        if clean_path:  # Make sure we have a valid path
                            valid_files.append(f)
                    
                    if not valid_files:
                        return Response({
                            'error': 'No valid files found in zip archive',
                            'message': 'Zip file contains no extractable documents'
                        }, status=status.HTTP_400_BAD_REQUEST)
                    
                    # Check for supported file types
                    supported_extensions = ['.pdf', '.doc', '.docx', '.txt', '.md', '.rtf']
                    
                    with transaction.atomic():
                        for file_path in valid_files:
                            try:
                                # Get file extension
                                _, ext = os.path.splitext(file_path.lower())
                                
                                if ext not in supported_extensions:
                                    failed_extractions.append({
                                        'filename': file_path,
                                        'error': f'Unsupported file type: {ext}'
                                    })
                                    continue
                                
                                # Extract file data
                                with zip_ref.open(file_path) as extracted_file:
                                    file_data = extracted_file.read()
                                
                                # Preserve the full relative path (like folder upload)
                                # Only clean up the path for problematic characters but keep structure
                                filename = file_path
                                
                                # Clean up path separators for cross-platform compatibility
                                filename = filename.replace('\\', '/').strip('/')
                                
                                # Skip files that are in system directories we filtered out earlier
                                if (filename.startswith('__MACOSX/') or 
                                    filename.startswith('.DS_Store') or
                                    '/.DS_Store' in filename):
                                    failed_extractions.append({
                                        'filename': filename,
                                        'error': 'System file or directory'
                                    })
                                    continue
                                
                                # Create document record
                                document = ProjectDocument.objects.create(
                                    project=project,
                                    original_filename=filename,
                                    file_size=len(file_data),
                                    file_type=self._get_mime_type_from_extension(ext),
                                    file_extension=ext,
                                    upload_status='processing',
                                    uploaded_by=request.user
                                )
                                
                                # Save file
                                doc_file_path = document.get_storage_path()
                                saved_path = default_storage.save(doc_file_path, ContentFile(file_data))
                                document.file_path = saved_path
                                document.upload_status = 'ready'
                                document.save()
                                
                                uploaded_documents.append(ProjectDocumentSerializer(document).data)
                                extracted_files_info.append({
                                    'original_path': file_path,
                                    'filename': filename,  # Now includes full path
                                    'size': len(file_data),
                                    'extension': ext
                                })
                                
                            except Exception as e:
                                failed_extractions.append({
                                    'filename': file_path,
                                    'error': str(e)
                                })
                                logger.error(f"Failed to extract {file_path}: {e}")
                
            finally:
                # Clean up temporary file
                try:
                    os.unlink(temp_file_path)
                except:
                    pass
            
            return Response({
                'uploaded_documents': uploaded_documents,
                'failed_extractions': failed_extractions,
                'extracted_files_info': extracted_files_info,
                'zip_filename': uploaded_file.name,
                'total_files_in_zip': len(file_list),
                'total_valid_files': len(valid_files),
                'total_extracted': len(uploaded_documents),
                'total_failed': len(failed_extractions),
                'message': f'Zip extraction completed: {len(uploaded_documents)} files extracted, {len(failed_extractions)} failed',
                'api_version': 'universal_v1'
            }, status=status.HTTP_201_CREATED if uploaded_documents else status.HTTP_400_BAD_REQUEST)
            
        except zipfile.BadZipFile:
            return Response({
                'error': 'Invalid zip file', 
                'message': 'The uploaded file is not a valid zip archive'
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'error': 'Zip upload failed', 'detail': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _get_mime_type_from_extension(self, ext: str) -> str:
        """Get MIME type from file extension"""
        mime_types = {
            '.pdf': 'application/pdf',
            '.doc': 'application/msword',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.txt': 'text/plain',
            '.md': 'text/markdown',
            '.rtf': 'application/rtf'
        }
        return mime_types.get(ext.lower(), 'application/octet-stream')
    
    @action(detail=True, methods=['post'])
    def process_documents(self, request, project_id=None):
        """Process project documents using consolidated processing - FIXED"""
        from vector_search.consolidated_api_views import process_unified_consolidated
        
        # Delegate to the consolidated processing endpoint
        logger.info(f"🚀 UNIVERSAL: Delegating document processing for project {project_id}")
        # Convert DRF request to Django HttpRequest for compatibility
        return process_unified_consolidated(request._request, project_id)
    
    @action(detail=True, methods=['post'])
    def search(self, request, project_id=None):
        """Search project documents using consolidated search"""
        from vector_search.consolidated_api_views import search_unified_consolidated
        
        # Delegate to the consolidated search endpoint
        logger.info(f"🔍 UNIVERSAL: Delegating document search for project {project_id}")
        return search_unified_consolidated(request._request, project_id)
    
    @action(detail=True, methods=['get'])
    def vector_status(self, request, project_id=None):
        """Get vector status using consolidated status endpoint"""
        from vector_search.consolidated_api_views import get_vector_status_consolidated
        
        # Delegate to the consolidated status endpoint
        logger.info(f"📊 UNIVERSAL: Delegating vector status for project {project_id}")
        return get_vector_status_consolidated(request._request, project_id)
    
    @action(detail=True, methods=['get'])
    def capabilities(self, request, project_id=None):
        """Get project capabilities using consolidated capabilities endpoint"""
        from vector_search.consolidated_api_views import get_project_capabilities_consolidated
        
        # Delegate to the consolidated capabilities endpoint
        logger.info(f"🎯 UNIVERSAL: Delegating capabilities check for project {project_id}")
        return get_project_capabilities_consolidated(request._request, project_id)
    
    @action(detail=True, methods=['delete'])
    def delete_document(self, request, project_id=None):
        """Delete a specific document from the project"""
        project = self.get_object()
        document_id = request.data.get('document_id') or request.query_params.get('document_id')
        
        if not document_id:
            return Response({
                'error': 'document_id is required',
                'message': 'Please specify which document to delete'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Try to find by document_id (UUID) first, then fallback to id (integer)
            try:
                # First try as UUID (most likely case)
                document = project.documents.get(document_id=document_id)
            except (ValueError, ProjectDocument.DoesNotExist):
                # Fallback to integer id if UUID lookup fails
                document = project.documents.get(id=document_id)
            document_name = document.original_filename
            
            # Delete the file from storage if it exists
            if document.file_path and default_storage.exists(document.file_path):
                default_storage.delete(document.file_path)
            
            # Delete the database record
            document.delete()
            
            logger.info(f"🗑️ UNIVERSAL: Deleted document {document_name} from project {project_id}")
            
            return Response({
                'message': f'Document "{document_name}" deleted successfully',
                'document_id': document_id,
                'project_id': project_id,
                'api_version': 'universal_v1'
            }, status=status.HTTP_200_OK)
            
        except ProjectDocument.DoesNotExist:
            return Response({
                'error': 'Document not found',
                'message': f'Document with ID {document_id} does not exist in this project'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"❌ UNIVERSAL: Failed to delete document {document_id}: {e}")
            return Response({
                'error': 'Delete failed',
                'detail': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    # ============================================================================
    # CUSTOM AGENT ORCHESTRATION ENDPOINTS (JSON Schema Based - When Available)
    # ============================================================================
    
    @action(detail=True, methods=['get', 'post'])
    def agent_workflows(self, request, project_id=None):
        """
        Universal agent workflow management with CUSTOM JSON schema validation
        """
        project = self.get_object()
        logger.info(f"🤖 UNIVERSAL: Agent workflows request for project {project.name} ({project_id})")
        
        if not SCHEMA_VALIDATOR_AVAILABLE:
            return Response({
                'error': 'Schema validator not available',
                'message': 'Please install jsonschema package: pip install jsonschema>=4.0.0',
                'workflows': [],
                'total_count': 0,
                'api_version': 'universal_v1',
                'agent_system': 'basic'
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        
        if request.method == 'GET':
            workflows = project.agent_workflows.all().order_by('-updated_at')
            serializer = AgentWorkflowSerializer(workflows, many=True)
            
            response_data = {
                'workflows': serializer.data,
                'total_count': workflows.count(),
                'project_id': project_id,
                'project_name': project.name,
                'template_type': project.template_type,
                'agent_capabilities': {
                    'schema_version': '1.0.0',
                    'system_type': 'custom_aicc_schema',
                    'supports_json_validation': True,
                    'supports_flow_analysis': True,
                    'autogen_removed': True
                },
                'api_version': 'universal_v1',
                'agent_system': 'custom_aicc_schema',
                'retrieved_at': timezone.now().isoformat()
            }
            
            return Response(response_data, status=status.HTTP_200_OK)
        
        elif request.method == 'POST':
            workflow_data = request.data.copy()
            
            # Validate workflow using our custom JSON schema
            if 'graph_json' in workflow_data and self.workflow_validator:
                is_valid, validation_errors, analysis = self.workflow_validator.validate_workflow(
                    workflow_data['graph_json']
                )
                
                if not is_valid:
                    return Response({
                        'error': 'Workflow validation failed',
                        'validation_errors': validation_errors,
                        'schema_analysis': analysis,
                        'api_version': 'universal_v1',
                        'agent_system': 'custom_aicc_schema'
                    }, status=status.HTTP_400_BAD_REQUEST)
            
            workflow_data['project'] = project.id
            workflow_data['created_by'] = request.user.id
            
            serializer = AgentWorkflowSerializer(data=workflow_data)
            if serializer.is_valid():
                workflow = serializer.save(project=project, created_by=request.user)
                
                response_data = {
                    **serializer.data,
                    'message': 'Workflow created successfully with custom JSON schema validation',
                    'project_id': project_id,
                    'api_version': 'universal_v1',
                    'agent_system': 'custom_aicc_schema',
                    'created_at': timezone.now().isoformat()
                }
                
                return Response(response_data, status=status.HTTP_201_CREATED)
            else:
                return Response({
                    'error': 'Invalid workflow data',
                    'validation_errors': serializer.errors,
                    'api_version': 'universal_v1'
                }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['get', 'put', 'delete'])
    def agent_workflow(self, request, project_id=None):
        """Single agent workflow management"""
        project = self.get_object()
        workflow_id = request.query_params.get('workflow_id')
        
        if not workflow_id:
            return Response({
                'error': 'workflow_id parameter required',
                'api_version': 'universal_v1'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            workflow = project.agent_workflows.get(workflow_id=workflow_id)
        except AgentWorkflow.DoesNotExist:
            return Response({
                'error': 'Workflow not found',
                'api_version': 'universal_v1'
            }, status=status.HTTP_404_NOT_FOUND)
        
        if request.method == 'GET':
            serializer = AgentWorkflowSerializer(workflow)
            return Response({
                **serializer.data,
                'project_id': project_id,
                'api_version': 'universal_v1',
                'agent_system': 'custom_aicc_schema' if SCHEMA_VALIDATOR_AVAILABLE else 'basic'
            })
        
        elif request.method == 'PUT':
            serializer = AgentWorkflowSerializer(workflow, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response({
                    **serializer.data,
                    'message': 'Workflow updated successfully',
                    'api_version': 'universal_v1'
                })
            else:
                return Response({
                    'error': 'Invalid update data',
                    'validation_errors': serializer.errors,
                    'api_version': 'universal_v1'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        elif request.method == 'DELETE':
            workflow_name = workflow.name
            workflow.delete()
            return Response({
                'message': f'Workflow "{workflow_name}" deleted successfully',
                'api_version': 'universal_v1'
            }, status=status.HTTP_204_NO_CONTENT)
    
    def destroy(self, request, *args, **kwargs):
        """
        Delete a project - ADMIN ONLY with password confirmation
        DELETE /api/projects/{project_id}/
        """
        # SECURITY: Only admin users can delete projects
        if not hasattr(request.user, 'is_admin') or not request.user.is_admin:
            logger.warning(f"🚫 UNIVERSAL: Non-admin user {request.user.email} attempted to delete project")
            return Response({
                'error': 'Permission denied',
                'detail': 'Only administrators can delete projects',
                'user_role': getattr(request.user, 'role', 'unknown'),
                'required_role': 'ADMIN',
                'api_version': 'universal_v1'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # SECURITY: Require password confirmation for project deletion
        password = request.data.get('password')
        if not password:
            return Response({
                'error': 'Password confirmation required',
                'detail': 'Project deletion requires password confirmation for security',
                'required_field': 'password',
                'api_version': 'universal_v1'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # SECURITY: Verify admin password
        if not request.user.check_password(password):
            logger.warning(f"🚫 UNIVERSAL: Invalid password for project deletion by {request.user.email}")
            return Response({
                'error': 'Authentication failed',
                'detail': 'Invalid password provided',
                'api_version': 'universal_v1'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        # Get the project
        project = self.get_object()
        project_name = project.name
        project_id = project.project_id
        documents_count = project.documents.count()
        
        logger.warning(f"🗑️ UNIVERSAL: Admin {request.user.email} deleting project {project_name} ({project_id}) with {documents_count} documents")
        
        try:
            with transaction.atomic():
                # Delete all associated files from storage
                deleted_files = 0
                for document in project.documents.all():
                    if document.file_path and default_storage.exists(document.file_path):
                        try:
                            default_storage.delete(document.file_path)
                            deleted_files += 1
                        except Exception as e:
                            logger.error(f"❌ UNIVERSAL: Failed to delete file {document.file_path}: {e}")
                
                # Delete vector collections if they exist
                try:
                    if hasattr(project, 'vector_collection'):
                        project.vector_collection.delete()
                        logger.info(f"🗑️ UNIVERSAL: Deleted vector collection for project {project_name}")
                except Exception as e:
                    logger.error(f"❌ UNIVERSAL: Failed to delete vector collection: {e}")
                
                # Delete all agent workflows
                workflows_count = project.agent_workflows.count()
                if workflows_count > 0:
                    project.agent_workflows.all().delete()
                    logger.info(f"🗑️ UNIVERSAL: Deleted {workflows_count} agent workflows")
                
                # Delete the project itself (will cascade delete documents, permissions, etc.)
                project.delete()
                
                logger.info(f"✅ UNIVERSAL: Successfully deleted project {project_name} ({project_id})")
                
                return Response({
                    'message': f'Project "{project_name}" deleted successfully',
                    'project_id': str(project_id),
                    'project_name': project_name,
                    'deleted_documents': documents_count,
                    'deleted_files': deleted_files,
                    'deleted_workflows': workflows_count,
                    'deleted_by': request.user.email,
                    'deleted_at': timezone.now().isoformat(),
                    'api_version': 'universal_v1'
                }, status=status.HTTP_200_OK)
                
        except Exception as e:
            logger.error(f"❌ UNIVERSAL: Failed to delete project {project_name}: {e}")
            return Response({
                'error': 'Deletion failed',
                'detail': str(e),
                'project_id': str(project_id),
                'project_name': project_name,
                'api_version': 'universal_v1'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def health(self, request):
        """Health check for universal project API"""
        return Response({
            'status': 'healthy',
            'api_version': 'universal_v1',
            'agent_system': 'custom_aicc_schema' if SCHEMA_VALIDATOR_AVAILABLE else 'basic',
            'schema_validator_available': SCHEMA_VALIDATOR_AVAILABLE,
            'timestamp': timezone.now().isoformat(),
            'message': 'Universal Project API is operational (AutoGen completely removed)',
            'features': {
                'template_independence': True,
                'universal_interface': True,
                'autogen_removed': True,
                'custom_implementation_ready': SCHEMA_VALIDATOR_AVAILABLE
            }
        })
