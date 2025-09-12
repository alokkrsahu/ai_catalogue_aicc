"""
Isolated ChromaDB Service for Public Chatbot
ZERO impact on existing Milvus/AI Catalogue system
Enhanced with intelligent chunking and large text support
"""
import logging
import threading
from typing import List, Dict, Any, Optional
from datetime import datetime
import os

# ChromaDB imports (isolated dependency)
try:
    import chromadb
    from chromadb.config import Settings
    from chromadb.utils import embedding_functions
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False

# Only import sentence-transformers if available (your system already has it)
try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False

# Import our advanced chunking and embedding systems
try:
    from .chunking import AdvancedTextChunker, ChunkStrategy, DocumentChunk
    from .embedding_strategies import LargeChunkEmbedder, EmbeddingStrategy
    ADVANCED_FEATURES_AVAILABLE = True
except ImportError:
    ADVANCED_FEATURES_AVAILABLE = False

logger = logging.getLogger('public_chatbot')


class PublicKnowledgeService:
    """
    Completely isolated ChromaDB service for public chatbot
    No integration with existing Milvus system
    """
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
            
        self.client = None
        self.collection = None
        self.embedding_function = None
        self.is_ready = False
        self._initialized = True
        
        # Initialize advanced chunking and embedding (if available)
        self.chunker = None
        self.large_embedder = None
        self.use_advanced_features = ADVANCED_FEATURES_AVAILABLE
        self._initialize_advanced_features()
        
        # Initialize ChromaDB
        self._initialize_chromadb()
    
    @classmethod
    def get_instance(cls):
        """Get singleton instance"""
        return cls()
    
    def _initialize_advanced_features(self):
        """Initialize advanced chunking and embedding features"""
        try:
            if not ADVANCED_FEATURES_AVAILABLE:
                logger.info("🧩 ADVANCED: Advanced features not available, using basic mode")
                return
            
            # Initialize text chunker with large chunk strategy
            chunk_strategy = ChunkStrategy.LARGE_SEMANTIC  # 2048 tokens with overlap
            self.chunker = AdvancedTextChunker(strategy=chunk_strategy)
            
            # Initialize large chunk embedder with enhanced model
            embedding_strategy = EmbeddingStrategy.SLIDING_WINDOW  # Best for large chunks
            self.large_embedder = LargeChunkEmbedder(
                strategy=embedding_strategy,
                use_enhanced_model=True  # Upgrade to better model if available
            )
            
            logger.info(f"🧩 ADVANCED: Initialized with {chunk_strategy.value} chunking and {embedding_strategy.value} embedding")
            logger.info(f"🧩 ADVANCED: Model info - {self.large_embedder.get_model_info()}")
            
        except Exception as e:
            logger.warning(f"🧩 ADVANCED: Could not initialize advanced features: {e}")
            self.use_advanced_features = False
    
    def _initialize_chromadb(self):
        """Initialize ChromaDB connection (isolated from main system)"""
        try:
            if not CHROMADB_AVAILABLE:
                logger.error("ChromaDB not available. Install with: pip install chromadb")
                return
            
            # ChromaDB connection settings (Docker container)
            chroma_host = os.getenv('CHROMADB_HOST', 'localhost')
            chroma_port = os.getenv('CHROMADB_PORT', '8000')  # ChromaDB container port
            
            logger.info(f"🔗 CHROMA: Connecting to ChromaDB at {chroma_host}:{chroma_port}")
            
            # Initialize ChromaDB client (isolated)
            self.client = chromadb.HttpClient(
                host=chroma_host,
                port=int(chroma_port),
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=False  # Security: prevent reset from API
                )
            )
            
            # Test connection
            try:
                collections = self.client.list_collections()
                logger.info(f"✅ CHROMA: Connected successfully. Found {len(collections)} collections")
            except Exception as conn_error:
                logger.warning(f"⚠️ CHROMA: Connection test failed, using persistent local mode: {conn_error}")
                # Fallback to persistent local mode
                self.client = chromadb.PersistentClient(
                    path="./chroma_public_db",
                    settings=Settings(
                        anonymized_telemetry=False,
                        allow_reset=False
                    )
                )
            
            # Initialize embedding function (reuse same model as your system)
            if SENTENCE_TRANSFORMERS_AVAILABLE:
                self.embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
                    model_name="all-MiniLM-L6-v2"  # Same as your existing system
                )
                logger.info("✅ CHROMA: Using SentenceTransformer embeddings")
            else:
                # Fallback to default embeddings
                self.embedding_function = embedding_functions.DefaultEmbeddingFunction()
                logger.warning("⚠️ CHROMA: Using default embeddings (SentenceTransformer not available)")
            
            # Create or get public knowledge collection
            self.collection = self._get_or_create_collection()
            self.is_ready = True
            
            logger.info("🚀 CHROMA: Public knowledge service initialized successfully")
            
        except Exception as e:
            logger.error(f"❌ CHROMA: Failed to initialize ChromaDB service: {e}")
            self.is_ready = False
    
    def _get_or_create_collection(self):
        """Get or create public knowledge collection"""
        try:
            collection_name = "public_knowledge_base"
            
            # Try to get existing collection
            try:
                collection = self.client.get_collection(
                    name=collection_name,
                    embedding_function=self.embedding_function
                )
                doc_count = collection.count()
                logger.info(f"📚 CHROMA: Using existing collection '{collection_name}' with {doc_count} documents")
                return collection
                
            except Exception:
                # Collection doesn't exist, create it
                collection = self.client.create_collection(
                    name=collection_name,
                    embedding_function=self.embedding_function,
                    metadata={
                        "description": "Public knowledge base for chatbot API",
                        "created_at": datetime.now().isoformat(),
                        "isolation_level": "public_only"
                    }
                )
                logger.info(f"✅ CHROMA: Created new collection '{collection_name}'")
                return collection
                
        except Exception as e:
            logger.error(f"❌ CHROMA: Failed to create/get collection: {e}")
            raise
    
    def _build_context_aware_query(self, latest_query: str, conversation_context: List[Dict[str, str]] = None) -> str:
        """
        Build context-aware search query by appending all user queries from conversation
        
        Args:
            latest_query: User's latest message
            conversation_context: List of conversation messages
            
        Returns:
            Formatted query string for vector search
        """
        if not conversation_context or len(conversation_context) <= 1:
            # First query or no context - use as is
            return latest_query
        
        # Extract all user queries from conversation history
        user_queries = []
        for message in conversation_context:
            if message.get('role') == 'user':
                content = message.get('content', '').strip()
                if content and content != latest_query:  # Avoid duplicate latest query
                    user_queries.append(content)
        
        # Format: "latest query. [previous user queries]"
        if user_queries:
            previous_queries = " ".join(user_queries)
            formatted_query = f"{latest_query}. [{previous_queries}]"
            logger.info(f"🔍 CONTEXT: Built context-aware query with {len(user_queries)} previous queries")
            return formatted_query
        else:
            return latest_query
    
    def _rephrase_query_with_llm(self, latest_query: str, conversation_context: List[Dict[str, str]]) -> str:
        """
        Use LLM to rephrase user query based on conversation context for better retrieval
        
        Args:
            latest_query: User's current query (potentially incomplete/lazy)
            conversation_context: Full conversation history
            
        Returns:
            Rephrased query that is more complete and specific
        """
        try:
            # Import LLM service
            from .llm_integration import PublicLLMService
            from .models import ChatbotConfiguration
            
            # Get chatbot configuration
            config = ChatbotConfiguration.get_config()
            
            # Build conversation history for context
            conversation_history = ""
            if conversation_context and len(conversation_context) > 0:
                for msg in conversation_context[:-1]:  # Exclude the latest query (it's already in latest_query)
                    role = msg.get('role', '').capitalize()
                    content = msg.get('content', '').strip()
                    if role and content:
                        conversation_history += f"{role}: {content}\n"
            
            # Create rephrasing prompt
            rephrasing_prompt = f"""Based on the following conversation context, please rephrase the user's latest query to be more complete, specific, and suitable for information retrieval. The rephrased query should:

1. Be a complete, well-formed question or statement
2. Include necessary context from the conversation 
3. Be specific enough for effective search
4. Maintain the user's original intent
5. Be suitable for finding relevant information

Conversation Context:
{conversation_history}

User's Latest Query: {latest_query}

Please provide ONLY the rephrased query, nothing else:"""
            
            # Create system prompt for rephrasing
            system_prompt = "You are an expert at rephrasing user queries to make them more effective for information retrieval. You rephrase incomplete or lazy queries into complete, specific, and searchable questions while preserving the user's intent."
            
            # Use LLM service for rephrasing
            llm_service = PublicLLMService()
            
            # Generate rephrased query using same provider/model as chatbot
            result = llm_service.generate_response(
                prompt=rephrasing_prompt,
                provider=config.default_llm_provider,
                model=config.default_model,
                max_tokens=150,  # Short response expected
                temperature=0.3,  # Lower temperature for consistent rephrasing
                system_prompt=system_prompt,
                request_id=f"rephrase_{hash(latest_query) % 10000:04d}"
            )
            
            if result.get('success') and result.get('response'):
                rephrased_query = result['response'].strip()
                
                # Basic validation - ensure we got a meaningful response
                if len(rephrased_query) > 10 and rephrased_query.lower() != latest_query.lower():
                    logger.info(f"🔄 REPHRASE: '{latest_query}' → '{rephrased_query}'")
                    return rephrased_query
                else:
                    logger.warning(f"🔄 REPHRASE: LLM returned insufficient rephrasing, using original query")
                    return latest_query
            else:
                logger.error(f"🔄 REPHRASE: LLM call failed - {result.get('error', 'Unknown error')}")
                return latest_query
                
        except Exception as e:
            logger.error(f"🔄 REPHRASE: Exception during query rephrasing - {e}")
            return latest_query
    
    def search_knowledge(self, query: str, limit: int = 10, conversation_context: List[Dict[str, str]] = None) -> List[Dict[str, Any]]:
        """
        Search public knowledge base with conversation context support
        
        Args:
            query: User's latest message
            limit: Maximum number of results to return (default 10)
            conversation_context: List of previous conversation messages
            
        Returns:
            List of search results with content and metadata
        """
        if not self.is_ready or not self.collection:
            logger.error("CHROMA: Service not ready for queries")
            return []
        
        # Get similarity threshold from configuration
        from .models import ChatbotConfiguration
        config = ChatbotConfiguration.get_config()
        similarity_threshold = config.similarity_threshold
        
        try:
            # Determine if this is a subsequent query (not first query)
            is_subsequent_query = conversation_context and len(conversation_context) > 1
            
            # Check if query rephrasing is enabled
            use_query_rephrasing = (
                hasattr(config, 'enable_query_rephrasing') and 
                config.enable_query_rephrasing and 
                is_subsequent_query
            )
            
            # Step 1: Rephrase query if this is a subsequent query and rephrasing is enabled
            final_query = query
            if use_query_rephrasing:
                logger.info(f"🔄 REPHRASE: Processing subsequent query for rephrasing: '{query}'")
                final_query = self._rephrase_query_with_llm(query, conversation_context)
                
                # Log the rephrasing result
                if final_query != query:
                    logger.info(f"🔄 REPHRASE: Successfully rephrased query")
                else:
                    logger.info(f"🔄 REPHRASE: Using original query (no rephrasing needed or failed)")
            else:
                if is_subsequent_query:
                    logger.info(f"🔄 REPHRASE: Skipped (disabled in config) for subsequent query: '{query}'")
                else:
                    logger.info(f"🔄 REPHRASE: Skipped (first query) for: '{query}'")
            
            # Step 2: Build context-aware search query (existing logic)
            # For first query or when rephrasing is disabled, use the existing context-aware approach
            if use_query_rephrasing:
                # Use the rephrased query directly (don't append conversation context since it's already incorporated)
                search_query = final_query
                logger.info(f"🔍 SEARCH: Using rephrased query for ChromaDB: '{search_query[:100]}...'")
            else:
                # Use existing context-aware query building for first query or when rephrasing is disabled
                search_query = self._build_context_aware_query(final_query, conversation_context)
                logger.info(f"🔍 SEARCH: Using context-aware query for ChromaDB: '{search_query[:100]}...'")
            
            
            # Perform vector search in ChromaDB (isolated from your Milvus)
            results = self.collection.query(
                query_texts=[search_query],
                n_results=min(limit, 15),  # Max 15 results to get top 10 quality ones
                include=['documents', 'metadatas', 'distances']
            )
            
            # Format results for API response
            formatted_results = []
            
            if results and 'documents' in results and results['documents']:
                documents = results['documents'][0]  # First query results
                metadatas = results.get('metadatas', [[]])[0]
                distances = results.get('distances', [[]])[0]
                
                for i, doc in enumerate(documents):
                    metadata = metadatas[i] if i < len(metadatas) else {}
                    distance = distances[i] if i < len(distances) else 1.0
                    
                    # Convert distance to similarity score (0-1)
                    similarity = max(0.0, 1.0 - distance)
                    
                    # Filter by similarity threshold
                    if similarity >= similarity_threshold:
                        formatted_results.append({
                            'content': doc,
                            'metadata': metadata,
                            'similarity_score': round(similarity, 4),
                            'source': metadata.get('source', 'Public Knowledge Base'),
                            'category': metadata.get('category', 'General'),
                            'title': metadata.get('title', 'Knowledge Entry')
                        })
            
            total_results = len(documents) if documents else 0
            filtered_results = len(formatted_results)
            logger.info(f"🔍 CHROMA: Found {filtered_results}/{total_results} results above threshold {similarity_threshold} for query: '{search_query[:50]}...'")
            return formatted_results
            
        except Exception as e:
            logger.error(f"❌ CHROMA: Search failed: {e}")
            return []
    
    def add_knowledge(self, documents: List[str], metadatas: List[Dict[str, Any]], ids: Optional[List[str]] = None) -> bool:
        """
        Add knowledge to public database (admin-controlled)
        
        Args:
            documents: List of document texts
            metadatas: List of metadata dictionaries
            ids: Optional list of document IDs
            
        Returns:
            True if successful, False otherwise
        """
        if not self.is_ready or not self.collection:
            logger.error("CHROMA: Service not ready for adding documents")
            return False
        
        try:
            # Generate IDs if not provided
            if not ids:
                ids = [f"doc_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{i}" for i in range(len(documents))]
            
            # Add security metadata
            for metadata in metadatas:
                metadata.update({
                    'added_at': datetime.now().isoformat(),
                    'isolation_level': 'public_only',
                    'approved_for_public': True
                })
            
            # Add to ChromaDB collection
            self.collection.add(
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )
            
            logger.info(f"✅ CHROMA: Added {len(documents)} documents to public knowledge base")
            return True
            
        except Exception as e:
            logger.error(f"❌ CHROMA: Failed to add documents: {e}")
            return False
    
    def delete_knowledge(self, document_id: str) -> bool:
        """
        Delete document and all its chunks from ChromaDB
        
        Args:
            document_id: Document ID from Django model
            
        Returns:
            True if successful, False otherwise
        """
        if not self.is_ready or not self.collection:
            logger.error("CHROMA: Service not ready for deleting documents")
            return False
        
        try:
            # Find all chunk IDs for this document
            # ChromaDB chunk IDs follow pattern: {document_id}_chunk_0, {document_id}_chunk_1, etc.
            
            # First, search for all chunks belonging to this document by metadata
            search_results = self.collection.get(
                where={"document_id": document_id},
                include=['metadatas']
            )
            
            if not search_results or not search_results.get('ids'):
                logger.warning(f"🔍 CHROMA: No chunks found for document {document_id}")
                return True  # Consider this success since document is already not in ChromaDB
            
            chunk_ids = search_results['ids']
            logger.info(f"🗑️ CHROMA: Found {len(chunk_ids)} chunks to delete for document {document_id}")
            
            # Delete all chunks for this document
            self.collection.delete(ids=chunk_ids)
            
            logger.info(f"✅ CHROMA: Successfully deleted {len(chunk_ids)} chunks for document {document_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ CHROMA: Failed to delete document {document_id}: {e}")
            return False
    
    def document_exists_in_chromadb(self, document_id: str) -> bool:
        """
        Check if document already exists in ChromaDB
        
        Args:
            document_id: Document ID from Django model
            
        Returns:
            True if document exists, False otherwise
        """
        if not self.is_ready or not self.collection:
            return False
        
        try:
            # Search for any chunks belonging to this document
            search_results = self.collection.get(
                where={"document_id": document_id},
                include=['metadatas'],
                limit=1  # We only need to know if any exist
            )
            
            exists = bool(search_results and search_results.get('ids'))
            if exists:
                chunk_count = len(search_results['ids']) if search_results.get('ids') else 0
                logger.info(f"🔍 CHROMA: Document {document_id} exists with {chunk_count} chunks")
            else:
                logger.info(f"🔍 CHROMA: Document {document_id} does not exist")
                
            return exists
            
        except Exception as e:
            logger.error(f"❌ CHROMA: Failed to check if document {document_id} exists: {e}")
            return False
    
    def smart_sync_knowledge(self, documents: List[str], metadatas: List[Dict[str, Any]], 
                           ids: Optional[List[str]] = None, document_id: str = None, 
                           force_update: bool = False) -> bool:
        """
        Smart sync that handles updates and prevents duplicates
        
        Args:
            documents: List of document texts (chunks)
            metadatas: List of metadata dictionaries  
            ids: List of chunk IDs
            document_id: Parent document ID for update checking
            force_update: Force update even if document exists
            
        Returns:
            True if successful, False otherwise
        """
        if not self.is_ready or not self.collection:
            logger.error("CHROMA: Service not ready for smart sync")
            return False
        
        try:
            # Check if document already exists
            if document_id and not force_update:
                if self.document_exists_in_chromadb(document_id):
                    logger.warning(f"🔄 CHROMA: Document {document_id} already exists. Use force_update=True to replace.")
                    return True  # Consider this success since document is already synced
            
            # If document exists and we want to update, delete old chunks first
            if document_id and (force_update or self.document_exists_in_chromadb(document_id)):
                logger.info(f"🔄 CHROMA: Updating existing document {document_id} - removing old chunks")
                self.delete_knowledge(document_id)
            
            # Add new chunks
            success = self.add_knowledge(documents=documents, metadatas=metadatas, ids=ids)
            
            if success:
                action = "updated" if document_id and force_update else "added"
                logger.info(f"✅ CHROMA: Smart sync {action} document {document_id} with {len(documents)} chunks")
            
            return success
            
        except Exception as e:
            logger.error(f"❌ CHROMA: Smart sync failed for document {document_id}: {e}")
            return False
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """Get collection statistics"""
        if not self.is_ready or not self.collection:
            return {'status': 'not_ready', 'document_count': 0}
        
        try:
            count = self.collection.count()
            return {
                'status': 'ready',
                'document_count': count,
                'collection_name': 'public_knowledge_base',
                'isolation_level': 'public_only',
                'last_checked': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"❌ CHROMA: Failed to get stats: {e}")
            return {'status': 'error', 'error': str(e)}
    
    def health_check(self) -> Dict[str, Any]:
        """Health check for monitoring"""
        try:
            if not self.is_ready:
                return {'status': 'unhealthy', 'reason': 'Service not initialized'}
            
            # Test basic functionality
            test_results = self.search_knowledge("test query", limit=1)
            stats = self.get_collection_stats()
            
            return {
                'status': 'healthy',
                'chromadb_available': CHROMADB_AVAILABLE,
                'sentence_transformers_available': SENTENCE_TRANSFORMERS_AVAILABLE,
                'collection_stats': stats,
                'search_test': 'passed' if isinstance(test_results, list) else 'failed',
                'last_check': datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'last_check': datetime.now().isoformat()
            }


class ChatbotSecurityService:
    """Security service for public chatbot (isolated from main system)"""
    
    # Prompt injection patterns
    INJECTION_PATTERNS = [
        r'ignore\s+previous\s+instructions',
        r'forget\s+everything',
        r'you\s+are\s+now',
        r'system\s*:\s*',
        r'assistant\s*:\s*',
        r'user\s*:\s*',
        r'<\s*system\s*>',
        r'<\s*\/\s*system\s*>',
        r'roleplay\s+as',
        r'pretend\s+to\s+be',
        r'act\s+as\s+if',
        r'disregard\s+',
        r'override\s+',
    ]
    
    @classmethod
    def validate_input(cls, message: str, client_ip: str = None) -> Dict[str, Any]:
        """
        Validate user input for security threats
        
        Args:
            message: User's input message
            client_ip: Client IP address for logging
            
        Returns:
            Dict with validation results
        """
        import re
        
        # Basic validation
        if not message or not message.strip():
            return {
                'valid': False,
                'error': 'Message cannot be empty',
                'reason': 'empty_message'
            }
        
        # Length validation
        if len(message) > 500:
            return {
                'valid': False,
                'error': 'Message too long (max 500 characters)',
                'reason': 'message_too_long'
            }
        
        # Check for prompt injection attempts
        message_lower = message.lower()
        for pattern in cls.INJECTION_PATTERNS:
            if re.search(pattern, message_lower):
                logger.warning(f"🚨 SECURITY: Prompt injection attempt from {client_ip}: {pattern}")
                return {
                    'valid': False,
                    'error': 'Invalid input detected',
                    'reason': 'security_violation',
                    'pattern_detected': pattern
                }
        
        # Check for excessive special characters (potential injection)
        special_char_ratio = sum(1 for c in message if not c.isalnum() and not c.isspace()) / len(message)
        if special_char_ratio > 0.3:  # More than 30% special characters
            logger.warning(f"🚨 SECURITY: High special character ratio from {client_ip}: {special_char_ratio:.2f}")
            return {
                'valid': False,
                'error': 'Invalid input format',
                'reason': 'suspicious_format'
            }
        
        return {
            'valid': True,
            'message': 'Input validation passed',
            'sanitized_message': message.strip()
        }
    
    @classmethod
    def check_rate_limit_exceeded(cls, ip_address: str) -> bool:
        """Check if IP has exceeded daily rate limits"""
        try:
            from .models import IPUsageLimit
            from django.utils import timezone
            
            usage, created = IPUsageLimit.objects.get_or_create(
                ip_address=ip_address,
                defaults={'daily_request_count': 0}
            )
            
            # Reset daily count if it's a new day
            if usage.last_reset_date < timezone.now().date():
                usage.daily_request_count = 0
                usage.last_reset_date = timezone.now().date()
                usage.save()
            
            # Check if blocked
            if usage.is_blocked and usage.blocked_until and usage.blocked_until > timezone.now():
                return True
            
            # Check daily limit (100 requests per day per IP)
            if usage.daily_request_count >= 100:
                usage.is_blocked = True
                usage.blocked_until = timezone.now().replace(hour=23, minute=59, second=59)
                usage.save()
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"❌ SECURITY: Rate limit check failed for {ip_address}: {e}")
            return False  # Allow request on error