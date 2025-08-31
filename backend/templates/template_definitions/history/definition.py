class HistoryTemplateDefinition:
    """History document analysis template definition"""
    
    def get_complete_configuration(self):
        """Return complete template configuration for project cloning"""
        return {
            'name': 'History Document Analysis',
            'template_type': 'history',
            'description': 'Specialized template for analyzing historical documents and research',
            'instructions': 'Upload historical documents for analysis. Focus on historical context, events, and significance.',
            'suggested_questions': [
                'What historical period does this document represent?',
                'What are the key historical events mentioned?',
                'Who are the important historical figures?',
                'What is the historical significance of this document?'
            ],
            'required_fields': ['document_upload'],
            'analysis_focus': 'Historical document analysis with focus on context, events, figures, and historical significance',
            'icon_class': 'fa-university',
            'color_theme': 'academic-gold',
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
                'max_documents': 40,
                'allowed_file_types': ['pdf', 'doc', 'docx', 'txt']
            },
            'ui_configuration': {
                'layout': 'single_page',
                'theme': 'history',
                'features': {
                    'drag_drop_upload': True,
                    'timeline_visualization': True,
                    'historical_context_analysis': True
                }
            }
        }
