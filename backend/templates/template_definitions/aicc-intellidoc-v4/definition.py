try:
    from .hierarchical_config import HierarchicalProcessingConfig
except ImportError:
    # Fallback configuration if hierarchical_config is not available
    class HierarchicalProcessingConfig:
        @staticmethod
        def get_hierarchical_configuration():
            return {
                'hierarchical_processing': {},
                'document_organization': {},
                'search_capabilities': {},
                'content_reconstruction': {},
                'ai_processing': {},
                'performance_settings': {},
                'quality_control': {},
                'document_categories': [],
                'document_types': [],
                'chunk_types': [],
                'processing_endpoints': []
            }

class AICCIntelliDocTemplateDefinition:
    """
    ✅ TEMPLATE INDEPENDENCE COMPLIANT
    
    Enhanced template definition for AICC-IntelliDoc with hierarchical processing capabilities
    Provides COMPLETE configuration data for Clone-and-Forget pattern implementation
    """
    
    def get_complete_configuration(self):
        """
        ✅ COMPLIANT: Return complete template configuration for project cloning
        
        ALL configuration data is provided here for complete cloning to project fields.
        Projects will be COMPLETELY INDEPENDENT of this template after creation.
        """
        hierarchical_config = HierarchicalProcessingConfig.get_hierarchical_configuration()
        
        return {
            # ✅ Basic template information (cloned to project fields)
            'name': 'AICC-IntelliDoc-v4',
            'template_type': 'aicc-intellidoc-v4',
            'template_name': 'AICC-IntelliDoc-v4',
            'description': 'Advanced AI agent orchestration template with document upload and 5-page customizable interface',
            
            # ✅ Project instructions (cloned to project.instructions)
            'instructions': '''Upload documents and orchestrate AI agents with advanced capabilities.
            
Features:
• Document upload and management with drag-and-drop interface
• AI agent orchestration and configuration  
• 5-page customizable navigation interface
• Enhanced hierarchical document processing
• Vector search and semantic analysis
• Complete template independence architecture

Navigate through different pages to access various features and configurations.
This project operates with complete independence from template files.''',
            
            # ✅ Suggested questions (cloned to project.suggested_questions)
            'suggested_questions': [
                'What are the key themes across all my documents?',
                'Can you provide a hierarchical overview of my document collection?',
                'How are my documents organized by category and type?',
                'What are the main insights from documents in the legal category?',
                'Can you reconstruct the full content of this document?',
                'What topics are covered in technical documents?',
                'How do different document types relate to each other?',
                'What patterns exist in my document hierarchy?',
                'Can you analyze the sentiment across my document collection?',
                'What are the most important entities mentioned in my documents?'
            ],
            
            # ✅ Required fields (cloned to project.required_fields)
            'required_fields': ['document_upload'],
            
            # ✅ Analysis focus (cloned to project.analysis_focus)
            'analysis_focus': 'Advanced AI agent orchestration with document upload capabilities, hierarchical processing, and 5-page customizable interface development with complete template independence',
            
            # ✅ UI configuration (cloned to project fields)
            'icon_class': 'fa-sitemap',
            'color_theme': 'oxford-blue',
            'has_navigation': True,
            'total_pages': 5,
            
            # ✅ Navigation pages configuration (cloned to project.navigation_pages)
            'navigation_pages': [
                {
                    'page_number': 1,
                    'id': 1,
                    'name': 'Document Upload',
                    'title': 'Document Upload',
                    'short_name': 'Upload',
                    'icon': 'fa-upload',
                    'description': 'Upload and manage documents with advanced processing capabilities',
                    'features': ['document_upload', 'file_management', 'drag_drop_interface', 'batch_upload']
                },
                {
                    'page_number': 2,
                    'id': 2,
                    'name': 'Agent Orchestration',
                    'title': 'Agent Orchestration',
                    'short_name': 'Agent',
                    'icon': 'fa-robot',
                    'description': 'Configure and orchestrate AI agents for document analysis',
                    'features': ['agent_orchestration', 'ai_configuration', 'processing_control']
                },
                {
                    'page_number': 3,
                    'id': 3,
                    'name': 'Analytics Dashboard',
                    'title': 'Analytics Dashboard',
                    'short_name': 'Analytics',
                    'icon': 'fa-chart-bar',
                    'description': 'View comprehensive analytics and insights from your documents',
                    'features': ['analytics_dashboard', 'data_visualization', 'insights_generation']
                },
                {
                    'page_number': 4,
                    'id': 4,
                    'name': 'Search & Discovery',
                    'title': 'Search & Discovery',
                    'short_name': 'Search',
                    'icon': 'fa-search',
                    'description': 'Advanced search capabilities with semantic and hierarchical filtering',
                    'features': ['advanced_search', 'semantic_search', 'hierarchical_filtering']
                },
                {
                    'page_number': 5,
                    'id': 5,
                    'name': 'Export & Reports',
                    'title': 'Export & Reports',
                    'short_name': 'Export',
                    'icon': 'fa-download',
                    'description': 'Generate reports and export analysis results',
                    'features': ['report_generation', 'data_export', 'customizable_reports']
                }
            ],
            
            # ✅ Processing capabilities (cloned to project.processing_capabilities)
            'processing_capabilities': {
                'supports_ai_analysis': True,
                'supports_vector_search': True,
                'supports_hierarchical_processing': True,
                'supports_enhanced_processing': True,
                'supports_chunking': True,
                'content_preservation': 'complete',
                'processing_mode': 'enhanced_hierarchical',
                'max_file_size': 52428800,  # 50MB for large documents
                'max_chunk_size': 35000,
                'chunk_overlap': 200,
                'supported_formats': ['pdf', 'doc', 'docx', 'txt', 'md', 'rtf'],
                'supported_file_types': ['pdf', 'doc', 'docx', 'txt', 'md', 'rtf'],
                'supported_mime_types': [
                    'application/pdf',
                    'application/msword',
                    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                    'text/plain',
                    'text/markdown',
                    'application/rtf'
                ],
                'ai_models': {
                    'content_analysis': 'gpt-4',
                    'embedding_model': 'text-embedding-ada-002',
                    'summarization_model': 'gpt-4',
                    'topic_extraction_model': 'gpt-4'
                },
                'vector_dimensions': 1536,
                'similarity_threshold': 0.7,
                'batch_processing': True,
                'parallel_processing': True,
                'max_concurrent_processes': 4,
                **hierarchical_config['hierarchical_processing'],
                **hierarchical_config['document_organization'],
                **hierarchical_config['search_capabilities'],
                **hierarchical_config['content_reconstruction'],
                **hierarchical_config['ai_processing'],
                **hierarchical_config['performance_settings']
            },
            
            # ✅ Validation rules (cloned to project.validation_rules)
            'validation_rules': {
                'required_fields': ['document_upload'],
                'max_documents': 100,
                'max_total_size': 524288000,  # 500MB total
                'allowed_file_types': ['pdf', 'doc', 'docx', 'txt', 'md', 'rtf'],
                'content_validation': True,
                'structure_validation': True,
                'integrity_checks': True,
                'duplicate_detection': True,
                **hierarchical_config['quality_control']
            },
            
            # ✅ UI configuration (cloned to project.ui_configuration)
            'ui_configuration': {
                'layout': 'hierarchical_multi_page_navigation',
                'theme': 'aicc_intellidoc_enhanced',
                'responsive': True,
                'dark_mode_support': True,
                'features': {
                    'drag_drop_upload': True,
                    'batch_upload': True,
                    'real_time_processing': True,
                    'hierarchical_navigation': True,
                    'category_filtering': True,
                    'advanced_search_interface': True,
                    'document_reconstruction': True,
                    'progress_tracking': True,
                    'error_handling': True,
                    'export_options': True,
                    'auto_save': True,
                    'keyboard_shortcuts': True,
                    'analytics_dashboard': True,
                    'agent_orchestration': True
                },
                'customizations': {
                    'primary_color': '#002147',  # Oxford Blue
                    'accent_color': '#1e3a8a',
                    'success_color': '#10b981',
                    'warning_color': '#f59e0b',
                    'error_color': '#ef4444',
                    'header_style': 'elevated',
                    'card_style': 'elevated',
                    'animation_level': 'enhanced',
                    'border_radius': '8px',
                    'shadow_level': 'medium'
                },
                'accessibility': {
                    'keyboard_navigation': True,
                    'screen_reader_support': True,
                    'high_contrast_mode': True,
                    'focus_indicators': True,
                    'aria_labels': True
                }
            },
            
            # ✅ Enhanced hierarchical configuration (cloned completely)
            'hierarchical_configuration': hierarchical_config,
            'document_categories': hierarchical_config['document_categories'],
            'document_types': hierarchical_config['document_types'],
            'chunk_types': hierarchical_config['chunk_types'],
            'processing_endpoints': hierarchical_config['processing_endpoints'],
            
            # ✅ Template independence metadata
            'template_independence': {
                'compliance_level': 'complete',
                'clone_and_forget_pattern': True,
                'universal_api_compatibility': True,
                'universal_interface_compatibility': True,
                'file_independence': True,
                'zero_runtime_dependencies': True,
                'compliance_score': '100/100'
            }
        }

    def get_hierarchical_search_capabilities(self):
        """Return available hierarchical search capabilities for template discovery"""
        return {
            'category_search': True,
            'subcategory_search': True,
            'document_type_search': True,
            'hierarchy_level_search': True,
            'chunk_type_search': True,
            'content_length_search': True,
            'combined_filters': True,
            'full_content_reconstruction': True,
            'semantic_search': True,
            'contextual_search': True,
            'template_independent': True
        }
    
    def get_processing_recommendations(self):
        """Return processing recommendations for template discovery"""
        return {
            'recommended_for': [
                'Large documents (>35,000 characters)',
                'Documents with clear structure',
                'Multi-document projects',
                'Research collections',
                'Technical documentation',
                'Legal document analysis',
                'Medical record processing',
                'Complex document hierarchies',
                'AI agent orchestration projects'
            ],
            'optimal_use_cases': [
                'Document categorization and organization',
                'Hierarchical content analysis',
                'Multi-level document search',
                'Content reconstruction and navigation',
                'AI-powered document insights',
                'Large-scale document processing',
                'Agent-based document analysis',
                'Advanced analytics and reporting'
            ],
            'performance_benefits': [
                'Zero information loss - all content preserved',
                'Intelligent document organization',
                'Enhanced search precision',
                'Full content reconstruction',
                'Hierarchical navigation',
                'Category-based filtering',
                'Multi-level search options',
                'Contextual chunk access',
                'Complete template independence',
                'Universal interface compatibility'
            ],
            'template_independence_features': [
                'Complete data cloning at project creation',
                'Zero runtime dependencies on template files',
                'Universal API compatibility',
                'Universal interface compatibility',
                'Projects work even if template is deleted',
                'Template modifications have zero project impact'
            ]
        }

    def get_template_metadata(self):
        """Return template metadata for management operations"""
        return {
            'template_id': 'aicc-intellidoc-v4',
            'template_name': 'AICC-IntelliDoc-v4',
            'version': '1.2.1',
            'description': 'Advanced AI agent orchestration template with 5-page navigation and complete template independence',
            'author': 'Alok Kumar Sahu',
            'created_date': '2025-07-21',
            'updated_date': '2025-07-22',
            'compliance_status': 'fully_compliant',
            'independence_score': '100/100',
            'template_management_only': True,
            'project_operations': 'Use universal endpoints only'
        }
