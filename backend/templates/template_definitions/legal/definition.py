class LegalTemplateDefinition:
    """Legal document analysis template definition"""
    
    def get_complete_configuration(self):
        """Return complete template configuration for project cloning"""
        return {
            'name': 'Legal Document Analysis',
            'template_type': 'legal',
            'description': 'Specialized template for analyzing legal documents',
            'instructions': 'Upload legal documents for analysis. Focus on contracts, agreements, and legal terminology.',
            'suggested_questions': [
                'What are the key terms and conditions?',
                'Are there any potential legal risks?',
                'What are the obligations of each party?',
                'Are there any unusual clauses?'
            ],
            'required_fields': ['document_upload'],
            'analysis_focus': 'Legal document analysis with focus on contracts, terms, obligations, and legal risks',
            'icon_class': 'fa-balance-scale',
            'color_theme': 'burgundy',
            'has_navigation': False,
            'total_pages': 1,
            'navigation_pages': [],
            'processing_capabilities': {
                'supports_ai_analysis': True,
                'supports_vector_search': True,
                'max_file_size': 10485760,
                'supported_formats': ['pdf', 'doc', 'docx', 'txt'],
                'ai_models': {
                    'content_analysis': 'gpt-4',
                    'embedding_model': 'text-embedding-ada-002'
                }
            },
            'validation_rules': {
                'required_fields': ['document_upload'],
                'max_documents': 25,
                'allowed_file_types': ['pdf', 'doc', 'docx', 'txt']
            },
            'ui_configuration': {
                'layout': 'single_page',
                'theme': 'legal',
                'features': {
                    'drag_drop_upload': True,
                    'legal_terminology_highlighting': True,
                    'contract_section_detection': True
                }
            }
        }
