"""
Template Cloning Utilities

Provides deep copy functionality for template configuration cloning
to ensure complete independence from template objects.
"""

import copy
import json
import logging
import time
from typing import Dict, Any, Tuple, Optional, List

logger = logging.getLogger(__name__)

# Required fields that should be present in template configuration
REQUIRED_FIELDS = ['navigation_pages', 'processing_capabilities', 
                   'validation_rules', 'ui_configuration']


def deep_clone_configuration_field(value: Any) -> Any:
    """
    Deep clone a configuration field (handles nested structures).
    
    Args:
        value: The value to clone (list, dict, or primitive)
        
    Returns:
        Deep copied value if it's a collection, original value otherwise
    """
    if isinstance(value, (list, dict)):
        return copy.deepcopy(value)
    return value


def validate_template_config(template_config: Dict[str, Any], template_id: str) -> List[str]:
    """
    Validate template configuration has required fields.
    
    Args:
        template_config: Template configuration dictionary
        template_id: Template identifier for logging
        
    Returns:
        List of missing required field names
    """
    missing = [f for f in REQUIRED_FIELDS if f not in template_config]
    if missing:
        logger.warning(f"Template {template_id} missing required fields: {missing}")
    return missing


def clone_template_configuration(
    template_config: Dict[str, Any], 
    template_metadata: Dict[str, Any],
    include_audit_trail: bool = False
) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
    """
    Clone template configuration with deep copy to ensure independence.
    
    Args:
        template_config: Template configuration dictionary
        template_metadata: Template metadata dictionary
        include_audit_trail: Whether to generate audit trail
        
    Returns:
        Tuple of (cloned_config, audit_trail)
        - cloned_config: Deep copied configuration
        - audit_trail: Audit information (None if include_audit_trail=False)
    """
    start_time = time.time() if include_audit_trail else None
    
    audit_trail = None
    if include_audit_trail:
        audit_trail = {
            'template_id': template_metadata.get('template_id', 'unknown'),
            'template_version': template_metadata.get('version', '1.0.0'),
            'fields_cloned': [],
            'fields_with_defaults': [],
            'warnings': []
        }
    
    cloned_config = {}
    
    # Basic fields that may be strings or primitives
    basic_fields = [
        'name', 'template_type', 'description', 'instructions', 
        'analysis_focus', 'icon_class', 'color_theme'
    ]
    
    for field in basic_fields:
        value = template_config.get(field)
        if value is not None:
            cloned_config[field] = value
            if audit_trail:
                audit_trail['fields_cloned'].append(field)
        else:
            # Use appropriate defaults
            if field in ['description', 'instructions', 'analysis_focus']:
                cloned_config[field] = ''
            elif field == 'icon_class':
                cloned_config[field] = 'fa-file-alt'
            elif field == 'color_theme':
                cloned_config[field] = 'oxford-blue'
            else:
                cloned_config[field] = ''
            
            if audit_trail:
                audit_trail['fields_with_defaults'].append(field)
                audit_trail['warnings'].append(f"Field {field} not in template, using default")
    
    # Collection fields that require deep copy
    collection_fields = {
        'suggested_questions': list,
        'required_fields': list,
        'navigation_pages': list,
        'processing_capabilities': dict,
        'validation_rules': dict,
        'ui_configuration': dict
    }
    
    for field, expected_type in collection_fields.items():
        value = template_config.get(field)
        if value is not None:
            # Validate type
            if not isinstance(value, expected_type):
                warning_msg = f"Field {field} has wrong type: expected {expected_type.__name__}, got {type(value).__name__}"
                logger.warning(warning_msg)
                if audit_trail:
                    audit_trail['warnings'].append(warning_msg)
            
            # Deep copy the collection
            cloned_config[field] = deep_clone_configuration_field(value)
            if audit_trail:
                audit_trail['fields_cloned'].append(field)
        else:
            # Use empty collection of appropriate type
            cloned_config[field] = expected_type()
            if audit_trail:
                audit_trail['fields_with_defaults'].append(field)
                audit_trail['warnings'].append(
                    f"Required field {field} missing, using empty {expected_type.__name__}"
                )
    
    # Boolean and integer fields
    boolean_fields = {
        'has_navigation': False,
        'total_pages': 1
    }
    
    for field, default_value in boolean_fields.items():
        value = template_config.get(field)
        if value is not None:
            cloned_config[field] = value
            if audit_trail:
                audit_trail['fields_cloned'].append(field)
        else:
            cloned_config[field] = default_value
            if audit_trail:
                audit_trail['fields_with_defaults'].append(field)
                audit_trail['warnings'].append(f"Field {field} not in template, using default: {default_value}")
    
    # Validate required fields
    missing_required = validate_template_config(template_config, template_metadata.get('template_id', 'unknown'))
    if missing_required and audit_trail:
        audit_trail['warnings'].extend([f"Missing required field: {field}" for field in missing_required])
    
    if audit_trail:
        audit_trail['duration_ms'] = (time.time() - start_time) * 1000
    
    return cloned_config, audit_trail

