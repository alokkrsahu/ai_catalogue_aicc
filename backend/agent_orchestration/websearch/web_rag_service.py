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
import time
from typing import Dict, List, Any, Optional, Tuple

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger('agent_orchestration')

# Lazy-loaded singletons (expensive to init)
_embedding_service = None
_milvus_healthy_until: Optional[float] = None  # monotonic deadline, None = unknown/unhealthy
_MILVUS_HEALTH_TTL = 60  # seconds — how long to trust a positive health check

# Collection handle cache — Milvus Collection is cheap to re-open but avoids
# utility.has_collection + col.load() round-trips on every call.
_collection_cache: Dict[str, Any] = {}

VECTOR_DIM = 384  # all-MiniLM-L6-v2
MAX_CHUNK_CHARS = 2000
MIN_CHUNK_CHARS = 20
INDEX_FLAG_PREFIX = "websearch_milvus_idx_"

# Milvus expression size is capped; chunk URL-hash delete lists above this.
_MAX_HASHES_PER_DELETE = 500


def _milvus_connection_params(timeout: int = 10) -> dict:
    """Build Milvus connection kwargs, including auth if configured."""
    params = {
        'alias': 'default',
        'host': getattr(settings, 'MILVUS_HOST', 'localhost'),
        'port': getattr(settings, 'MILVUS_PORT', '19530'),
        'timeout': timeout,
    }
    milvus_user = getattr(settings, 'MILVUS_USER', None)
    milvus_password = getattr(settings, 'MILVUS_PASSWORD', None)
    if milvus_user and milvus_password:
        params['user'] = milvus_user
        params['password'] = milvus_password
    return params


def _get_embedding_service():
    """Lazy-load the shared embedding service singleton."""
    global _embedding_service
    if _embedding_service is None:
        from ..docaware.embedding_service import DocAwareEmbeddingService
        _embedding_service = DocAwareEmbeddingService()
    return _embedding_service


def _invalidate_milvus_caches():
    """Drop Milvus-related process caches. Call on any MilvusException."""
    global _milvus_healthy_until
    _milvus_healthy_until = None
    _collection_cache.clear()


def _check_milvus() -> bool:
    """
    Check if Milvus is reachable. Result is cached for _MILVUS_HEALTH_TTL seconds
    on success; on failure the cache is invalidated so the next call retries.
    """
    global _milvus_healthy_until
    now = time.monotonic()
    if _milvus_healthy_until is not None and now < _milvus_healthy_until:
        return True
    try:
        from pymilvus import connections, utility
        params = _milvus_connection_params(timeout=5)
        alias = params['alias']
        connected = any(c[0] == alias and c[1] for c in connections.list_connections())
        if not connected:
            connections.connect(**params)
        utility.list_collections(using=alias)
        _milvus_healthy_until = now + _MILVUS_HEALTH_TTL
        return True
    except Exception as e:
        logger.warning(f"⚠️ WEB RAG: Milvus not available — falling back to full content: {e}")
        _invalidate_milvus_caches()
        return False


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
    """Create (or open) the websearch Milvus collection for a project. Cached per-process."""
    cached = _collection_cache.get(str(project_id))
    if cached is not None:
        return cached

    from pymilvus import (
        Collection, CollectionSchema, FieldSchema, DataType, utility, connections,
    )

    name = _collection_name(project_id)
    alias = "default"

    # Ensure connected (check address is non-empty — alias can exist without active connection)
    params = _milvus_connection_params(timeout=10)
    connected = any(c[0] == alias and c[1] for c in connections.list_connections())
    if not connected:
        connections.connect(**params)

    if utility.has_collection(name, using=alias):
        col = Collection(name, using=alias)
        col.load()
        _collection_cache[str(project_id)] = col
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
    _collection_cache[str(project_id)] = col
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
    # Batch index (the performance hot path)
    # ------------------------------------------------------------------

    async def index_urls_batch(
        self,
        items: List[Tuple[str, Dict[str, Any]]],
        project_id: str,
        cache_ttl: int = 3600,
    ) -> Dict[str, Any]:
        """
        Chunk, embed, and upsert multiple URLs into Milvus in a single batched
        pipeline. One embed call, one delete, one insert, one flush — regardless
        of how many URLs are passed in. Per-URL chunk embeddings are cached in
        Redis and re-used when the Milvus index flag has expired but the URL
        content is still fresh.

        Args:
            items: List of (url, page_capture_dict). Pages with extraction_error
                   are skipped.
            project_id: Per-project scope.
            cache_ttl: TTL for Redis caches (index flag + embedding cache).

        Returns:
            {'indexed': int, 'skipped': int, 'failed': int,
             'timings_ms': {fetch, chunk, embed, milvus, flush, total}}
        """
        from asgiref.sync import sync_to_async
        from .cache_service import WebSearchCacheService

        cache_service = WebSearchCacheService()

        t0 = time.time()
        indexed = 0
        skipped = 0
        failed = 0
        timings: Dict[str, float] = {}

        # 1. Honour the per-URL index flag — skip pages whose flag is still alive.
        flag_keys = {url: _index_flag_key(project_id, url) for url, _ in items}
        try:
            alive_flags = cache.get_many(list(flag_keys.values()))
        except Exception:
            alive_flags = {}
        alive_urls = {url for url, key in flag_keys.items() if alive_flags.get(key)}

        work_items = [(url, page) for url, page in items if url not in alive_urls]
        skipped += len(alive_urls)

        if not work_items:
            timings['total'] = round((time.time() - t0) * 1000, 1)
            return {'indexed': 0, 'skipped': skipped, 'failed': 0, 'timings_ms': timings}

        # 2. Chunk all pages (fast, pure Python).
        t_chunk_start = time.time()
        per_url_chunks: Dict[str, List[Dict[str, Any]]] = {}
        for url, page in work_items:
            if not page or page.get('extraction_error'):
                failed += 1
                continue
            try:
                chunks = _chunk_page_capture(page, url)
            except Exception as e:
                logger.warning(f"⚠️ WEB RAG: chunking failed for {url[:60]}: {e}")
                failed += 1
                continue
            if not chunks:
                # Empty page: still mark as indexed so we don't retry forever.
                try:
                    cache.set(flag_keys[url], 1, timeout=cache_ttl)
                except Exception:
                    pass
                skipped += 1
                continue
            per_url_chunks[url] = chunks
        timings['chunk'] = round((time.time() - t_chunk_start) * 1000, 1)

        if not per_url_chunks:
            timings['total'] = round((time.time() - t0) * 1000, 1)
            return {'indexed': 0, 'skipped': skipped, 'failed': failed, 'timings_ms': timings}

        # 3. Split work into (already-embedded, cached in Redis) vs (needs embed).
        urls_needing_work = list(per_url_chunks.keys())
        cached_embeddings = cache_service.get_cached_embeddings_batch(urls_needing_work, project_id)

        urls_to_embed: List[str] = []
        chunks_needing_embed: List[Dict[str, Any]] = []
        embed_url_index: List[str] = []  # parallel list: which URL each chunk belongs to
        final_chunks_per_url: Dict[str, List[Dict[str, Any]]] = {}

        for url, chunks in per_url_chunks.items():
            cached = cached_embeddings.get(url)
            if cached and len(cached) == len(chunks):
                # Happy path: cached embeddings match current chunk count.
                final_chunks_per_url[url] = cached
                continue
            urls_to_embed.append(url)
            for c in chunks:
                chunks_needing_embed.append(c)
                embed_url_index.append(url)

        # 4. ONE batch_encode call for all uncached chunks — sentence-transformers
        # vectorises internally, so this is 3-5× faster than N small calls.
        t_embed_start = time.time()
        if chunks_needing_embed:
            texts_to_embed = [c['content'] for c in chunks_needing_embed]
            try:
                embeddings = await sync_to_async(_get_embedding_service().batch_encode)(texts_to_embed)
            except Exception as e:
                logger.error(f"❌ WEB RAG: batch embed failed: {e}")
                timings['embed'] = round((time.time() - t_embed_start) * 1000, 1)
                timings['total'] = round((time.time() - t0) * 1000, 1)
                return {
                    'indexed': 0,
                    'skipped': skipped,
                    'failed': failed + len(urls_to_embed),
                    'timings_ms': timings,
                }

            # Redistribute embeddings back to per-URL lists and cache them.
            per_url_new: Dict[str, List[Dict[str, Any]]] = {u: [] for u in urls_to_embed}
            for chunk, emb, url in zip(chunks_needing_embed, embeddings, embed_url_index):
                entry = {**chunk, 'embedding': emb}
                per_url_new[url].append(entry)
            for url, entries in per_url_new.items():
                final_chunks_per_url[url] = entries
                cache_service.cache_embeddings(url, project_id, entries, ttl=cache_ttl)
        timings['embed'] = round((time.time() - t_embed_start) * 1000, 1)

        # 5. Build the flat column-oriented Milvus insert.
        all_embeddings: List[List[float]] = []
        all_content: List[str] = []
        all_url: List[str] = []
        all_url_hash: List[str] = []
        all_title: List[str] = []
        all_heading: List[str] = []
        all_type: List[str] = []
        all_idx: List[int] = []
        all_wc: List[int] = []

        unique_url_hashes: List[str] = []
        for url, entries in final_chunks_per_url.items():
            if not entries:
                continue
            unique_url_hashes.append(entries[0].get('url_hash') or _url_hash(url))
            for e in entries:
                all_embeddings.append(e['embedding'])
                all_content.append(e['content'])
                all_url.append(e.get('url', url)[:2048])
                all_url_hash.append(e.get('url_hash') or _url_hash(url))
                all_title.append(e.get('title', ''))
                all_heading.append(e.get('section_heading', ''))
                all_type.append(e.get('section_type', 'other'))
                all_idx.append(int(e.get('chunk_index', 0)))
                all_wc.append(int(e.get('word_count', 0)))

        if not all_content:
            timings['total'] = round((time.time() - t0) * 1000, 1)
            return {'indexed': 0, 'skipped': skipped, 'failed': failed, 'timings_ms': timings}

        # 6. Milvus: ONE delete, ONE insert, ONE flush.
        t_milvus_start = time.time()
        try:
            col = await sync_to_async(_get_or_create_collection)(project_id)

            # Delete in chunks to respect Milvus expression size limit.
            unique_url_hashes = list({h for h in unique_url_hashes if h})
            for i in range(0, len(unique_url_hashes), _MAX_HASHES_PER_DELETE):
                batch = unique_url_hashes[i:i + _MAX_HASHES_PER_DELETE]
                expr = 'url_hash in [' + ','.join(f'"{h}"' for h in batch) + ']'
                await sync_to_async(col.delete)(expr)

            await sync_to_async(col.insert)([
                all_embeddings, all_content, all_url, all_url_hash,
                all_title, all_heading, all_type, all_idx, all_wc,
            ])
            timings['milvus'] = round((time.time() - t_milvus_start) * 1000, 1)

            t_flush_start = time.time()
            await sync_to_async(col.flush)()
            timings['flush'] = round((time.time() - t_flush_start) * 1000, 1)

        except Exception as e:
            logger.error(f"❌ WEB RAG: Milvus batch index failed: {e}")
            _invalidate_milvus_caches()
            timings['milvus'] = round((time.time() - t_milvus_start) * 1000, 1)
            timings['total'] = round((time.time() - t0) * 1000, 1)
            return {
                'indexed': 0,
                'skipped': skipped,
                'failed': failed + len(final_chunks_per_url),
                'timings_ms': timings,
            }

        # 7. Set all index flags in one MSET.
        try:
            cache.set_many(
                {flag_keys[url]: 1 for url in final_chunks_per_url.keys()},
                timeout=cache_ttl,
            )
        except Exception as e:
            logger.warning(f"⚠️ WEB RAG: set_many flags failed: {e}")

        indexed = len(final_chunks_per_url)
        timings['total'] = round((time.time() - t0) * 1000, 1)
        logger.info(
            f"🌐 WEB RAG: Batch indexed {indexed} URLs, {len(all_content)} chunks "
            f"(project {str(project_id)[:8]}) — {timings}"
        )
        return {
            'indexed': indexed,
            'skipped': skipped,
            'failed': failed,
            'timings_ms': timings,
        }

    # ------------------------------------------------------------------
    # Single-URL wrapper (preserved for backward compat)
    # ------------------------------------------------------------------

    async def ensure_indexed(
        self,
        url: str,
        page_capture: Dict[str, Any],
        project_id: str,
        cache_ttl: int = 2592000,
    ) -> bool:
        """
        Thin wrapper around index_urls_batch for single-URL callers.
        Returns True if newly indexed, False if already up-to-date or failed.
        """
        flag_key = _index_flag_key(project_id, url)
        if cache.get(flag_key):
            return False
        result = await self.index_urls_batch(
            [(url, page_capture)], project_id, cache_ttl=cache_ttl
        )
        return result['indexed'] > 0

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
            _invalidate_milvus_caches()
            return []

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    async def get_indexed_urls(self, project_id: str) -> List[str]:
        """Return distinct URLs currently indexed in the project's Milvus collection."""
        from asgiref.sync import sync_to_async
        try:
            from pymilvus import utility, connections
            params = _milvus_connection_params(timeout=10)
            alias = params['alias']
            connected = any(c[0] == alias and c[1] for c in connections.list_connections())
            if not connected:
                connections.connect(**params)

            name = _collection_name(project_id)
            if not await sync_to_async(utility.has_collection)(name, using=alias):
                return []

            col = await sync_to_async(_get_or_create_collection)(project_id)
            results = await sync_to_async(col.query)(
                expr="word_count >= 0",
                output_fields=["url"],
                limit=16384,
            )
            return list({r['url'] for r in results})
        except Exception as e:
            logger.warning(f"⚠️ WEB RAG: Failed to get indexed URLs: {e}")
            _invalidate_milvus_caches()
            return []

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    async def remove_url(self, url: str, project_id: str):
        """Delete all Milvus chunks for a single URL. No flush — applies lazily."""
        from asgiref.sync import sync_to_async
        from .cache_service import WebSearchCacheService

        cache_service = WebSearchCacheService()
        try:
            col = await sync_to_async(_get_or_create_collection)(project_id)
            uh = _url_hash(url)
            await sync_to_async(col.delete)(f'url_hash == "{uh}"')
            cache.delete(_index_flag_key(project_id, url))
            cache_service.invalidate_embeddings(url, project_id)
            logger.info(f"🌐 WEB RAG: Removed chunks for {url[:60]}")
        except Exception as e:
            logger.warning(f"⚠️ WEB RAG: Failed to remove URL chunks: {e}")
            _invalidate_milvus_caches()

    async def clear_project(self, project_id: str):
        """Drop the entire websearch collection for a project."""
        from asgiref.sync import sync_to_async
        try:
            from pymilvus import utility, connections
            params = _milvus_connection_params(timeout=10)
            alias = params['alias']
            connected = any(c[0] == alias and c[1] for c in connections.list_connections())
            if not connected:
                connections.connect(**params)

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
        finally:
            _collection_cache.pop(str(project_id), None)
