"""
Web RAG Service
===============

Provides semantic search over cached web URL content using Milvus.
Chunks PageCapture sections → embeds → upserts into a per-project
Milvus collection → searches with user query → returns top-K chunks.
"""

import hashlib
import logging
import re
from typing import Dict, List, Any, Optional

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger('agent_orchestration')

# Lazy-loaded singletons (expensive to init)
_embedding_service = None
_milvus_available = None

VECTOR_DIM = 384  # all-MiniLM-L6-v2
MAX_CHUNK_CHARS = 2000
MIN_CHUNK_CHARS = 20
INDEX_FLAG_PREFIX = "websearch_milvus_idx_"


def _get_embedding_service():
    """Lazy-load the shared embedding service singleton."""
    global _embedding_service
    if _embedding_service is None:
        from ..docaware.embedding_service import DocAwareEmbeddingService
        _embedding_service = DocAwareEmbeddingService()
    return _embedding_service


def _check_milvus():
    """Check if Milvus is reachable (cached result)."""
    global _milvus_available
    if _milvus_available is not None:
        return _milvus_available
    try:
        from pymilvus import connections, utility
        milvus_host = getattr(settings, 'MILVUS_HOST', 'localhost')
        milvus_port = getattr(settings, 'MILVUS_PORT', '19530')
        alias = "default"
        if alias not in [c[0] for c in connections.list_connections()]:
            connections.connect(alias=alias, host=milvus_host, port=milvus_port, timeout=5)
        utility.list_collections(using=alias)
        _milvus_available = True
    except Exception as e:
        logger.warning(f"⚠️ WEB RAG: Milvus not available — falling back to full content: {e}")
        _milvus_available = False
    return _milvus_available


def _collection_name(project_id: str) -> str:
    """Deterministic collection name for a project's web content."""
    safe_pid = str(project_id).replace('-', '_')
    return f"websearch_{safe_pid}"


def _url_hash(url: str) -> str:
    return hashlib.md5(url.encode('utf-8')).hexdigest()


def _index_flag_key(project_id: str, url: str) -> str:
    safe_pid = str(project_id).replace('-', '_')
    return f"{INDEX_FLAG_PREFIX}{safe_pid}_{_url_hash(url)}"


# ---------------------------------------------------------------------------
# Collection management
# ---------------------------------------------------------------------------

def _get_or_create_collection(project_id: str):
    """Create (or open) the websearch Milvus collection for a project."""
    from pymilvus import (
        Collection, CollectionSchema, FieldSchema, DataType, utility, connections,
    )

    name = _collection_name(project_id)
    alias = "default"

    # Ensure connected
    milvus_host = getattr(settings, 'MILVUS_HOST', 'localhost')
    milvus_port = getattr(settings, 'MILVUS_PORT', '19530')
    if alias not in [c[0] for c in connections.list_connections()]:
        connections.connect(alias=alias, host=milvus_host, port=milvus_port, timeout=10)

    if utility.has_collection(name, using=alias):
        col = Collection(name, using=alias)
        col.load()
        return col

    fields = [
        FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
        FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=VECTOR_DIM),
        FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=65535),
        FieldSchema(name="url", dtype=DataType.VARCHAR, max_length=2048),
        FieldSchema(name="url_hash", dtype=DataType.VARCHAR, max_length=32),
        FieldSchema(name="title", dtype=DataType.VARCHAR, max_length=512),
        FieldSchema(name="section_heading", dtype=DataType.VARCHAR, max_length=512),
        FieldSchema(name="section_type", dtype=DataType.VARCHAR, max_length=20),
        FieldSchema(name="chunk_index", dtype=DataType.INT64),
        FieldSchema(name="word_count", dtype=DataType.INT64),
    ]
    schema = CollectionSchema(fields=fields, description=f"WebSearch RAG for project {project_id}")
    col = Collection(name=name, schema=schema, using=alias)

    col.create_index(
        field_name="embedding",
        index_params={"metric_type": "IP", "index_type": "IVF_FLAT", "params": {"nlist": 256}},
    )
    col.create_index(field_name="url_hash")
    col.load()
    logger.info(f"🌐 WEB RAG: Created Milvus collection {name}")
    return col


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

def _chunk_page_capture(page: Dict[str, Any], url: str) -> List[Dict[str, Any]]:
    """
    Convert a PageCapture dict into embedding-ready chunks.

    Each section becomes a chunk. Non-heading sections get the nearest
    preceding heading prepended for context.  Very long sections are
    split at sentence boundaries.
    """
    sections = page.get('sections') or []
    title = (page.get('title') or '')[:500]
    chunks: List[Dict[str, Any]] = []
    current_heading = title  # fallback heading

    for idx, sec in enumerate(sections):
        sec_type = sec.get('type', 'other')
        text = (sec.get('text') or '').strip()
        if not text or len(text) < MIN_CHUNK_CHARS:
            # Update heading even if we skip the section
            if sec_type == 'heading':
                current_heading = text or current_heading
            continue

        if sec_type == 'heading':
            current_heading = text
            # Include heading as its own chunk only if substantial
            if len(text) >= MIN_CHUNK_CHARS:
                chunks.append({
                    'content': text,
                    'section_heading': text[:500],
                    'section_type': sec_type,
                    'chunk_index': idx,
                })
            continue

        # Prepend heading context for non-heading sections
        heading_prefix = f"{current_heading}\n\n" if current_heading else ""

        if len(heading_prefix) + len(text) <= MAX_CHUNK_CHARS:
            chunks.append({
                'content': (heading_prefix + text)[:MAX_CHUNK_CHARS],
                'section_heading': current_heading[:500],
                'section_type': sec_type,
                'chunk_index': idx,
            })
        else:
            # Split long sections at sentence boundaries
            for part in _split_text(text, MAX_CHUNK_CHARS - len(heading_prefix)):
                chunks.append({
                    'content': (heading_prefix + part)[:MAX_CHUNK_CHARS],
                    'section_heading': current_heading[:500],
                    'section_type': sec_type,
                    'chunk_index': idx,
                })

    # Add url / title metadata to every chunk
    uh = _url_hash(url)
    for c in chunks:
        c['url'] = url[:2048]
        c['url_hash'] = uh
        c['title'] = title
        c['word_count'] = len(c['content'].split())

    return chunks


def _split_text(text: str, max_len: int) -> List[str]:
    """Split text at sentence boundaries, keeping each part under max_len."""
    sentences = re.split(r'(?<=[.!?])\s+', text)
    parts: List[str] = []
    current = ""
    for s in sentences:
        if len(current) + len(s) + 1 <= max_len:
            current = f"{current} {s}".strip() if current else s
        else:
            if current:
                parts.append(current)
            current = s[:max_len]  # truncate individual sentence if needed
    if current:
        parts.append(current)
    return parts or [text[:max_len]]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class WebRAGService:
    """Semantic search over cached web URL content via Milvus."""

    def is_available(self) -> bool:
        return _check_milvus()

    # ------------------------------------------------------------------
    # Index
    # ------------------------------------------------------------------

    async def ensure_indexed(
        self,
        url: str,
        page_capture: Dict[str, Any],
        project_id: str,
        cache_ttl: int = 3600,
    ) -> bool:
        """
        Chunk + embed + upsert a PageCapture into Milvus if not already indexed.
        Returns True if newly indexed, False if already up-to-date.
        """
        flag_key = _index_flag_key(project_id, url)
        if cache.get(flag_key):
            return False  # already indexed and flag still alive

        from asgiref.sync import sync_to_async

        chunks = _chunk_page_capture(page_capture, url)
        if not chunks:
            logger.debug(f"🌐 WEB RAG: No chunks for {url[:60]}")
            return False

        try:
            # Embed all chunks
            texts = [c['content'] for c in chunks]
            embeddings = await sync_to_async(_get_embedding_service().batch_encode)(texts)

            # Get or create collection
            col = await sync_to_async(_get_or_create_collection)(project_id)

            # Delete old chunks for this URL (in case content changed)
            uh = _url_hash(url)
            await sync_to_async(col.delete)(f'url_hash == "{uh}"')

            # Prepare insert data (column-oriented for Milvus)
            insert_data = [
                embeddings,                                         # embedding
                [c['content'] for c in chunks],                     # content
                [c['url'] for c in chunks],                         # url
                [c['url_hash'] for c in chunks],                    # url_hash
                [c['title'] for c in chunks],                       # title
                [c['section_heading'] for c in chunks],             # section_heading
                [c['section_type'] for c in chunks],                # section_type
                [c['chunk_index'] for c in chunks],                 # chunk_index
                [c['word_count'] for c in chunks],                  # word_count
            ]

            await sync_to_async(col.insert)(insert_data)
            await sync_to_async(col.flush)()

            # Set index flag with same TTL as the URL cache
            cache.set(flag_key, 1, timeout=cache_ttl)

            logger.info(f"🌐 WEB RAG: Indexed {len(chunks)} chunks for {url[:60]} (project {str(project_id)[:8]})")
            return True

        except Exception as e:
            logger.error(f"❌ WEB RAG: Failed to index {url[:60]}: {e}")
            return False

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    async def search(
        self,
        query: str,
        project_id: str,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Embed the query and search the websearch Milvus collection.
        Returns top-K chunks with content, url, section_heading, score.
        """
        from asgiref.sync import sync_to_async

        try:
            query_embedding = await sync_to_async(_get_embedding_service().encode_query)(query)

            col = await sync_to_async(_get_or_create_collection)(project_id)

            results = await sync_to_async(col.search)(
                data=[query_embedding],
                anns_field="embedding",
                param={"metric_type": "IP", "params": {"nprobe": 16}},
                limit=top_k,
                output_fields=["content", "url", "title", "section_heading", "section_type", "word_count"],
            )

            chunks = []
            for hit in results[0]:
                chunks.append({
                    'content': hit.entity.get('content', ''),
                    'url': hit.entity.get('url', ''),
                    'title': hit.entity.get('title', ''),
                    'section_heading': hit.entity.get('section_heading', ''),
                    'section_type': hit.entity.get('section_type', ''),
                    'word_count': hit.entity.get('word_count', 0),
                    'score': round(hit.score, 4),
                })

            logger.info(f"🌐 WEB RAG: Found {len(chunks)} chunks for query '{query[:50]}...' (project {str(project_id)[:8]})")
            return chunks

        except Exception as e:
            logger.error(f"❌ WEB RAG: Search failed: {e}")
            return []

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    async def remove_url(self, url: str, project_id: str):
        """Delete all Milvus chunks for a single URL."""
        from asgiref.sync import sync_to_async
        try:
            col = await sync_to_async(_get_or_create_collection)(project_id)
            uh = _url_hash(url)
            await sync_to_async(col.delete)(f'url_hash == "{uh}"')
            cache.delete(_index_flag_key(project_id, url))
            logger.info(f"🌐 WEB RAG: Removed chunks for {url[:60]}")
        except Exception as e:
            logger.warning(f"⚠️ WEB RAG: Failed to remove URL chunks: {e}")

    async def clear_project(self, project_id: str):
        """Drop the entire websearch collection for a project."""
        from asgiref.sync import sync_to_async
        try:
            from pymilvus import utility, connections
            alias = "default"
            milvus_host = getattr(settings, 'MILVUS_HOST', 'localhost')
            milvus_port = getattr(settings, 'MILVUS_PORT', '19530')
            if alias not in [c[0] for c in connections.list_connections()]:
                connections.connect(alias=alias, host=milvus_host, port=milvus_port, timeout=10)

            name = _collection_name(project_id)
            if await sync_to_async(utility.has_collection)(name, using=alias):
                from pymilvus import Collection
                col = Collection(name, using=alias)
                await sync_to_async(col.drop)()
                logger.info(f"🌐 WEB RAG: Dropped collection {name}")
            else:
                logger.debug(f"🌐 WEB RAG: No collection to drop for {name}")
        except Exception as e:
            logger.warning(f"⚠️ WEB RAG: Failed to drop collection: {e}")
