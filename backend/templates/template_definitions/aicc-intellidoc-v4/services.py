# templates/template_definitions/aicc-intellidoc-v4/services.py
# TEMPLATE INDEPENDENCE COMPLIANT: Template management services ONLY

import logging
from pathlib import Path


# Template-specific logger
logger = logging.getLogger('templates.aicc-intellidoc-v4')

class AICCIntelliDocTemplateManagementService:
    """
    ✅ TEMPLATE INDEPENDENCE COMPLIANT
    
    Handles TEMPLATE MANAGEMENT operations ONLY:
    - Template discovery
    - Template metadata management
    - Template configuration serving
    
    ❌ DOES NOT handle project operations (projects use universal services)
    """
    
    def __init__(self):
        self.template_id = 'aicc-intellidoc-v4'
        logger.info(f"Initialized {self.__class__.__name__} for template {self.template_id} (Template Management Only)")
    
    def get_template_discovery_data(self):
        """Get template discovery data for template selection page"""
        logger.info(f"Getting template discovery data for {self.template_id}")
        
        try:
            from .definition import AICCIntelliDocTemplateDefinition
            template_definition = AICCIntelliDocTemplateDefinition()
            config = template_definition.get_complete_configuration()
            
            discovery_data = {
                'template_id': self.template_id,
                'name': config.get('name'),
                'description': config.get('description'),
                'capabilities': {
                    'hierarchical_processing': True,
                    'advanced_navigation': True,
                    'ai_analysis': True,
                    'multi_document_support': True,
                    'category_classification': True,
                    'vector_search': True,
                    'template_independence': True
                },
                'configuration': config,
                'template_management_only': True
            }
            
            logger.info(f"Template discovery data generated for {self.template_id}")
            return discovery_data
            
        except Exception as e:
            logger.error(f"Error getting template discovery data for {self.template_id}: {str(e)}")
            raise

    def get_template_configuration(self):
        """Get complete template configuration for project creation data cloning"""
        logger.info(f"Getting template configuration for {self.template_id}")
        
        try:
            from .definition import AICCIntelliDocTemplateDefinition
            template_definition = AICCIntelliDocTemplateDefinition()
            config = template_definition.get_complete_configuration()
            
            logger.info(f"Template configuration retrieved for {self.template_id}")
            return config
            
        except Exception as e:
            logger.error(f"Error getting template configuration for {self.template_id}: {str(e)}")
            raise

    def validate_template_integrity(self):
        """Validate template file integrity"""
        logger.info(f"Validating template integrity for {self.template_id}")
        
        try:
            template_dir = Path(__file__).parent
            required_files = [
                'definition.py',
                'views.py',
                'serializers.py', 
                'urls.py',
                'services.py',
                'hierarchical_config.py',
                'metadata.json'
            ]
            
            integrity_report = {
                'template_id': self.template_id,
                'files_checked': len(required_files),
                'files_present': 0,
                'missing_files': [],
                'integrity_passed': True
            }
            
            for file_name in required_files:
                file_path = template_dir / file_name
                if file_path.exists():
                    integrity_report['files_present'] += 1
                else:
                    integrity_report['missing_files'].append(file_name)
                    integrity_report['integrity_passed'] = False
            
            logger.info(f"Template integrity validation completed for {self.template_id}: {integrity_report['files_present']}/{integrity_report['files_checked']} files present")
            return integrity_report
            
        except Exception as e:
            logger.error(f"Error validating template integrity for {self.template_id}: {str(e)}")
            raise


