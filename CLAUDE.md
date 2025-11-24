# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI Catalogue AICC is a containerized AI-powered document analysis and workflow orchestration platform. It provides semantic search, custom agent orchestration, and multi-LLM integration for intelligent document processing.

**Tech Stack:**
- **Backend**: Django 5.2+ (Python 3.13+)
- **Frontend**: SvelteKit with TypeScript
- **Databases**: PostgreSQL (relational), Milvus v2.6.0 (vector search), ChromaDB (public chatbot)
- **Infrastructure**: Docker Compose, Nginx, etcd, MinIO

## Development Commands

### Starting the Application

```bash
# Development mode (hot reload enabled for both frontend and backend)
./scripts/start-dev.sh

# View logs
docker compose -f docker-compose.yml -f docker-compose.override.yml logs -f

# Backend logs only
docker compose logs -f backend

# Frontend logs only
docker compose logs -f frontend-dev

# Restart a specific service
docker compose restart <service-name>

# Stop all services
docker compose -f docker-compose.yml -f docker-compose.override.yml down
```

### Database Operations

```bash
# Access PostgreSQL via psql
docker compose exec postgres psql -U ai_catalogue_user -d ai_catalogue_db

# Django migrations
docker compose exec backend python manage.py makemigrations
docker compose exec backend python manage.py migrate

# Create superuser
docker compose exec backend python manage.py createsuperuser

# Access Django shell
docker compose exec backend python manage.py shell
```

### Frontend Development

```bash
# Access frontend container
docker compose exec frontend-dev sh

# Inside container - install packages
npm install <package-name>

# Rebuild frontend
docker compose build frontend-dev
docker compose restart frontend-dev
```

### Backend Development

```bash
# Access backend container
docker compose exec backend sh

# Run tests
docker compose exec backend python manage.py test

# Check Python dependencies
docker compose exec backend pip list

# Install new Python package (then update requirements.txt)
docker compose exec backend pip install <package-name>
```

### Milvus Operations

```bash
# Check Milvus health
curl http://localhost:9091/healthz

# Access Attu (Milvus UI)
# URL: http://localhost:3001
# Milvus Address: milvus:19530
# Credentials: see MILVUS_ROOT_USER and MILVUS_ROOT_PASSWORD in .env
```

## Architecture

### High-Level System Design

```
┌─────────────┐     ┌─────────────┐     ┌──────────────┐
│   Nginx     │────▶│  SvelteKit  │────▶│    Django    │
│   :80/443   │     │   :5173     │     │    :8000     │
└─────────────┘     └─────────────┘     └──────┬───────┘
                                               │
                    ┌──────────────────────────┼────────────┐
                    │                          │            │
              ┌─────▼─────┐            ┌──────▼──────┐  ┌──▼─────┐
              │ PostgreSQL │            │   Milvus    │  │ ChromaDB│
              │   :5432    │            │   :19530    │  │  :8001  │
              └────────────┘            └─────┬───────┘  └─────────┘
                                              │
                                    ┌─────────┴─────────┐
                                    │                   │
                              ┌─────▼─────┐      ┌─────▼─────┐
                              │   etcd    │      │   MinIO   │
                              │   :2379   │      │   :9000   │
                              └───────────┘      └───────────┘
```

### Backend Django Apps

**Core Apps:**
- `core/` - Django project settings, URL routing, middleware configuration
- `api/` - REST API endpoints, serializers, universal project views
- `users/` - Custom user model with roles (Admin/Staff/User), authentication, permissions
- `templates/` - Project template system for different document processing workflows

**AI & Vector Search:**
- `vector_search/` - Document processing, semantic search, hierarchical processing
- `django_milvus_search/` - Milvus integration, collection management, embedding operations
- `agent_orchestration/` - **Custom agent framework** (no AutoGen), workflow execution, conversation orchestration
- `llm_eval/` - Multi-provider LLM management (OpenAI, Anthropic, Google)

**Specialized Features:**
- `project_api_keys/` - Project-specific encrypted API key management
- `public_chatbot/` - Isolated public chatbot API with ChromaDB backend

**Key Services:**
- `agent_orchestration/workflow_executor.py` - Executes agent workflows
- `agent_orchestration/conversation_orchestrator.py` - Manages multi-agent conversations
- `agent_orchestration/chat_manager.py` - Handles chat logic
- `agent_orchestration/docaware/` - RAG functionality for agents (document-aware agents)
- `vector_search/database.py` - Milvus connection pooling and operations
- `vector_search/consolidated_api_views.py` - Unified vector search endpoints

### Frontend Structure

```
frontend/my-sveltekit-app/src/
├── routes/
│   ├── +layout.svelte        # Root layout
│   ├── +layout.ts            # Layout loader
│   ├── +page.svelte          # Home page
│   ├── admin/                # Admin dashboard routes
│   ├── features/             # Feature pages
│   ├── login/                # Authentication
│   └── reset-password/       # Password reset
├── lib/
│   ├── components/           # Reusable Svelte components
│   ├── services/             # API service layers
│   └── stores/               # Svelte stores for state management
└── app.css                   # Global styles (Tailwind)
```

### Universal Project System

The application uses a **template-based project architecture**:

1. **Project Templates** (`templates/models.py`): Define reusable project configurations
2. **Universal Projects** API (`api/universal_project_views.py`): Single endpoint handles all project types
3. **Template Discovery**: Dynamic template loading from `templates/template_definitions/`
4. **Processing Modes**: Hierarchical, standard, or template-specific processing

**All project operations use**: `/api/projects/{project_id}/` endpoints

### Agent Orchestration (Custom Implementation)

**No AutoGen dependency** - completely custom implementation:

- **Workflow Definition**: JSON-based workflow schemas with agent nodes and transitions
- **Agent Types**: AssistantAgent, UserProxyAgent, DelegateAgent, GroupChatManager
- **DocAware Agents**: RAG-enabled agents that search project documents during conversation
- **Execution Model**: Async conversation orchestration with real-time streaming
- **LLM Providers**: Multi-provider support via `agent_orchestration/llm_provider_manager.py`

**DocAware Search Methods:**
- Semantic search (vector similarity)
- Hybrid search (semantic + keyword)
- Contextual search (conversation-aware)
- Keyword search (BM25)
- Similarity threshold filtering

### Vector Database Architecture

**Milvus v2.6.0 Features:**
- Storage Format V2 with improved performance
- Unified coordinator architecture (mixCoord)
- Enhanced authentication system
- Native WAL with streaming capabilities

**Collection Naming Convention:**
- Main collection: `{project_id}_collection`
- Hierarchical: `{project_id}_hierarchical`
- Template-specific: `{project_id}_{template_name}`

**Embedding Model**: Uses SentenceTransformers (configurable in `vector_search/embeddings.py`)

## Environment Configuration

**Critical Environment Variables:**

```bash
# Database
DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT

# Milvus (v2.6.0 requires authentication)
MILVUS_ROOT_USER=milvusadmin
MILVUS_ROOT_PASSWORD=<secure_password>
MILVUS_HOST=milvus
MILVUS_PORT=19530

# MinIO
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=<secure_password>

# Django
DJANGO_SECRET_KEY=<secret>
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1,backend,frontend

# API Keys (for document processing and LLM operations)
GOOGLE_API_KEY=<key>          # PDF/image OCR via Gemini
OPENAI_API_KEY=<key>          # Content summarization
ANTHROPIC_API_KEY=<key>       # Advanced AI features

# Public Chatbot (isolated)
AICC_CHATBOT_OPENAI_API_KEY=<key>

# Security (CRITICAL - encrypts project-specific API keys)
PROJECT_API_KEY_ENCRYPTION_KEY=<32-byte-base64-key>
```

## Common Development Workflows

### Adding a New Django App

1. Create app: `docker compose exec backend python manage.py startapp <app_name>`
2. Add to `INSTALLED_APPS` in `backend/core/settings.py`
3. Create models in `<app_name>/models.py`
4. Run migrations: `docker compose exec backend python manage.py makemigrations && docker compose exec backend python manage.py migrate`
5. Register in admin (optional): `<app_name>/admin.py`
6. Add API endpoints in `<app_name>/views.py` and URL routing

### Adding a New API Endpoint

1. Create view in appropriate app's `views.py` or `api_views.py`
2. Add URL pattern to `backend/core/urls.py` or app-specific `urls.py`
3. Add to DRF router if using ViewSets
4. Test endpoint: `curl http://localhost:8000/api/<endpoint>/`

### Processing Documents for a Project

Documents are processed through the unified endpoint:
- `POST /api/projects/{project_id}/process_documents/` (or `/digest/` for legacy)
- Automatically selects processing mode based on project template
- Generates embeddings and stores in Milvus
- Supports PDF, DOCX, TXT, MD, XLSX formats

### Creating Agent Workflows

1. Define workflow JSON with agents and transitions
2. POST to `/api/projects/{project_id}/workflows/`
3. Execute: POST to `/api/projects/{project_id}/workflows/{workflow_id}/execute/`
4. Monitor via conversation endpoint or streaming WebSocket

### Running Tests

```bash
# All tests
docker compose exec backend python manage.py test

# Specific app
docker compose exec backend python manage.py test agent_orchestration

# Specific test file
docker compose exec backend python test_conversation_workflow.py

# With verbose output
docker compose exec backend python manage.py test --verbosity=2
```

## Important Architectural Notes

### Authentication & Authorization
- JWT-based authentication via `rest_framework_simplejwt`
- Token endpoints: `/api/token/` (obtain), `/api/token/refresh/` (refresh)
- Custom user model: `users.User` with role-based access (Admin/Staff/User)
- Group-based permissions for dashboard icons and project access

### API Key Management
- **System-level keys**: Set via environment variables (GOOGLE_API_KEY, etc.)
- **Project-level keys**: Encrypted in database via `project_api_keys` app
- Encryption key: `PROJECT_API_KEY_ENCRYPTION_KEY` (must be set in .env)

### CORS Configuration
- Custom middleware: `public_chatbot.middleware.cors.PublicChatbotCORSMiddleware`
- Development origins allowed via `CORS_ALLOWED_ORIGINS` and `CSRF_TRUSTED_ORIGINS`

### DocAware Integration
- Enabled per-agent in workflow configuration
- Searches project documents during conversation
- Configurable search methods and parameters
- Automatic context injection into agent prompts

### Milvus Connection Management
- Connection pooling in `vector_search/database.py`
- Automatic retry logic for transient failures
- Health check: `curl http://localhost:9091/healthz`
- UI management: Attu at `http://localhost:3001`

### ChromaDB Usage
- **Only** used by public chatbot (`public_chatbot/` app)
- Separate from main Milvus vector database
- API: `http://localhost:8001`
- Data persisted in `chromadb_data` volume

## Troubleshooting

### Milvus Connection Issues
```bash
# Check Milvus health
docker compose logs milvus --tail 50

# Verify credentials in .env
grep MILVUS .env

# Restart Milvus
docker compose restart milvus
```

### Database Migration Errors
```bash
# Check migration status
docker compose exec backend python manage.py showmigrations

# Reset specific app migrations (dangerous - dev only)
docker compose exec backend python manage.py migrate <app_name> zero
docker compose exec backend python manage.py migrate <app_name>
```

### Frontend Build Failures
```bash
# Clear node_modules and rebuild
docker compose exec frontend-dev sh
rm -rf node_modules package-lock.json
npm install
```

### Port Conflicts
```bash
# Check what's using a port
lsof -i :<port_number>

# Or use the fix script
./fix-port-3001.sh
```

## File Locations

- **Configuration**: `.env` (root), `backend/core/settings.py`
- **Docker**: `docker-compose.yml`, `docker-compose.override.yml` (dev mode)
- **Startup scripts**: `./scripts/start-dev.sh`, `./scripts/start.sh`
- **Documentation**: `./documentation/` (README.md, README-DOCKER.md, etc.)
- **Media uploads**: `backend/media/` (mounted to `backend_media` volume)
- **Logs**: `backend/logs/`, `./logs/`
- **Test files**: `backend/test_*.py` (various integration tests)

## Access URLs

- **Application**: http://localhost (via Nginx)
- **Frontend Dev**: http://localhost:5173 (direct, with HMR)
- **Backend API**: http://localhost:8000
- **Django Admin**: http://localhost:8000/admin/
- **API Root**: http://localhost:8000/api/
- **PgAdmin**: http://localhost:8080
- **Attu (Milvus UI)**: http://localhost:3001
- **Milvus API**: http://localhost:9091
- **ChromaDB API**: http://localhost:8001

---

## DocAware Backend & Milvus Vector Implementation

### Overview

DocAware is a Retrieval-Augmented Generation (RAG) system that enables agents to search and retrieve project documents during conversation. The **Content Filter** feature allows agents to scope searches to specific folders within the project's hierarchical document structure using Milvus vector database.

### Architecture Components

#### 1. API Layer - `backend/agent_orchestration/docaware_views.py`

**DocAwareConfigViewSet** provides REST endpoints for DocAware functionality:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/docaware/search_methods/` | GET | Returns available search methods and configurations |
| `/docaware/test_search/` | POST | Tests search with optional content filter |
| `/docaware/hierarchical_paths/` | GET | Returns folder structure for content filtering |
| `/docaware/validate_parameters/` | POST | Validates search method parameters |
| `/docaware/collections/` | GET | Returns available Milvus collections |

**Key Implementation Details:**

```python
# hierarchical_paths endpoint (docaware_views.py:314-393)
@action(detail=False, methods=['get'])
def hierarchical_paths(self, request):
    """Get hierarchical paths for content filtering"""
    project_id = request.query_params.get('project_id')

    # Initialize DocAware service
    docaware_service = EnhancedDocAwareAgentService(project_id)

    # Get hierarchical paths from Milvus collection
    hierarchical_data = docaware_service.get_hierarchical_paths()

    return Response({
        'project_id': project_id,
        'hierarchical_paths': hierarchical_data,
        'count': len(hierarchical_data)
    })

# test_search endpoint with content filter (docaware_views.py:118-271)
@action(detail=False, methods=['post'])
def test_search(self, request):
    """Test search functionality with given parameters"""
    project_id = request.data.get('project_id')
    method_id = request.data.get('method')
    parameters = request.data.get('parameters', {})
    query = request.data.get('query')
    content_filter = request.data.get('content_filter')  # Content filter ID

    # Initialize DocAware service
    docaware_service = EnhancedDocAwareAgentService(project_id)

    # Perform search with content filter
    search_results = docaware_service.search_documents(
        query=query,
        search_method=search_method,
        method_parameters=parameters,
        content_filter=content_filter
    )

    return Response({
        'success': True,
        'query': query,
        'method': method_id,
        'results_count': len(search_results),
        'sample_results': formatted_results
    })
```

#### 2. Service Layer - `backend/agent_orchestration/docaware/service.py`

**EnhancedDocAwareAgentService** is the main RAG service class that integrates with Django Milvus Search.

**Core Methods:**

##### A. `search_documents()` - Main Search Entry Point

```python
def search_documents(
    self,
    query: str,
    search_method: SearchMethod = SearchMethod.SEMANTIC_SEARCH,
    method_parameters: Optional[Dict[str, Any]] = None,
    conversation_context: Optional[List[str]] = None,
    content_filter: Optional[str] = None  # ← Content filter parameter
) -> List[Dict[str, Any]]:
    """
    Search documents using the specified method

    Args:
        query: Search query text
        search_method: Method to use for searching
        method_parameters: Parameters specific to the search method
        conversation_context: Recent conversation context
        content_filter: Content filter ID (e.g., "folder_Reports/Financial")

    Returns:
        List of search results with content and metadata
    """
    # Build content filter expression
    content_filter_expr = self._build_content_filter_expression(content_filter) if content_filter else None

    if content_filter_expr:
        logger.info(f"📚 SEARCH: Applying content filter: {content_filter_expr}")

    # Validate and set parameters
    validated_params = DocAwareSearchMethods.validate_parameters(search_method, parameters)

    # Route to appropriate search implementation with content filter
    if search_method == SearchMethod.SEMANTIC_SEARCH:
        return self._semantic_search(query, validated_params, content_filter_expr)
    elif search_method == SearchMethod.HYBRID_SEARCH:
        return self._hybrid_search(query, validated_params, content_filter_expr)
    # ... other search methods
```

##### B. `_build_content_filter_expression()` - Filter Expression Builder

**Critical Function** - Converts content filter IDs to Milvus filter expressions:

```python
def _build_content_filter_expression(self, content_filter: str) -> str:
    """
    Build Milvus filter expression from content filter ID

    Args:
        content_filter: Content filter ID
            - "folder_Reports/Financial" → Filter by folder path
            - "file_doc123" → Filter by specific document

    Returns:
        Milvus filter expression string
    """
    if not content_filter:
        return ""

    try:
        # FOLDER FILTER: Filter by hierarchical path prefix
        if content_filter.startswith('folder_'):
            folder_path = content_filter[7:]  # Remove 'folder_' prefix
            escaped_path = folder_path.replace("'", "''")  # SQL injection prevention
            # Use LIKE operator for hierarchical matching
            filter_expr = f"hierarchical_path like '{escaped_path}%'"
            logger.info(f"🔍 CONTENT FILTER: Folder - path starts with: {folder_path}")

        # FILE FILTER: Filter by specific document ID
        elif content_filter.startswith('file_'):
            document_id = content_filter[5:]  # Remove 'file_' prefix
            escaped_doc_id = document_id.replace("'", "''")
            filter_expr = f"document_id == '{escaped_doc_id}'"
            logger.info(f"🔍 CONTENT FILTER: File - document_id: {document_id}")

        else:
            logger.warning(f"🔍 CONTENT FILTER: Unknown filter format: {content_filter}")
            return ""

        logger.info(f"🔍 CONTENT FILTER: Generated expression: {filter_expr}")
        return filter_expr

    except Exception as e:
        logger.error(f"❌ CONTENT FILTER: Failed to build filter: {e}")
        return ""
```

**Filter ID Format:**
- `folder_Reports/Financial` → Filters all documents in "Reports/Financial" folder and subfolders
- `file_abc123` → Filters specific document with ID "abc123"

##### C. `get_hierarchical_paths()` - Extract Folder Structure

**Purpose:** Extracts unique folder paths from Milvus collection for frontend dropdown

```python
def get_hierarchical_paths(self) -> List[Dict[str, Any]]:
    """
    Get unique hierarchical paths for content filtering from Milvus collection
    Returns unique folder paths only (no individual files)
    """
    try:
        logger.info(f"📚 HIERARCHICAL PATHS: Getting unique folder paths for {self.collection_name}")

        # Create search with dummy vector to retrieve all hierarchical_path values
        dummy_query = [0.0] * 384  # 384-dimensional zero vector

        search_request = SearchRequest(
            collection_name=self.collection_name,
            query_vectors=[dummy_query],
            index_type=IndexType.AUTOINDEX,
            metric_type=MetricType(detected_metric),
            limit=10000,  # High limit to get all documents
            output_fields=["hierarchical_path"]  # Only fetch this field
        )

        search_result = self.milvus_service.search(search_request)

        # Extract unique folder paths
        unique_folder_paths = set()

        for hit in search_result.hits:
            hierarchical_path = hit.get("hierarchical_path", "")

            if hierarchical_path and hierarchical_path.strip():
                clean_path = hierarchical_path.strip().strip('/')
                if clean_path:
                    # Add full path as folder
                    unique_folder_paths.add(clean_path)

                    # Also add all parent folder paths
                    path_parts = clean_path.split('/')
                    for i in range(1, len(path_parts)):
                        parent_path = '/'.join(path_parts[:i])
                        if parent_path:
                            unique_folder_paths.add(parent_path)

        # Convert to sorted list for frontend
        folder_list = []
        for folder_path in sorted(unique_folder_paths):
            folder_list.append({
                "id": f"folder_{folder_path}",  # Frontend ID format
                "name": folder_path.split('/')[-1],  # Last part of path
                "path": folder_path,
                "type": "folder",
                "displayName": folder_path,
                "isFolder": True
            })

        logger.info(f"📚 HIERARCHICAL PATHS: Found {len(folder_list)} unique folder paths")
        return folder_list

    except Exception as e:
        logger.error(f"📚 HIERARCHICAL PATHS: Failed to get paths: {e}")
        return []
```

**Algorithm:**
1. Query Milvus with dummy vector + high limit (10,000) to retrieve all documents
2. Extract `hierarchical_path` field from each document
3. Build set of unique folder paths including all parent folders
4. Format as list with metadata for frontend dropdown

##### D. `_semantic_search()` - Vector Search with Filter

```python
def _semantic_search(self, query: str, params: Dict[str, Any], content_filter_expr: str = None):
    """Enhanced semantic search with automatic metric detection and content filter"""
    try:
        # Auto-detect collection metric type
        detected_metric = self.get_collection_metric_type(self.collection_name)

        # Generate query embedding
        query_vector = self.embedding_service.encode_query(query)

        # Create search request WITH content filter
        search_request = SearchRequest(
            collection_name=self.collection_name,
            query_vectors=[query_vector],
            index_type=IndexType(params["index_type"]),
            metric_type=MetricType(detected_metric),
            limit=params["search_limit"],
            filter_expression=content_filter_expr if content_filter_expr else "",  # ← Filter applied
            output_fields=["*"]  # Return all fields
        )

        # Perform search
        search_result = self.milvus_service.search(search_request)

        # Filter by relevance threshold and format results
        results = []
        for hit in search_result.hits:
            score = hit.get("score", 0.0)
            if score >= params["relevance_threshold"]:
                results.append({
                    "content": hit.get("content", ""),
                    "metadata": {
                        "source": hit.get("source", "Unknown"),
                        "page": hit.get("page", 1),
                        "score": score,
                        "hierarchical_path": hit.get("hierarchical_path", ""),
                        "chunk_type": hit.get("chunk_type", "text"),
                        "document_id": hit.get("document_id", ""),
                        "collection": self.collection_name,
                        "search_method": "semantic_search",
                        "metric_used": detected_metric
                    }
                })

        logger.info(f"✅ SEMANTIC: Found {len(results)} results above threshold using {detected_metric}")
        return results

    except Exception as e:
        logger.error(f"❌ SEMANTIC: Search failed: {e}")
        return []
```

#### 3. Search Methods - `backend/agent_orchestration/docaware/search_methods.py`

**Available Search Methods:**

| Method | Description | Requires Embedding | Content Filter Support |
|--------|-------------|-------------------|----------------------|
| **Semantic Search** | Vector similarity using embeddings | Yes | ✅ |
| **Hybrid Search** | Semantic + keyword matching | Yes | ✅ |
| **Contextual Search** | Conversation-aware search | Yes | ✅ |
| **Similarity Threshold** | Return all above threshold | Yes | ✅ |
| **Multi-Collection** | Search across collections | Yes | ✅ (project collection only) |
| **Hierarchical Search** | Hierarchy-aware search | Yes | ✅ |
| **Keyword Search** | BM25-style keyword search | No | ✅ |

**All search methods support content filtering** via the `filter_expression` parameter in Milvus SearchRequest.

**Example - Hybrid Search with Content Filter:**

```python
def _hybrid_search(self, query: str, params: Dict, content_filter_expr: str = None):
    """Hybrid search combining semantic and keyword scoring"""

    # Combine existing metadata filter with content filter
    existing_filter = params.get("filter_expression", "")

    if content_filter_expr and existing_filter:
        combined_filter = f"({existing_filter}) && ({content_filter_expr})"
    elif content_filter_expr:
        combined_filter = content_filter_expr
    else:
        combined_filter = existing_filter

    # Search with combined filter
    search_request = SearchRequest(
        collection_name=self.collection_name,
        query_vectors=[query_vector],
        filter_expression=combined_filter,  # ← Combined filters
        ...
    )
```

#### 4. Milvus Vector Database - `backend/vector_search/database.py`

**MilvusProjectVectorDatabase** manages Milvus collections for each project.

##### Collection Schema

```python
fields = [
    # Primary fields
    FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
    FieldSchema(name="document_id", dtype=DataType.VARCHAR, max_length=100),
    FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=384),
    FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=65535),

    # File metadata
    FieldSchema(name="file_name", dtype=DataType.VARCHAR, max_length=255),
    FieldSchema(name="file_type", dtype=DataType.VARCHAR, max_length=100),
    FieldSchema(name="file_size", dtype=DataType.INT64),
    FieldSchema(name="content_length", dtype=DataType.INT64),
    FieldSchema(name="uploaded_at", dtype=DataType.VARCHAR, max_length=50),

    # ⭐ HIERARCHICAL METADATA FIELDS (for content filtering) ⭐
    FieldSchema(name="category", dtype=DataType.VARCHAR, max_length=50),
    FieldSchema(name="subcategory", dtype=DataType.VARCHAR, max_length=50),
    FieldSchema(name="document_type", dtype=DataType.VARCHAR, max_length=50),
    FieldSchema(name="virtual_path", dtype=DataType.VARCHAR, max_length=500),
    FieldSchema(name="hierarchical_path", dtype=DataType.VARCHAR, max_length=500),  # ← KEY FIELD
    FieldSchema(name="hierarchy_level", dtype=DataType.INT64),
    FieldSchema(name="organization_level", dtype=DataType.VARCHAR, max_length=50),

    # Chunk-specific fields
    FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, max_length=100),
    FieldSchema(name="chunk_index", dtype=DataType.INT64),
    FieldSchema(name="total_chunks", dtype=DataType.INT64),
    FieldSchema(name="chunk_type", dtype=DataType.VARCHAR, max_length=50),
    FieldSchema(name="section_title", dtype=DataType.VARCHAR, max_length=200),
    FieldSchema(name="is_complete_document", dtype=DataType.BOOL),

    # AI-Generated Content Fields
    FieldSchema(name="summary", dtype=DataType.VARCHAR, max_length=2000),
    FieldSchema(name="summary_word_count", dtype=DataType.INT64),
    FieldSchema(name="topic", dtype=DataType.VARCHAR, max_length=500),
    FieldSchema(name="topic_word_count", dtype=DataType.INT64),

    # Processing Metadata
    FieldSchema(name="vector_id", dtype=DataType.VARCHAR, max_length=100),
    FieldSchema(name="has_embedding", dtype=DataType.BOOL),
    FieldSchema(name="processing_time_ms", dtype=DataType.INT64),
    FieldSchema(name="error_message", dtype=DataType.VARCHAR, max_length=1000)
]
```

##### Index Creation

```python
def _create_indices(self):
    """Create indices for efficient search"""

    # Vector index for semantic search
    index_params = {
        "metric_type": "IP",  # Inner Product (for normalized vectors)
        "index_type": "IVF_FLAT",
        "params": {"nlist": 1024}
    }
    self.collection.create_index(field_name="embedding", index_params=index_params)

    # ⭐ SCALAR INDICES FOR FAST FILTERING ⭐
    self.collection.create_index(field_name="document_id")
    self.collection.create_index(field_name="file_type")
    self.collection.create_index(field_name="file_name")
    self.collection.create_index(field_name="hierarchical_path")  # ← Enables fast prefix matching
    self.collection.create_index(field_name="category")
    self.collection.create_index(field_name="subcategory")
    self.collection.create_index(field_name="chunk_type")

    logger.info(f"Created enhanced indices for {self.collection_name}")
```

**Why Index `hierarchical_path`?**
- Enables efficient `LIKE 'path%'` filtering (prefix matching)
- Speeds up folder-based searches significantly
- Allows quick extraction of unique folder paths

#### 5. Hierarchical Path Structure

##### Path Format - `backend/vector_search/enhanced_hierarchical_processor.py`

```python
# Generate hierarchical path for each chunk
base_path = hier_info.get('virtual_path', f"documents/general/{file_name}")
path_parts = base_path.split('/')
file_part = path_parts[-1]
folder_path = '/'.join(path_parts[:-1])

# Format: {folder_path}/{file_name}#chunk_{index:03d}
chunk_hierarchical_path = f"{folder_path}/{file_part}#chunk_{chunk_index:03d}"
```

**Examples:**

| Document Location | Chunk Index | hierarchical_path |
|------------------|-------------|-------------------|
| `Reports/Financial/Q1_2024.pdf` | 0 | `Reports/Financial/Q1_2024.pdf#chunk_000` |
| `Reports/Financial/Q1_2024.pdf` | 5 | `Reports/Financial/Q1_2024.pdf#chunk_005` |
| `Legal/Contracts/NDA.docx` | 2 | `Legal/Contracts/NDA.docx#chunk_002` |
| `Research/AI/Paper.pdf` | 10 | `Research/AI/Paper.pdf#chunk_010` |

##### Folder Hierarchy Extraction

From a single path like `Reports/Financial/Subsidiary/Q1.pdf#chunk_000`, the system extracts:

```python
unique_folder_paths = [
    "Reports",                        # Level 1
    "Reports/Financial",              # Level 2
    "Reports/Financial/Subsidiary"   # Level 3 (immediate parent)
]
```

This allows **filtering at any level** of the folder hierarchy:
- Filter by `Reports` → Gets all documents in Reports and subdirectories
- Filter by `Reports/Financial` → Gets only Financial subdirectory
- Filter by `Reports/Financial/Subsidiary` → Gets only Subsidiary subdirectory

### Complete Content Filter Search Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    1. Frontend Request                           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
POST /docaware/test_search/
{
  "project_id": "abc123",
  "method": "semantic_search",
  "query": "quarterly financial report",
  "content_filter": "folder_Reports/Financial",  ← User selection
  "parameters": {
    "search_limit": 5,
    "relevance_threshold": 0.7
  }
}
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│         2. Service Layer - Build Filter Expression              │
└─────────────────────────────────────────────────────────────────┘

_build_content_filter_expression("folder_Reports/Financial")
    ↓
Returns: "hierarchical_path like 'Reports/Financial%'"

                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│           3. Milvus Search with Filter Expression                │
└─────────────────────────────────────────────────────────────────┘

SearchRequest(
    collection_name="project_abc123_collection",
    query_vectors=[embedding_vector],
    filter_expression="hierarchical_path like 'Reports/Financial%'",
    metric_type="IP",
    limit=5
)
    ↓
Milvus performs:
  1. Vector similarity search (Inner Product metric)
  2. Filters results where hierarchical_path starts with "Reports/Financial"
  3. Returns top 5 matches above relevance threshold

                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                  4. Results Formatting                           │
└─────────────────────────────────────────────────────────────────┘

Filtered Results:
[
  {
    "content": "Q1 financial report shows 15% revenue growth...",
    "metadata": {
      "source": "Q1_2024.pdf",
      "hierarchical_path": "Reports/Financial/Q1_2024.pdf#chunk_003",
      "score": 0.89,
      "page": 5,
      "chunk_type": "section",
      "search_method": "semantic_search"
    }
  },
  {
    "content": "Annual revenue summary for fiscal year...",
    "metadata": {
      "source": "Annual_Summary.pdf",
      "hierarchical_path": "Reports/Financial/Annual_Summary.pdf#chunk_001",
      "score": 0.84,
      "page": 2,
      "chunk_type": "paragraph",
      "search_method": "semantic_search"
    }
  }
]
```

### Milvus Filter Expressions

**Supported Operators:**

| Operator | Example | Description |
|----------|---------|-------------|
| `==` | `document_id == 'abc123'` | Exact match |
| `!=` | `file_type != 'pdf'` | Not equal |
| `like` | `hierarchical_path like 'Reports%'` | Prefix match (SQL-style) |
| `>`, `<`, `>=`, `<=` | `score >= 0.8` | Numeric comparison |
| `in` | `category in ['Legal', 'Financial']` | Set membership |
| `&&` | `(filter1) && (filter2)` | AND logic |
| `\|\|` | `(filter1) \|\| (filter2)` | OR logic |

**Content Filter Examples:**

```python
# Single folder filter
"hierarchical_path like 'Reports/Financial%'"

# Specific document
"document_id == 'doc_12345'"

# Folder + file type
"hierarchical_path like 'Legal%' && file_type == 'pdf'"

# Multiple folders (OR)
"(hierarchical_path like 'Reports%') || (hierarchical_path like 'Legal%')"

# Complex filter
"hierarchical_path like 'Reports%' && category == 'Financial' && chunk_type == 'section'"
```

### Performance Optimizations

#### A. Index Strategy

```python
# Vector index for fast similarity search
Index Type: IVF_FLAT
Metric Type: IP (Inner Product)
Parameters: nlist=1024

# Scalar indices for fast filtering
- hierarchical_path (VARCHAR index with LIKE support)
- document_id (VARCHAR index)
- category (VARCHAR index)
- chunk_type (VARCHAR index)
```

#### B. Query Optimization

1. **Filter First, Then Search:**
   - Milvus applies `filter_expression` BEFORE vector search
   - Reduces search space significantly
   - Example: 100,000 documents → 5,000 after filter → 5 results

2. **Prefix Matching:**
   - `LIKE 'path%'` is optimized for VARCHAR indices
   - Much faster than substring matching (`LIKE '%path%'`)
   - Index scan instead of full table scan

3. **Limit Control:**
   - Frontend specifies `search_limit` (default: 5)
   - Reduces data transfer and processing time
   - Balances result quality vs. performance

#### C. Caching Strategy

- **Frontend Caching**: `hierarchical_paths` response cached in component state
- **No Repeated Queries**: Folder structure loaded once per session
- **Invalidation**: Only refreshed when new documents are processed
- **Result Caching**: Search results cached temporarily for test searches

### Error Handling & Security

#### A. Empty Filter

```python
if not content_filter:
    return ""  # No filtering, search all documents
```

#### B. Invalid Filter Format

```python
if not content_filter.startswith('folder_') and not content_filter.startswith('file_'):
    logger.warning(f"Unknown filter format: {content_filter}")
    return ""  # Fail gracefully, search all documents
```

#### C. SQL Injection Prevention

```python
# Escape single quotes in user input
escaped_path = folder_path.replace("'", "''")
filter_expr = f"hierarchical_path like '{escaped_path}%'"

# Example:
# Input: "Reports/O'Reilly"
# Escaped: "Reports/O''Reilly"
# Expression: "hierarchical_path like 'Reports/O''Reilly%'"
```

#### D. Access Control

```python
# Verify project access before search
project = get_object_or_404(IntelliDocProject, project_id=project_id)
if project.created_by != request.user:
    return Response({'error': 'Access denied'}, status=403)
```

#### E. No Results Handling

```python
if len(search_results) == 0:
    return {
        'success': True,
        'results': [],
        'message': 'No documents found matching filter criteria',
        'suggestions': [
            'Try removing content filter to search all documents',
            'Verify folder path is correct',
            'Check if documents exist in the selected folder'
        ]
    }
```

### Frontend Integration

**Complete Data Flow:**

```typescript
// 1. Load hierarchical paths on component mount
const response = await api.get(`/agent-orchestration/docaware/hierarchical_paths/?project_id=${projectId}`);
hierarchicalPaths = response.data.hierarchical_paths;

// 2. User selects folder from dropdown
<select bind:value={nodeConfig.content_filter}>
  <option value="">All project files (no filter)</option>
  {#each hierarchicalPaths as folder}
    <option value={folder.id}>📁 {folder.displayName}</option>
  {/each}
</select>

// 3. Test search with selected filter
const result = await docAwareService.testSearch(
  projectId,
  searchMethod,
  searchParameters,
  query,
  nodeConfig.content_filter  // ← e.g., "folder_Reports/Financial"
);

// 4. Display results with filter confirmation
{#if nodeConfig.content_filter}
  <div class="bg-green-100 rounded p-2">
    <strong>Filter Active:</strong>
    DocAware will only search documents in folder:
    <strong>{selectedFolder.displayName}</strong>
  </div>
{/if}
```

### Key Files Reference

**Backend:**
- `backend/agent_orchestration/docaware_views.py` - API endpoints
- `backend/agent_orchestration/docaware/service.py` - Main RAG service (lines 51-920)
- `backend/agent_orchestration/docaware/search_methods.py` - Search method configurations
- `backend/vector_search/database.py` - Milvus collection management (lines 145-259)
- `backend/vector_search/enhanced_hierarchical_processor.py` - Path generation (line 609)

**Frontend:**
- `frontend/my-sveltekit-app/src/lib/services/docAwareService.ts` - Frontend service
- `frontend/my-sveltekit-app/src/lib/components/NodePropertiesPanel.svelte` - Content Filter UI (lines 1181-1231, 1420-1470)
- `frontend/my-sveltekit-app/src/lib/components/AgentOrchestrationInterface.svelte` - Hierarchical paths loading (lines 243-272)

### Summary

✅ **hierarchical_path** field enables folder-based document filtering
✅ **Content Filter** translates to Milvus `LIKE` expressions for efficient prefix matching
✅ **All 7 search methods** support content filtering via `filter_expression` parameter
✅ **Folder hierarchy** automatically extracted from document paths with parent folder support
✅ **Performance** optimized via VARCHAR indices and filter-first query strategy
✅ **Security** includes SQL injection prevention and access control
✅ **Flexibility** allows filtering at any level of the folder hierarchy

The implementation provides **targeted, efficient RAG searches** by scoping vector similarity to specific document subsets based on hierarchical folder structure.
