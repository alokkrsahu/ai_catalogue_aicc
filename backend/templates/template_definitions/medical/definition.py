class MedicalTemplateDefinition:
    """Medical document analysis template definition"""
    
    def get_complete_configuration(self):
        """Return complete template configuration for project cloning"""
        return {
            'name': 'Medical Document Analysis',
            'template_type': 'medical',
            'description': 'Specialized template for analyzing medical documents and research',
            'instructions': 'Upload medical documents for analysis. Focus on clinical data, research findings, and medical terminology.',
            'suggested_questions': [
                'What are the key medical findings?',
                'What treatments are recommended?',
                'Are there any contraindications mentioned?',
                'What are the clinical outcomes?'
            ],
            'required_fields': ['document_upload'],
            'analysis_focus': 'Medical document analysis with focus on clinical data, treatments, outcomes, and medical terminology',
            'icon_class': 'fa-user-md',
            'color_theme': 'forest-green',
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
                'max_documents': 30,
                'allowed_file_types': ['pdf', 'doc', 'docx', 'txt']
            },
            'ui_configuration': {
                'layout': 'single_page',
                'theme': 'medical',
                'features': {
                    'drag_drop_upload': True,
                    'medical_terminology_highlighting': True,
                    'clinical_section_detection': True
                }
            }
        }
