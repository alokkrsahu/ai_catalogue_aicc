# Enhanced Milvus Vector Database - Full AI Implementation Only
try:
    from pymilvus import connections, Collection, FieldSchema, CollectionSchema, DataType, utility
    MILVUS_AVAILABLE = True
    print("✅ Using enhanced Milvus with full AI capabilities")
except ImportError:
    MILVUS_AVAILABLE = False
    print("❌ pymilvus not available - Enhanced mode requires Milvus")
    raise ImportError("Enhanced processing requires pymilvus - install with: pip install pymilvus")

from typing import List, Dict, Optional, Any
import numpy as np
import logging
from django.conf import settings
import uuid
from .detailed_logger import DocumentProcessingTracker, doc_logger, log_data_state, log_vector_insertion_attempt

logger = logging.getLogger(__name__)

# Enhanced database factory function
def create_project_vector_database(project_id: str):
    """Factory function to create enhanced Milvus database - no fallbacks"""
    if not MILVUS_AVAILABLE:
        raise ImportError("Enhanced processing requires pymilvus - install with: pip install pymilvus")
    
    logger.info(f"🚀 Creating ENHANCED Milvus database for project {project_id}")
    database = MilvusProjectVectorDatabase(project_id)
    logger.info(f"✅ Successfully created ENHANCED Milvus database for project {project_id}")
    logger.info(f"📊 Full AI field support: ALL metadata fields will be stored (including AI-generated content)")
    return database

if not MILVUS_AVAILABLE:
    raise ImportError("Enhanced processing requires pymilvus - install with: pip install pymilvus")

class MilvusProjectVectorDatabase:
    """Enhanced vector database for projects using Milvus with full AI capabilities"""
    
    def __init__(self, project_id: str):
        self.project_id = project_id
        self.collection_name = self._generate_collection_name(project_id)
        self.vector_dim = 384  # all-MiniLM-L6-v2 dimension
        self._connect_to_milvus()
        self._setup_collection()
    
    def _generate_collection_name(self, project_id: str) -> str:
        """Generate collection name using project name instead of generic 'project' prefix"""
        try:
            # Import here to avoid circular imports
            from users.models import IntelliDocProject
            import re
            
            # Get project and use its name to generate collection name
            project = IntelliDocProject.objects.get(project_id=project_id)
            
            # Sanitize project name for Milvus compatibility
            # Milvus collection names can only contain numbers, letters and underscores
            sanitized_name = re.sub(r'[^a-zA-Z0-9_]', '', project.name.lower())
            
            # Ensure name is not empty and starts with a letter or underscore
            if not sanitized_name or sanitized_name[0].isdigit():
                sanitized_name = f"project_{sanitized_name}"
            
            # Limit length to reasonable size (Milvus has limits)
            if len(sanitized_name) > 20:
                sanitized_name = sanitized_name[:20]
            
            # Append project ID to ensure uniqueness
            collection_name = f"{sanitized_name}_{project_id.replace('-', '_')}"
            
            logger.info(f"Generated collection name: {collection_name} for project '{project.name}'")
            return collection_name
            
        except Exception as e:
            logger.warning(f"Failed to get project name for {project_id}: {e}")
            logger.warning(f"Falling back to generic collection name")
            # Fallback to original pattern if project lookup fails
            return f"project_{project_id.replace('-', '_')}"
    
    def _connect_to_milvus(self):
        """Connect to Milvus database with robust connection handling"""
        try:
            # Get Milvus connection settings from Django settings
            milvus_host = getattr(settings, 'MILVUS_HOST', 'localhost')
            milvus_port = getattr(settings, 'MILVUS_PORT', '19530')
            milvus_user = getattr(settings, 'MILVUS_USER', None)
            milvus_password = getattr(settings, 'MILVUS_PASSWORD', None)
            
            logger.info(f"🔄 Attempting to connect to Milvus at {milvus_host}:{milvus_port} with authentication: {'enabled' if milvus_user else 'disabled'}")
            
            # Use a global connection name to avoid conflicts
            connection_alias = "default"
            self.connection_alias = connection_alias
            
            try:
                # Check if connection already exists and is working
                from pymilvus import connections
                if connection_alias in connections.list_connections():
                    logger.debug(f"Using existing Milvus connection: {connection_alias}")
                    # Test the connection
                    collections_list = utility.list_collections(using=connection_alias)
                    logger.info(f"✅ Existing connection verified. Found {len(collections_list)} collections.")
                    return
                
            except Exception as test_error:
                logger.debug(f"Existing connection test failed: {test_error}")
                # Try to disconnect and reconnect
                try:
                    connections.disconnect(connection_alias)
                except:
                    pass
            
            # Create new connection with proper error handling and authentication
            connection_params = {
                'alias': connection_alias,
                'host': milvus_host,
                'port': milvus_port,
                'timeout': 10  # Reduced timeout for faster failure detection
            }
            
            # Add authentication if credentials are provided
            if milvus_user and milvus_password:
                connection_params['user'] = milvus_user
                connection_params['password'] = milvus_password
                logger.info(f"🔐 Using authenticated connection with user: {milvus_user}")
            
            connections.connect(**connection_params)
            
            logger.info(f"✅ Connected to Milvus at {milvus_host}:{milvus_port}")
            
            # Test the connection with actual operation
            try:
                collections_list = utility.list_collections(using=connection_alias)
                logger.info(f"✅ Connection verified. Found {len(collections_list)} collections.")
                logger.info(f"📊 Using ENHANCED Milvus implementation with {len(collections_list)} existing collections")
            except Exception as test_error:
                logger.error(f"Connection test failed: {test_error}")
                raise ConnectionError(f"Connection test failed: {test_error}")
                
        except Exception as e:
            logger.error(f"❌ Failed to connect to Milvus: {e}")
            logger.error(f"💡 Suggestion: Make sure Milvus is running: docker-compose -f docker-compose-milvus.yml up -d")
            logger.error(f"🔄 Enhanced mode requires Milvus - no fallbacks available")
            raise ConnectionError(f"Milvus connection failed: {e}")
    
    def _setup_collection(self):
        """Setup Milvus collection with necessary fields for this project"""
        try:
            fields = [
                FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
                FieldSchema(name="document_id", dtype=DataType.VARCHAR, max_length=100),
                FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.vector_dim),
                FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=65535),
                FieldSchema(name="file_name", dtype=DataType.VARCHAR, max_length=255),
                FieldSchema(name="file_type", dtype=DataType.VARCHAR, max_length=100),
                FieldSchema(name="file_size", dtype=DataType.INT64),
                FieldSchema(name="content_length", dtype=DataType.INT64),
                FieldSchema(name="uploaded_at", dtype=DataType.VARCHAR, max_length=50),
                
                # Hierarchical metadata fields
                FieldSchema(name="category", dtype=DataType.VARCHAR, max_length=50),
                FieldSchema(name="subcategory", dtype=DataType.VARCHAR, max_length=50),
                FieldSchema(name="document_type", dtype=DataType.VARCHAR, max_length=50),
                FieldSchema(name="virtual_path", dtype=DataType.VARCHAR, max_length=500),
                FieldSchema(name="hierarchical_path", dtype=DataType.VARCHAR, max_length=500),
                FieldSchema(name="hierarchy_level", dtype=DataType.INT64),
                FieldSchema(name="organization_level", dtype=DataType.VARCHAR, max_length=50),
                
                # Chunk-specific fields
                FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, max_length=100),
                FieldSchema(name="chunk_index", dtype=DataType.INT64),
                FieldSchema(name="total_chunks", dtype=DataType.INT64),
                FieldSchema(name="chunk_type", dtype=DataType.VARCHAR, max_length=50),
                FieldSchema(name="section_title", dtype=DataType.VARCHAR, max_length=200),
                FieldSchema(name="is_complete_document", dtype=DataType.BOOL),
                
                # AI-Generated Content Fields (Summary and Topic)
                FieldSchema(name="summary", dtype=DataType.VARCHAR, max_length=2000),
                FieldSchema(name="summary_word_count", dtype=DataType.INT64),
                FieldSchema(name="summary_generated_at", dtype=DataType.VARCHAR, max_length=50),
                FieldSchema(name="summarizer_used", dtype=DataType.VARCHAR, max_length=50),
                FieldSchema(name="topic", dtype=DataType.VARCHAR, max_length=500),
                FieldSchema(name="topic_word_count", dtype=DataType.INT64),
                FieldSchema(name="topic_generated_at", dtype=DataType.VARCHAR, max_length=50),
                FieldSchema(name="topic_generator_used", dtype=DataType.VARCHAR, max_length=50),
                
                # Processing Metadata Fields
                FieldSchema(name="vector_id", dtype=DataType.VARCHAR, max_length=100),
                FieldSchema(name="has_embedding", dtype=DataType.BOOL),
                FieldSchema(name="processing_time_ms", dtype=DataType.INT64),
                FieldSchema(name="error_message", dtype=DataType.VARCHAR, max_length=1000)
            ]
            
            schema = CollectionSchema(fields=fields, description=f"Enhanced document vectors for project {self.project_id}")
            
            # Create collection if it doesn't exist
            if not utility.has_collection(self.collection_name, using=self.connection_alias):
                self.collection = Collection(name=self.collection_name, schema=schema, using=self.connection_alias)
                logger.info(f"Created new enhanced collection: {self.collection_name}")
                
                # Create vector index
                self._create_indices()
            else:
                self.collection = Collection(self.collection_name, using=self.connection_alias)
                logger.info(f"Using existing enhanced collection: {self.collection_name}")
            
            # Load collection for search with proper error handling
            try:
                self.collection.load()
                logger.info(f"Successfully loaded enhanced collection: {self.collection_name}")
            except Exception as load_error:
                logger.warning(f"Failed to load collection {self.collection_name}: {load_error}")
                # Try to create a new collection if loading fails
                self.collection.drop()
                self.collection = Collection(name=self.collection_name, schema=schema, using=self.connection_alias)
                self._create_indices()
                self.collection.load()
                logger.info(f"Recreated and loaded enhanced collection: {self.collection_name}")
            
        except Exception as e:
            logger.error(f"Failed to setup enhanced collection {self.collection_name}: {e}")
            raise
    
    def _create_indices(self):
        """Create indices for efficient search"""
        try:
            # Create vector index
            index_params = {
                "metric_type": "IP",  # Inner Product for normalized vectors
                "index_type": "IVF_FLAT",
                "params": {"nlist": 1024}
            }
            
            self.collection.create_index(
                field_name="embedding",
                index_params=index_params,
                timeout=None
            )
            
            # Create scalar field indices for filtering
            self.collection.create_index(field_name="document_id")
            self.collection.create_index(field_name="file_type")
            self.collection.create_index(field_name="file_name")
            
            # Create indices for hierarchical fields
            self.collection.create_index(field_name="category")
            self.collection.create_index(field_name="subcategory")
            self.collection.create_index(field_name="document_type")
            self.collection.create_index(field_name="hierarchy_level")
            self.collection.create_index(field_name="organization_level")
            
            # Create indices for chunk fields
            self.collection.create_index(field_name="chunk_type")
            self.collection.create_index(field_name="chunk_index")
            
            logger.info(f"Created enhanced indices for collection {self.collection_name}")
            
        except Exception as e:
            logger.error(f"Failed to create indices for {self.collection_name}: {e}")
            raise
    
    def batch_insert_document_chunks(self, chunks_data: List[Any], document_name: str) -> bool:
        """Atomically insert all chunks for a document using batch insertion"""
        try:
            logger.info(f"📦 Starting ATOMIC batch insertion for {document_name} - {len(chunks_data)} chunks")
            
            if not chunks_data:
                logger.error(f"No chunks provided for {document_name}")
                return False
            
            # Prepare batch data for all chunks
            batch_entities = self._prepare_batch_entities(chunks_data, document_name)
            
            if not batch_entities:
                logger.error(f"Failed to prepare batch entities for {document_name}")
                return False
            
            # CRITICAL: Ensure collection exists and is loaded before batch insertion
            try:
                if not hasattr(self, 'collection') or self.collection is None:
                    logger.warning(f"Collection not initialized, reinitializing for {document_name}")
                    self._setup_collection()
                
                # Verify collection is loaded - use utility method instead of is_loaded attribute
                try:
                    # Try to get collection info to verify it's loaded
                    self.collection.num_entities
                except Exception as load_check:
                    logger.warning(f"Collection not loaded, loading for {document_name}: {load_check}")
                    self.collection.load()
                    
                # Double check the collection exists
                if not utility.has_collection(self.collection_name, using=self.connection_alias):
                    logger.error(f"Collection {self.collection_name} does not exist before batch insertion")
                    return False
                    
            except Exception as collection_error:
                logger.error(f"Collection setup failed for {document_name}: {collection_error}")
                return False
            
            # Single atomic batch insertion
            insert_result = self.collection.insert(batch_entities)
            
            # Single flush operation
            self.collection.flush()
            
            logger.info(f"✅ ATOMIC batch insertion successful for {document_name} - {len(chunks_data)} chunks stored")
            return True
            
        except Exception as e:
            logger.error(f"❌ ATOMIC batch insertion failed for {document_name}: {e}")
            return False
    
    def _prepare_batch_entities(self, chunks_data: List[Any], document_name: str) -> Optional[List]:
        """Prepare batch entities for Milvus insertion"""
        try:
            # Initialize entity arrays for all fields
            batch_entities = [
                [],  # document_id
                [],  # embedding
                [],  # content
                [],  # file_name
                [],  # file_type
                [],  # file_size
                [],  # content_length
                [],  # uploaded_at
                [],  # category
                [],  # subcategory
                [],  # document_type
                [],  # virtual_path
                [],  # hierarchical_path
                [],  # hierarchy_level
                [],  # organization_level
                [],  # chunk_id
                [],  # chunk_index
                [],  # total_chunks
                [],  # chunk_type
                [],  # section_title
                [],  # is_complete_document
                [],  # summary
                [],  # summary_word_count
                [],  # summary_generated_at
                [],  # summarizer_used
                [],  # topic
                [],  # topic_word_count
                [],  # topic_generated_at
                [],  # topic_generator_used
                [],  # vector_id
                [],  # has_embedding
                [],  # processing_time_ms
                []   # error_message
            ]
            
            # Helper functions for safe conversion
            def safe_str(value, default=''):
                return str(value) if value is not None else default
            
            def safe_int(value, default=0):
                if value is None:
                    return default
                try:
                    return int(value)
                except (ValueError, TypeError):
                    return default
            
            def safe_bool(value, default=True):
                if value is None:
                    return default
                return bool(value)
            
            # Process each chunk and add to batch
            for chunk_data in chunks_data:
                # Validate chunk data
                if not hasattr(chunk_data, 'embedding') or chunk_data.embedding is None:
                    logger.error(f"No embedding found for chunk in {document_name}")
                    return None
                
                if not hasattr(chunk_data, 'content') or not chunk_data.content:
                    logger.error(f"No content found for chunk in {document_name}")
                    return None
                
                # Extract metadata
                metadata = chunk_data.metadata
                content = str(chunk_data.content)[:60000]  # Safe truncation
                
                # Add chunk data to batch arrays
                batch_entities[0].append(safe_str(metadata.get('document_id')))
                batch_entities[1].append(chunk_data.embedding.tolist())
                batch_entities[2].append(content)
                batch_entities[3].append(safe_str(metadata.get('file_name')))
                batch_entities[4].append(safe_str(metadata.get('file_type')))
                batch_entities[5].append(safe_int(metadata.get('file_size')))
                batch_entities[6].append(len(content))
                batch_entities[7].append(safe_str(metadata.get('uploaded_at')))
                
                # Hierarchical metadata
                batch_entities[8].append(safe_str(metadata.get('category'), 'general'))
                batch_entities[9].append(safe_str(metadata.get('subcategory')))
                batch_entities[10].append(safe_str(metadata.get('document_type'), 'document'))
                batch_entities[11].append(safe_str(metadata.get('virtual_path')))
                batch_entities[12].append(safe_str(metadata.get('hierarchical_path')))
                batch_entities[13].append(safe_int(metadata.get('hierarchy_level')))
                batch_entities[14].append(safe_str(metadata.get('organization_level'), 'hierarchical'))
                
                # Chunk metadata
                batch_entities[15].append(safe_str(metadata.get('chunk_id')))
                batch_entities[16].append(safe_int(metadata.get('chunk_index')))
                batch_entities[17].append(safe_int(metadata.get('total_chunks'), 1))
                batch_entities[18].append(safe_str(metadata.get('chunk_type'), 'complete_document'))
                batch_entities[19].append(safe_str(metadata.get('section_title')))
                batch_entities[20].append(safe_bool(metadata.get('is_complete_document')))
                
                # AI-Generated Content Fields
                batch_entities[21].append(safe_str(metadata.get('summary')))
                batch_entities[22].append(safe_int(metadata.get('summary_word_count')))
                batch_entities[23].append(safe_str(metadata.get('summary_generated_at')))
                batch_entities[24].append(safe_str(metadata.get('summarizer_used'), 'enhanced_ai'))
                batch_entities[25].append(safe_str(metadata.get('topic')))
                batch_entities[26].append(safe_int(metadata.get('topic_word_count')))
                batch_entities[27].append(safe_str(metadata.get('topic_generated_at')))
                batch_entities[28].append(safe_str(metadata.get('topic_generator_used'), 'enhanced_ai'))
                
                # Processing Metadata Fields
                batch_entities[29].append(safe_str(metadata.get('vector_id')))
                batch_entities[30].append(safe_bool(metadata.get('has_embedding')))
                batch_entities[31].append(safe_int(metadata.get('processing_time_ms')))
                batch_entities[32].append(safe_str(metadata.get('error_message')))
            
            logger.info(f"📦 Prepared batch entities for {document_name}: {len(chunks_data)} chunks")
            return batch_entities
            
        except Exception as e:
            logger.error(f"❌ Failed to prepare batch entities for {document_name}: {e}")
            return None
    
    def insert_document(self, doc_info) -> bool:
        """Insert single document into the enhanced vector database (Legacy method - use batch_insert_document_chunks instead)"""
        try:
            # Get basic info for logging
            file_name = doc_info.metadata.get('file_name', 'unknown') if hasattr(doc_info, 'metadata') else 'unknown'
            document_id = doc_info.metadata.get('document_id', 'unknown') if hasattr(doc_info, 'metadata') else 'unknown'
            
            logger.info(f"🚀 Enhanced insertion starting for {file_name}")
            
            # Validate required fields
            if not hasattr(doc_info, 'embedding') or doc_info.embedding is None:
                logger.error(f"No embedding found for document {file_name}")
                return False
            
            if not hasattr(doc_info, 'content') or not doc_info.content:
                logger.error(f"No content found for document {file_name}")
                return False
            
            # Prepare data for insertion with enhanced metadata
            content = str(doc_info.content)[:60000]  # Safe truncation
            
            # Extract all metadata with safe defaults to handle None values
            metadata = doc_info.metadata
            
            # Helper function to safely convert None to empty string
            def safe_str(value, default=''):
                return str(value) if value is not None else default
            
            def safe_int(value, default=0):
                if value is None:
                    return default
                try:
                    return int(value)
                except (ValueError, TypeError):
                    return default
            
            def safe_bool(value, default=True):
                if value is None:
                    return default
                return bool(value)
            
            entities = [
                [safe_str(metadata.get('document_id'))],
                [doc_info.embedding.tolist()],
                [content],
                [safe_str(metadata.get('file_name'))],
                [safe_str(metadata.get('file_type'))],
                [safe_int(metadata.get('file_size'))],
                [len(content)],
                [safe_str(metadata.get('uploaded_at'))],
                
                # Hierarchical metadata - safely handle None values
                [safe_str(metadata.get('category'), 'general')],
                [safe_str(metadata.get('subcategory'))],  # This was the problem - None instead of ''
                [safe_str(metadata.get('document_type'), 'document')],
                [safe_str(metadata.get('virtual_path'))],
                [safe_str(metadata.get('hierarchical_path'))],
                [safe_int(metadata.get('hierarchy_level'))],
                [safe_str(metadata.get('organization_level'), 'hierarchical')],
                
                # Chunk metadata
                [safe_str(metadata.get('chunk_id'))],
                [safe_int(metadata.get('chunk_index'))],
                [safe_int(metadata.get('total_chunks'), 1)],
                [safe_str(metadata.get('chunk_type'), 'complete_document')],
                [safe_str(metadata.get('section_title'))],
                [safe_bool(metadata.get('is_complete_document'))],
                
                # AI-Generated Content Fields
                [safe_str(metadata.get('summary'))],
                [safe_int(metadata.get('summary_word_count'))],
                [safe_str(metadata.get('summary_generated_at'))],
                [safe_str(metadata.get('summarizer_used'), 'enhanced_ai')],
                [safe_str(metadata.get('topic'))],
                [safe_int(metadata.get('topic_word_count'))],
                [safe_str(metadata.get('topic_generated_at'))],
                [safe_str(metadata.get('topic_generator_used'), 'enhanced_ai')],
                
                # Processing Metadata Fields
                [safe_str(metadata.get('vector_id'))],
                [safe_bool(metadata.get('has_embedding'))],
                [safe_int(metadata.get('processing_time_ms'))],
                [safe_str(metadata.get('error_message'))]
            ]
            
            # CRITICAL: Ensure collection exists and is loaded before insertion
            try:
                if not hasattr(self, 'collection') or self.collection is None:
                    logger.warning(f"Collection not initialized, reinitializing for {file_name}")
                    self._setup_collection()
                
                # Verify collection is loaded - use utility method instead of is_loaded attribute
                try:
                    # Try to get collection info to verify it's loaded
                    self.collection.num_entities
                except Exception as load_check:
                    logger.warning(f"Collection not loaded, loading for {file_name}: {load_check}")
                    self.collection.load()
                    
                # Double check the collection exists
                if not utility.has_collection(self.collection_name, using=self.connection_alias):
                    logger.error(f"Collection {self.collection_name} does not exist before insertion")
                    return False
                    
            except Exception as collection_error:
                logger.error(f"Collection setup failed for {file_name}: {collection_error}")
                return False
            
            # Insert into Milvus
            insert_result = self.collection.insert(entities)
            self.collection.flush()
            
            logger.info(f"✅ Enhanced insertion successful for {file_name}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Enhanced insertion failed for {file_name}: {e}")
            return False
    
    def search_documents(self, query_vector: np.ndarray, limit: int = 5, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Search documents in the enhanced vector database"""
        try:
            # Build filter expression
            expr = self._build_filter_expression(filters) if filters else None
            
            # Perform search
            search_params = {
                "metric_type": "IP",
                "params": {"nprobe": 10}
            }
            
            results = self.collection.search(
                data=[query_vector.tolist()],
                anns_field="embedding",
                param=search_params,
                expr=expr,
                limit=limit,
                output_fields=[
                    "document_id", "content", "file_name", "file_type", "file_size", "uploaded_at",
                    "category", "subcategory", "document_type", "virtual_path", "hierarchical_path",
                    "hierarchy_level", "organization_level", "chunk_id", "chunk_index", "total_chunks",
                    "chunk_type", "section_title", "is_complete_document",
                    "summary", "summary_word_count", "summary_generated_at", "summarizer_used",
                    "topic", "topic_word_count", "topic_generated_at", "topic_generator_used",
                    "vector_id", "has_embedding", "processing_time_ms", "error_message"
                ]
            )
            
            # Format results
            formatted_results = []
            for hit in results[0]:
                formatted_results.append({
                    # All enhanced fields
                    "document_id": hit.entity.get('document_id'),
                    "content": hit.entity.get('content'),
                    "file_name": hit.entity.get('file_name'),
                    "file_type": hit.entity.get('file_type'),
                    "file_size": hit.entity.get('file_size'),
                    "uploaded_at": hit.entity.get('uploaded_at'),
                    "category": hit.entity.get('category'),
                    "subcategory": hit.entity.get('subcategory'),
                    "summary": hit.entity.get('summary'),
                    "topic": hit.entity.get('topic'),
                    "similarity": float(hit.score)
                })
            
            logger.info(f"Enhanced search found {len(formatted_results)} results in {self.collection_name}")
            return formatted_results
            
        except Exception as e:
            logger.error(f"Enhanced search failed in {self.collection_name}: {e}")
            return []
    
    def _build_filter_expression(self, filters: Dict[str, Any]) -> str:
        """Build Milvus filter expression from filter dict"""
        if not filters:
            return None
            
        expressions = []
        
        for field, condition in filters.items():
            if isinstance(condition, dict):
                # Handle complex conditions
                for op, value in condition.items():
                    if op == '$eq':
                        if isinstance(value, str):
                            expressions.append(f'{field} == "{value}"')
                        else:
                            expressions.append(f'{field} == {value}')
                    elif op == '$ne':
                        if isinstance(value, str):
                            expressions.append(f'{field} != "{value}"')
                        else:
                            expressions.append(f'{field} != {value}')
                    elif op == '$in':
                        if isinstance(value, (list, tuple)):
                            if all(isinstance(v, str) for v in value):
                                value_str = '", "'.join(value)
                                expressions.append(f'{field} in ["{value_str}"]')
                            else:
                                value_str = ', '.join(str(v) for v in value)
                                expressions.append(f'{field} in [{value_str}]')
            else:
                # Handle simple equality
                if isinstance(condition, str):
                    expressions.append(f'{field} == "{condition}"')
                else:
                    expressions.append(f'{field} == {condition}')
                    
        return " && ".join(expressions) if expressions else None
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """Get statistics about the enhanced collection"""
        try:
            stats = self.collection.num_entities
            return {
                "collection_name": self.collection_name,
                "total_documents": stats,
                "project_id": self.project_id,
                "storage_type": "Enhanced Milvus Vector Database with Full AI"
            }
        except Exception as e:
            logger.error(f"Failed to get enhanced stats for {self.collection_name}: {e}")
            return {
                "collection_name": self.collection_name,
                "total_documents": 0,
                "project_id": self.project_id,
                "error": str(e)
            }
    
    def delete_collection(self):
        """Delete the entire collection for this project"""
        try:
            if utility.has_collection(self.collection_name):
                utility.drop_collection(self.collection_name)
                logger.info(f"Deleted enhanced collection {self.collection_name}")
                return True
        except Exception as e:
            logger.error(f"Failed to delete enhanced collection {self.collection_name}: {e}")
            return False
    
    def delete_document(self, document_id: str) -> bool:
        """Delete a specific document from the enhanced collection"""
        try:
            expr = f'document_id == "{document_id}"'
            self.collection.delete(expr)
            self.collection.flush()
            logger.info(f"Deleted document {document_id} from enhanced collection {self.collection_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete document {document_id} from enhanced collection {self.collection_name}: {e}")
            return False

# Compatibility alias for backwards compatibility
ProjectVectorDatabase = create_project_vector_database
