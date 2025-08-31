"""
Django Admin for Public Chatbot - Isolated Management Interface
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from .models import (
    PublicChatRequest, IPUsageLimit, PublicKnowledgeDocument, 
    ChatbotConfiguration
)


def get_user_identifier(user):
    """
    Get user identifier handling different User model attributes
    """
    try:
        return user.username
    except AttributeError:
        try:
            return user.email
        except AttributeError:
            try:
                return user.name
            except AttributeError:
                return str(user)


@admin.register(PublicChatRequest)
class PublicChatRequestAdmin(admin.ModelAdmin):
    """Admin interface for public chat requests"""
    list_display = [
        'request_id', 'ip_address', 'status', 'message_preview', 
        'response_generated', 'llm_provider_used', 'response_time_ms', 
        'created_at'
    ]
    list_filter = [
        'status', 'response_generated', 'llm_provider_used', 
        'chroma_context_used', 'created_at'
    ]
    search_fields = ['request_id', 'ip_address', 'message_preview']
    readonly_fields = [
        'request_id', 'message_hash', 'created_at', 'completed_at', 
        'response_time_ms'
    ]
    ordering = ['-created_at']
    
    fieldsets = (
        ('Request Info', {
            'fields': ('request_id', 'session_id', 'created_at', 'completed_at')
        }),
        ('Client Info', {
            'fields': ('ip_address', 'user_agent', 'origin_domain')
        }),
        ('Message', {
            'fields': ('message_preview', 'message_length', 'message_hash')
        }),
        ('Response', {
            'fields': (
                'response_generated', 'response_length', 'response_time_ms', 'status'
            )
        }),
        ('ChromaDB', {
            'fields': (
                'chroma_search_time_ms', 'chroma_results_found', 'chroma_context_used'
            )
        }),
        ('LLM', {
            'fields': (
                'llm_provider_used', 'llm_model_used', 'llm_tokens_used', 
                'llm_cost_estimate'
            )
        }),
        ('Errors', {
            'fields': ('error_type', 'error_message'),
            'classes': ('collapse',)
        })
    )
    
    def has_add_permission(self, request):
        return False  # No manual creation
    
    def has_change_permission(self, request, obj=None):
        return False  # Read-only


@admin.register(IPUsageLimit)
class IPUsageLimitAdmin(admin.ModelAdmin):
    """Admin interface for IP usage tracking"""
    list_display = [
        'ip_address', 'daily_request_count', 'total_requests', 
        'successful_requests', 'security_violations', 'is_blocked_display', 
        'last_seen'
    ]
    list_filter = [
        'is_blocked', 'country_code', 'last_reset_date', 'security_violations'
    ]
    search_fields = ['ip_address', 'country_code']
    readonly_fields = [
        'total_requests', 'successful_requests', 'first_seen', 'last_seen'
    ]
    ordering = ['-last_seen']
    
    fieldsets = (
        ('IP Info', {
            'fields': ('ip_address', 'country_code', 'user_agent_pattern')
        }),
        ('Usage Stats', {
            'fields': (
                'daily_request_count', 'daily_token_usage', 'last_reset_date',
                'hourly_request_count', 'last_hourly_reset'
            )
        }),
        ('Totals', {
            'fields': (
                'total_requests', 'successful_requests', 'security_violations',
                'first_seen', 'last_seen'
            )
        }),
        ('Blocking', {
            'fields': ('is_blocked', 'blocked_until', 'block_reason')
        })
    )
    
    def is_blocked_display(self, obj):
        if obj.is_blocked:
            if obj.blocked_until and obj.blocked_until > timezone.now():
                return format_html('<span style="color: red;">🚫 BLOCKED until {}</span>', 
                                 obj.blocked_until.strftime('%Y-%m-%d %H:%M'))
            else:
                return format_html('<span style="color: orange;">⚠️ BLOCKED (expired)</span>')
        return format_html('<span style="color: green;">✅ ACTIVE</span>')
    
    is_blocked_display.short_description = 'Status'


@admin.register(PublicKnowledgeDocument)
class PublicKnowledgeDocumentAdmin(admin.ModelAdmin):
    """Admin interface for public knowledge documents"""
    list_display = [
        'title', 'category', 'approval_status_display', 'sync_status_display', 
        'quality_score', 'search_count', 'updated_at'
    ]
    list_filter = [
        'category', 'is_approved', 'security_reviewed', 'synced_to_chromadb',
        'language', 'created_at'
    ]
    search_fields = ['title', 'content_preview', 'tags', 'document_id']
    readonly_fields = [
        'document_id', 'content_hash', 'content_preview', 'chromadb_id',
        'last_synced', 'search_count', 'last_used', 'created_at', 'updated_at'
    ]
    
    fieldsets = (
        ('Document Info', {
            'fields': ('document_id', 'title', 'category', 'subcategory', 'language')
        }),
        ('Content', {
            'fields': ('content', 'content_preview', 'content_hash', 'tags')
        }),
        ('Approval', {
            'fields': (
                'is_approved', 'security_reviewed', 'quality_score',
                'created_by', 'approved_by'
            )
        }),
        ('ChromaDB Sync', {
            'fields': (
                'synced_to_chromadb', 'chromadb_id', 'last_synced', 'sync_error'
            )
        }),
        ('Usage Stats', {
            'fields': ('search_count', 'last_used')
        }),
        ('Metadata', {
            'fields': ('source_url', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def approval_status_display(self, obj):
        if obj.is_approved and obj.security_reviewed:
            return format_html('<span style="color: green;">✅ APPROVED</span>')
        elif obj.is_approved:
            return format_html('<span style="color: orange;">⏳ PENDING SECURITY</span>')
        else:
            return format_html('<span style="color: red;">❌ NOT APPROVED</span>')
    
    approval_status_display.short_description = 'Approval'
    
    def sync_status_display(self, obj):
        if obj.synced_to_chromadb and obj.last_synced:
            return format_html('<span style="color: green;">✅ SYNCED {}</span>', 
                             obj.last_synced.strftime('%m/%d %H:%M'))
        elif obj.sync_error:
            return format_html('<span style="color: red;">❌ ERROR</span>')
        else:
            return format_html('<span style="color: orange;">⏳ PENDING</span>')
    
    sync_status_display.short_description = 'ChromaDB Sync'
    
    actions = ['approve_documents', 'sync_to_chromadb_immediately', 'mark_for_sync']
    
    def approve_documents(self, request, queryset):
        """Approve selected documents"""
        user_identifier = get_user_identifier(request.user)
        updated = queryset.update(
            is_approved=True,
            security_reviewed=True,
            approved_by=user_identifier
        )
        self.message_user(request, f'{updated} documents approved.')
    
    approve_documents.short_description = 'Approve selected documents'
    
    def sync_to_chromadb_immediately(self, request, queryset):
        """Immediately sync selected documents to ChromaDB"""
        from .services import PublicKnowledgeService
        from django.utils import timezone
        
        # Get ChromaDB service
        try:
            knowledge_service = PublicKnowledgeService.get_instance()
            if not knowledge_service.is_ready:
                self.message_user(request, 
                                 "❌ ChromaDB service is not ready. Check connection and try again.",
                                 level='ERROR')
                return
        except Exception as e:
            self.message_user(request, 
                             f"❌ Failed to initialize ChromaDB service: {e}",
                             level='ERROR')
            return
        
        # Filter approved documents
        approved_docs = queryset.filter(is_approved=True, security_reviewed=True)
        synced_count = 0
        error_count = 0
        
        for doc in approved_docs:
            try:
                # Sync using the same method as management command
                success = self._sync_document_immediately(doc, knowledge_service)
                
                if success:
                    synced_count += 1
                else:
                    error_count += 1
                    
            except Exception as e:
                error_count += 1
                doc.sync_error = str(e)[:500]
                doc.save()
        
        # Show results
        if synced_count > 0:
            self.message_user(request, 
                             f"✅ Successfully synced {synced_count} documents to ChromaDB immediately!")
        if error_count > 0:
            self.message_user(request, 
                             f"❌ Failed to sync {error_count} documents. Check sync errors in document details.",
                             level='WARNING')
    
    sync_to_chromadb_immediately.short_description = '🚀 Sync to ChromaDB immediately'
    
    def mark_for_sync(self, request, queryset):
        """Mark documents for later sync (manual command needed)"""
        count = 0
        for doc in queryset.filter(is_approved=True, security_reviewed=True):
            doc.synced_to_chromadb = False  # Mark for sync
            doc.save()
            count += 1
        
        self.message_user(request, 
                         f'{count} documents marked for sync. Run: python manage.py sync_public_knowledge')
    
    mark_for_sync.short_description = '📋 Mark for later sync'
    
    def _sync_document_immediately(self, doc, service):
        """
        Sync individual document to ChromaDB immediately
        Using the same logic as the management command
        """
        from django.utils import timezone
        
        try:
            # Create base metadata for all chunks
            base_metadata = {
                'title': doc.title,
                'category': doc.category,
                'subcategory': doc.subcategory or '',
                'source': 'Public Knowledge Base',
                'document_id': doc.document_id,
                'quality_score': doc.quality_score,
                'language': doc.language,
                'tags': doc.tags,
                'source_url': doc.source_url or '',
                'sync_timestamp': timezone.now().isoformat(),
                'approved_by': doc.approved_by,
                'isolation_level': 'public_only'
            }
            
            # Determine if this is an update or new document
            is_update = doc.synced_to_chromadb or service.document_exists_in_chromadb(doc.document_id)
            
            # Check if service supports advanced chunking
            if hasattr(service, 'use_advanced_features') and service.use_advanced_features and hasattr(service, 'chunker'):
                # Use advanced chunking system
                chunks = service.chunker.chunk_document(
                    content=doc.content,
                    document_id=doc.document_id,
                    metadata=base_metadata
                )
                
                if chunks:
                    # Prepare data for ChromaDB
                    documents = [chunk.content for chunk in chunks]
                    metadatas = [{
                        **chunk.metadata,
                        'chunk_index': chunk.chunk_index,
                        'total_chunks': chunk.total_chunks,
                        'chunk_type': chunk.chunk_type,
                        'token_count': chunk.token_count,
                        'char_count': chunk.char_count
                    } for chunk in chunks]
                    ids = [chunk.chunk_id for chunk in chunks]
                    
                    # Use smart sync to handle updates and prevent duplicates
                    success = service.smart_sync_knowledge(
                        documents=documents, 
                        metadatas=metadatas, 
                        ids=ids,
                        document_id=doc.document_id,
                        force_update=is_update
                    )
                else:
                    success = False
            else:
                # Fallback to legacy method with smart sync
                documents = [doc.content]
                metadatas = [base_metadata]
                ids = [f"pub_{doc.document_id}"]
                success = service.smart_sync_knowledge(
                    documents=documents, 
                    metadatas=metadatas, 
                    ids=ids,
                    document_id=doc.document_id,
                    force_update=is_update
                )
            
            if success:
                # Update sync status
                doc.synced_to_chromadb = True
                doc.chromadb_id = f"pub_{doc.document_id}"
                doc.last_synced = timezone.now()
                doc.sync_error = ''
                doc.save()
                return True
            else:
                doc.sync_error = 'Failed to add to ChromaDB collection'
                doc.save()
                return False
                
        except Exception as e:
            doc.sync_error = str(e)[:500]
            doc.save()
            return False


@admin.register(ChatbotConfiguration)
class ChatbotConfigurationAdmin(admin.ModelAdmin):
    """Admin interface for chatbot configuration"""
    
    def has_add_permission(self, request):
        # Only one configuration instance allowed
        return not ChatbotConfiguration.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        return False  # Don't allow deletion of config
    
    fieldsets = (
        ('Service Control', {
            'fields': ('is_enabled', 'enable_vector_search', 'maintenance_mode', 'maintenance_message')
        }),
        ('Rate Limiting', {
            'fields': (
                'daily_requests_per_ip', 'hourly_requests_per_ip', 
                'max_message_length'
            )
        }),
        ('ChromaDB Settings', {
            'fields': ('max_search_results', 'similarity_threshold')
        }),
        ('LLM Settings', {
            'fields': (
                'default_llm_provider', 'default_model', 'max_response_tokens',
                'system_prompt'
            )
        }),
        ('Security', {
            'fields': (
                'enable_security_scanning', 'block_suspicious_ips', 
                'log_full_conversations'
            )
        }),
        ('Audit', {
            'fields': ('created_at', 'updated_at', 'updated_by'),
            'classes': ('collapse',)
        })
    )
    
    readonly_fields = ['created_at', 'updated_at']
    list_display = ['__str__', 'vector_search_status', 'is_enabled', 'maintenance_mode', 'updated_at']
    
    def vector_search_status(self, obj):
        """Display vector search status with emoji"""
        if obj.enable_vector_search:
            return "🔍 Enabled"
        else:
            return "❌ Disabled"
    vector_search_status.short_description = "Vector Search"
    
    def save_model(self, request, obj, form, change):
        obj.updated_by = get_user_identifier(request.user)
        super().save_model(request, obj, form, change)


# Admin site customization
admin.site.site_header = "Public Chatbot Administration"
admin.site.site_title = "Public Chatbot Admin"
admin.site.index_title = "Public Chatbot Management"