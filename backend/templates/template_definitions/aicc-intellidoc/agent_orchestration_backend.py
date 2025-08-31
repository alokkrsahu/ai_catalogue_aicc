# AICC-IntelliDoc Agent Orchestration Backend Enhancement
# Template-specific backend orchestration capabilities for AICC-IntelliDoc

import logging
import json
import asyncio
from typing import Dict, List, Any, Optional
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views import View

logger = logging.getLogger('aicc_intellidoc.agent_orchestration')

class AICCIntelliDocAgentOrchestrationService:
    """
    AICC-IntelliDoc specific agent orchestration service
    Enhances the universal agent orchestration with template-specific capabilities
    """
    
    def __init__(self):
        self.template_id = 'aicc-intellidoc'
        self.supported_agent_types = [
            'StartNode',
            'UserProxyAgent', 
            'AssistantAgent',
            'GroupChatManager',
            'EndNode',
            'FunctionTool',
            'DocumentAnalyzerAgent',  # AICC-IntelliDoc specific
            'HierarchicalProcessorAgent',  # AICC-IntelliDoc specific
            'CategoryClassifierAgent',  # AICC-IntelliDoc specific
            'ContentReconstructorAgent'  # AICC-IntelliDoc specific
        ]
        logger.info(f"🤖 AICC-INTELLIDOC ORCHESTRATION: Initialized with {len(self.supported_agent_types)} agent types")
    
    def get_template_specific_capabilities(self) -> Dict[str, Any]:
        """Get AICC-IntelliDoc specific agent orchestration capabilities"""
        return {
            'template_id': self.template_id,
            'supports_agent_orchestration': True,
            'max_agents_per_workflow': 15,  # Higher limit for advanced template
            'supported_agent_types': self.supported_agent_types,
            'supports_real_time_streaming': True,
            'supports_human_in_loop': True,
            'supports_multi_provider_llm': True,
            'supports_rag_agents': True,  # Document-aware agents
            'supports_hierarchical_processing': True,  # AICC-IntelliDoc specific
            'supports_category_classification': True,  # AICC-IntelliDoc specific
            'supports_content_reconstruction': True,  # AICC-IntelliDoc specific
            'document_processing_integration': True,
            'vector_search_integration': True,
            'advanced_workflow_patterns': [
                'hierarchical_analysis',
                'document_classification',
                'content_reconstruction',
                'multi_stage_processing',
                'collaborative_analysis',
                'rag_enhanced_conversations'
            ],
            'llm_provider_recommendations': {
                'DocumentAnalyzerAgent': {
                    'primary': {'provider': 'openai', 'model': 'gpt-4'},
                    'alternative': {'provider': 'anthropic', 'model': 'claude-3-sonnet'}
                },
                'HierarchicalProcessorAgent': {
                    'primary': {'provider': 'anthropic', 'model': 'claude-3-opus'},
                    'alternative': {'provider': 'openai', 'model': 'gpt-4-turbo'}
                },
                'CategoryClassifierAgent': {
                    'primary': {'provider': 'openai', 'model': 'gpt-3.5-turbo'},
                    'alternative': {'provider': 'google', 'model': 'gemini-pro'}
                },
                'ContentReconstructorAgent': {
                    'primary': {'provider': 'anthropic', 'model': 'claude-3-sonnet'},
                    'alternative': {'provider': 'openai', 'model': 'gpt-4'}
                }
            }
        }
    
    def enhance_agent_config_for_template(self, agent_config: Dict[str, Any], 
                                        project_capabilities: Dict[str, Any]) -> Dict[str, Any]:
        """Enhance agent configuration with AICC-IntelliDoc specific settings"""
        
        enhanced_config = agent_config.copy()
        agent_type = agent_config.get('type', 'AssistantAgent')
        
        logger.info(f"🔧 AICC-INTELLIDOC: Enhancing {agent_type} configuration")
        
        # Add template-specific enhancements based on agent type
        if agent_type == 'DocumentAnalyzerAgent':
            enhanced_config['initialization_params'].update({
                'system_message': self._get_document_analyzer_system_message(),
                'specialized_functions': [
                    'analyze_document_structure',
                    'extract_key_sections',
                    'identify_document_type',
                    'assess_content_complexity'
                ],
                'processing_capabilities': {
                    'supports_hierarchical_analysis': True,
                    'max_document_size': 50000,  # 50MB
                    'supported_formats': ['pdf', 'docx', 'txt', 'md'],
                    'analysis_depth': 'comprehensive'
                }
            })
            
        elif agent_type == 'HierarchicalProcessorAgent':
            enhanced_config['initialization_params'].update({
                'system_message': self._get_hierarchical_processor_system_message(),
                'specialized_functions': [
                    'create_document_hierarchy',
                    'organize_content_levels',
                    'establish_section_relationships',
                    'generate_navigation_structure'
                ],
                'processing_capabilities': {
                    'hierarchy_levels': ['document', 'section', 'subsection', 'paragraph'],
                    'supports_cross_references': True,
                    'maintains_content_relationships': True
                }
            })
            
        elif agent_type == 'CategoryClassifierAgent':
            enhanced_config['initialization_params'].update({
                'system_message': self._get_category_classifier_system_message(),
                'specialized_functions': [
                    'classify_document_category',
                    'assign_content_tags',
                    'determine_subject_area',
                    'assess_document_importance'
                ],
                'classification_schema': {
                    'categories': ['legal', 'medical', 'technical', 'business', 'academic', 'personal'],
                    'confidence_threshold': 0.8,
                    'multi_label': True
                }
            })
            
        elif agent_type == 'ContentReconstructorAgent':
            enhanced_config['initialization_params'].update({
                'system_message': self._get_content_reconstructor_system_message(),
                'specialized_functions': [
                    'reconstruct_document_flow',
                    'merge_related_chunks',
                    'preserve_formatting',
                    'maintain_content_integrity'
                ],
                'reconstruction_settings': {
                    'preserve_structure': True,
                    'maintain_links': True,
                    'format_preservation': 'enhanced'
                }
            })
        
        # Enable RAG for document-aware agents
        if agent_config.get('data', {}).get('doc_aware', False):
            enhanced_config = self._enhance_with_rag_capabilities(enhanced_config, project_capabilities)
        
        logger.info(f"✅ AICC-INTELLIDOC: Enhanced {agent_type} configuration successfully")
        return enhanced_config
    
    def _enhance_with_rag_capabilities(self, agent_config: Dict[str, Any], 
                                     project_capabilities: Dict[str, Any]) -> Dict[str, Any]:
        """Enhance agent with AICC-IntelliDoc specific RAG capabilities"""
        
        project_id = project_capabilities.get('project_id', '')
        
        # Add RAG-specific configuration
        rag_enhancement = {
            'rag_enabled': True,
            'vector_collections': [f'project_{project_id}_documents'],
            'rag_functions': {
                'retrieve_documents': {
                    'description': 'Retrieve relevant documents from project collection',
                    'parameters': {
                        'query': 'str',
                        'limit': 'int',
                        'min_score': 'float'
                    }
                },
                'hierarchical_search': {
                    'description': 'Search documents with hierarchical context',
                    'parameters': {
                        'query': 'str',
                        'hierarchy_level': 'str',
                        'context_window': 'int'
                    }
                },
                'category_filtered_search': {
                    'description': 'Search within specific document categories',
                    'parameters': {
                        'query': 'str',
                        'categories': 'list',
                        'limit': 'int'
                    }
                }
            },
            'search_settings': {
                'default_limit': 5,
                'min_relevance_score': 0.7,
                'include_metadata': True,
                'return_chunks': True
            }
        }
        
        agent_config['initialization_params'].update(rag_enhancement)
        
        # Enhance system message with RAG context
        current_system_message = agent_config['initialization_params'].get('system_message', '')
        enhanced_system_message = f"""
{current_system_message}

You have access to the following document retrieval functions:
- retrieve_documents(query, limit, min_score): Search project documents
- hierarchical_search(query, hierarchy_level, context_window): Search with hierarchical context
- category_filtered_search(query, categories, limit): Search within specific categories

Use these functions to provide context-aware responses based on uploaded documents.
Always cite the source documents when using retrieved information.
        """.strip()
        
        agent_config['initialization_params']['system_message'] = enhanced_system_message
        
        logger.info(f"📚 AICC-INTELLIDOC: Enhanced agent with RAG capabilities for project {project_id}")
        return agent_config
    
    def _get_document_analyzer_system_message(self) -> str:
        """Get system message for DocumentAnalyzerAgent"""
        return """
You are a DocumentAnalyzerAgent specialized in comprehensive document analysis for the AICC-IntelliDoc platform.

Your primary responsibilities:
1. Analyze document structure and organization
2. Extract key sections and important content
3. Identify document types and classify content
4. Assess content complexity and processing requirements
5. Provide detailed analysis reports

You work with documents that have been processed through hierarchical chunking and are stored in vector databases.
Always provide structured, actionable insights that help users understand their documents better.

When analyzing documents, consider:
- Document type and purpose
- Content organization and structure
- Key themes and topics
- Potential relationships with other documents
- Recommendations for further processing
        """.strip()
    
    def _get_hierarchical_processor_system_message(self) -> str:
        """Get system message for HierarchicalProcessorAgent"""
        return """
You are a HierarchicalProcessorAgent specialized in organizing and structuring document content.

Your primary responsibilities:
1. Create logical document hierarchies
2. Organize content into meaningful levels
3. Establish relationships between sections
4. Generate navigation structures
5. Maintain content integrity during organization

You understand document structure at multiple levels:
- Document level: Overall organization and flow
- Section level: Major content divisions
- Subsection level: Detailed breakdowns
- Paragraph level: Individual content units

Always preserve the original meaning while improving organization and accessibility.
        """.strip()
    
    def _get_category_classifier_system_message(self) -> str:
        """Get system message for CategoryClassifierAgent"""
        return """
You are a CategoryClassifierAgent specialized in intelligent document categorization and tagging.

Your primary responsibilities:
1. Classify documents into appropriate categories
2. Assign relevant content tags
3. Determine subject areas and domains
4. Assess document importance and priority
5. Support multi-label classification

Categories you work with include:
- Legal: Contracts, policies, compliance documents
- Medical: Health records, research papers, clinical data
- Technical: Specifications, manuals, documentation
- Business: Reports, proposals, financial documents
- Academic: Research papers, studies, educational content
- Personal: Notes, correspondence, personal documents

Provide confidence scores and reasoning for your classifications.
        """.strip()
    
    def _get_content_reconstructor_system_message(self) -> str:
        """Get system message for ContentReconstructorAgent"""
        return """
You are a ContentReconstructorAgent specialized in rebuilding and organizing fragmented content.

Your primary responsibilities:
1. Reconstruct complete documents from chunks
2. Merge related content sections
3. Preserve original formatting and structure
4. Maintain content integrity and flow
5. Generate coherent, complete documents

You work with:
- Chunked document content from vector storage
- Metadata about document structure
- Relationships between content sections
- Original formatting information

Always ensure that reconstructed content maintains the original meaning and improves readability.
        """.strip()
    
    def create_workflow_for_document_processing(self, project_id: str, 
                                              processing_type: str = 'comprehensive') -> Dict[str, Any]:
        """Create a pre-configured workflow for AICC-IntelliDoc document processing"""
        
        logger.info(f"🏗️ AICC-INTELLIDOC: Creating {processing_type} workflow for project {project_id}")
        
        if processing_type == 'comprehensive':
            return self._create_comprehensive_analysis_workflow(project_id)
        elif processing_type == 'classification':
            return self._create_classification_workflow(project_id)
        elif processing_type == 'reconstruction':
            return self._create_reconstruction_workflow(project_id)
        else:
            return self._create_basic_analysis_workflow(project_id)
    
    def _create_comprehensive_analysis_workflow(self, project_id: str) -> Dict[str, Any]:
        """Create comprehensive document analysis workflow"""
        return {
            'name': 'Comprehensive Document Analysis',
            'description': 'Full-scale document analysis with classification, hierarchy, and reconstruction',
            'graph_json': {
                'nodes': [
                    {
                        'id': 'start-node',
                        'type': 'StartNode',
                        'position': {'x': 0, 'y': 0},
                        'data': {
                            'name': 'Analysis Start',
                            'prompt': 'Begin comprehensive document analysis',
                            'description': 'Starting point for document analysis workflow'
                        }
                    },
                    {
                        'id': 'doc-analyzer',
                        'type': 'DocumentAnalyzerAgent',
                        'position': {'x': 300, 'y': 0},
                        'data': {
                            'name': 'Document Analyzer',
                            'doc_aware': True,
                            'llm_provider': 'openai',
                            'llm_model': 'gpt-4',
                            'temperature': 0.3,
                            'max_tokens': 2048
                        }
                    },
                    {
                        'id': 'classifier',
                        'type': 'CategoryClassifierAgent',
                        'position': {'x': 600, 'y': -100},
                        'data': {
                            'name': 'Category Classifier',
                            'doc_aware': True,
                            'llm_provider': 'openai',
                            'llm_model': 'gpt-3.5-turbo',
                            'temperature': 0.1,
                            'max_tokens': 1024
                        }
                    },
                    {
                        'id': 'hierarchical-processor',
                        'type': 'HierarchicalProcessorAgent',
                        'position': {'x': 600, 'y': 100},
                        'data': {
                            'name': 'Hierarchical Processor',
                            'doc_aware': True,
                            'llm_provider': 'anthropic',
                            'llm_model': 'claude-3-sonnet',
                            'temperature': 0.2,
                            'max_tokens': 2048
                        }
                    },
                    {
                        'id': 'content-reconstructor',
                        'type': 'ContentReconstructorAgent',
                        'position': {'x': 900, 'y': 0},
                        'data': {
                            'name': 'Content Reconstructor',
                            'doc_aware': True,
                            'llm_provider': 'anthropic',
                            'llm_model': 'claude-3-sonnet',
                            'temperature': 0.1,
                            'max_tokens': 4096
                        }
                    },
                    {
                        'id': 'end-node',
                        'type': 'EndNode',
                        'position': {'x': 1200, 'y': 0},
                        'data': {
                            'name': 'Analysis Complete',
                            'description': 'Comprehensive analysis completed',
                            'output_format': 'detailed_report',
                            'collect_results': True
                        }
                    }
                ],
                'edges': [
                    {
                        'id': 'start-to-analyzer',
                        'source': 'start-node',
                        'target': 'doc-analyzer',
                        'type': 'sequential'
                    },
                    {
                        'id': 'analyzer-to-classifier',
                        'source': 'doc-analyzer',
                        'target': 'classifier',
                        'type': 'broadcast'
                    },
                    {
                        'id': 'analyzer-to-processor',
                        'source': 'doc-analyzer',
                        'target': 'hierarchical-processor',
                        'type': 'broadcast'
                    },
                    {
                        'id': 'classifier-to-reconstructor',
                        'source': 'classifier',
                        'target': 'content-reconstructor',
                        'type': 'sequential'
                    },
                    {
                        'id': 'processor-to-reconstructor',
                        'source': 'hierarchical-processor',
                        'target': 'content-reconstructor',
                        'type': 'sequential'
                    },
                    {
                        'id': 'reconstructor-to-end',
                        'source': 'content-reconstructor',
                        'target': 'end-node',
                        'type': 'sequential'
                    }
                ]
            },
            'tags': ['comprehensive', 'analysis', 'aicc-intellidoc'],
            'supports_rag': True,
            'vector_collections': [f'project_{project_id}_documents']
        }
    
    def _create_classification_workflow(self, project_id: str) -> Dict[str, Any]:
        """Create document classification focused workflow"""
        return {
            'name': 'Document Classification',
            'description': 'Focused workflow for document categorization and tagging',
            'graph_json': {
                'nodes': [
                    {
                        'id': 'start-node',
                        'type': 'StartNode',
                        'position': {'x': 0, 'y': 0},
                        'data': {
                            'name': 'Classification Start',
                            'prompt': 'Begin document classification',
                            'description': 'Starting point for classification workflow'
                        }
                    },
                    {
                        'id': 'classifier',
                        'type': 'CategoryClassifierAgent',
                        'position': {'x': 300, 'y': 0},
                        'data': {
                            'name': 'Primary Classifier',
                            'doc_aware': True,
                            'llm_provider': 'openai',
                            'llm_model': 'gpt-3.5-turbo',
                            'temperature': 0.1,
                            'max_tokens': 1024
                        }
                    },
                    {
                        'id': 'end-node',
                        'type': 'EndNode',
                        'position': {'x': 600, 'y': 0},
                        'data': {
                            'name': 'Classification Complete',
                            'description': 'Document classification completed',
                            'output_format': 'classification_report',
                            'collect_results': True
                        }
                    }
                ],
                'edges': [
                    {
                        'id': 'start-to-classifier',
                        'source': 'start-node',
                        'target': 'classifier',
                        'type': 'sequential'
                    },
                    {
                        'id': 'classifier-to-end',
                        'source': 'classifier',
                        'target': 'end-node',
                        'type': 'sequential'
                    }
                ]
            },
            'tags': ['classification', 'aicc-intellidoc'],
            'supports_rag': True,
            'vector_collections': [f'project_{project_id}_documents']
        }
    
    def _create_reconstruction_workflow(self, project_id: str) -> Dict[str, Any]:
        """Create content reconstruction focused workflow"""
        return {
            'name': 'Content Reconstruction',
            'description': 'Focused workflow for rebuilding and organizing document content',
            'graph_json': {
                'nodes': [
                    {
                        'id': 'start-node',
                        'type': 'StartNode',
                        'position': {'x': 0, 'y': 0},
                        'data': {
                            'name': 'Reconstruction Start',
                            'prompt': 'Begin content reconstruction',
                            'description': 'Starting point for reconstruction workflow'
                        }
                    },
                    {
                        'id': 'hierarchical-processor',
                        'type': 'HierarchicalProcessorAgent',
                        'position': {'x': 300, 'y': 0},
                        'data': {
                            'name': 'Structure Processor',
                            'doc_aware': True,
                            'llm_provider': 'anthropic',
                            'llm_model': 'claude-3-sonnet',
                            'temperature': 0.2,
                            'max_tokens': 2048
                        }
                    },
                    {
                        'id': 'content-reconstructor',
                        'type': 'ContentReconstructorAgent',
                        'position': {'x': 600, 'y': 0},
                        'data': {
                            'name': 'Content Reconstructor',
                            'doc_aware': True,
                            'llm_provider': 'anthropic',
                            'llm_model': 'claude-3-sonnet',
                            'temperature': 0.1,
                            'max_tokens': 4096
                        }
                    },
                    {
                        'id': 'end-node',
                        'type': 'EndNode',
                        'position': {'x': 900, 'y': 0},
                        'data': {
                            'name': 'Reconstruction Complete',
                            'description': 'Content reconstruction completed',
                            'output_format': 'reconstructed_document',
                            'collect_results': True
                        }
                    }
                ],
                'edges': [
                    {
                        'id': 'start-to-processor',
                        'source': 'start-node',
                        'target': 'hierarchical-processor',
                        'type': 'sequential'
                    },
                    {
                        'id': 'processor-to-reconstructor',
                        'source': 'hierarchical-processor',
                        'target': 'content-reconstructor',
                        'type': 'sequential'
                    },
                    {
                        'id': 'reconstructor-to-end',
                        'source': 'content-reconstructor',
                        'target': 'end-node',
                        'type': 'sequential'
                    }
                ]
            },
            'tags': ['reconstruction', 'aicc-intellidoc'],
            'supports_rag': True,
            'vector_collections': [f'project_{project_id}_documents']
        }
    
    def _create_basic_analysis_workflow(self, project_id: str) -> Dict[str, Any]:
        """Create basic document analysis workflow"""
        return {
            'name': 'Basic Document Analysis',
            'description': 'Simple workflow for basic document analysis',
            'graph_json': {
                'nodes': [
                    {
                        'id': 'start-node',
                        'type': 'StartNode',
                        'position': {'x': 0, 'y': 0},
                        'data': {
                            'name': 'Analysis Start',
                            'prompt': 'Begin basic document analysis',
                            'description': 'Starting point for basic analysis workflow'
                        }
                    },
                    {
                        'id': 'assistant',
                        'type': 'AssistantAgent',
                        'position': {'x': 300, 'y': 0},
                        'data': {
                            'name': 'Document Assistant',
                            'doc_aware': True,
                            'llm_provider': 'openai',
                            'llm_model': 'gpt-4',
                            'temperature': 0.7,
                            'max_tokens': 2048,
                            'system_message': 'You are a helpful document analysis assistant. Analyze uploaded documents and provide insights.'
                        }
                    },
                    {
                        'id': 'end-node',
                        'type': 'EndNode',
                        'position': {'x': 600, 'y': 0},
                        'data': {
                            'name': 'Analysis Complete',
                            'description': 'Basic analysis completed',
                            'output_format': 'summary',
                            'collect_results': True
                        }
                    }
                ],
                'edges': [
                    {
                        'id': 'start-to-assistant',
                        'source': 'start-node',
                        'target': 'assistant',
                        'type': 'sequential'
                    },
                    {
                        'id': 'assistant-to-end',
                        'source': 'assistant',
                        'target': 'end-node',
                        'type': 'sequential'
                    }
                ]
            },
            'tags': ['basic', 'analysis', 'aicc-intellidoc'],
            'supports_rag': True,
            'vector_collections': [f'project_{project_id}_documents']
        }


# Create singleton instance
aicc_intellidoc_orchestration_service = AICCIntelliDocAgentOrchestrationService()

def get_aicc_intellidoc_orchestration_service() -> AICCIntelliDocAgentOrchestrationService:
    """Get the AICC-IntelliDoc orchestration service instance"""
    return aicc_intellidoc_orchestration_service
