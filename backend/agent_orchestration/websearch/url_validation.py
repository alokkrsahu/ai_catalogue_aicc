"""
Shared URL-list validation helpers for websearch configuration.

Used by the sync-websearch-index and summarize-urls endpoints (and any other
caller that accepts a user-provided URL list). Centralises protocol check,
whitespace trim, order-preserving dedupe, and count cap so the policy is
enforced identically everywhere.
"""
from typing import Iterable, List, Tuple

from django.conf import settings


def get_max_urls_per_agent() -> int:
    """Return the configured per-agent URL cap. Defaults to 100."""
    websearch_config = getattr(settings, 'WEBSEARCH_CONFIG', {})
    try:
        value = int(websearch_config.get('MAX_URLS_PER_AGENT', 100))
    except (TypeError, ValueError):
        value = 100
    return max(1, value)


def clean_url_list(raw: Iterable) -> Tuple[List[str], int, int]:
    """
    Normalise, dedupe (preserve order), and cap a list of user-supplied URLs.

    Returns (urls, dropped_invalid, dropped_over_cap) where:
      - urls:             cleaned URL list, length ≤ MAX_URLS_PER_AGENT
      - dropped_invalid:  entries that failed the http(s) protocol check
      - dropped_over_cap: entries that were trimmed because the list exceeded
                          MAX_URLS_PER_AGENT (post-dedupe)
    """
    max_urls = get_max_urls_per_agent()
    seen = set()
    cleaned: List[str] = []
    dropped_invalid = 0

    for item in (raw or []):
        if not isinstance(item, str):
            dropped_invalid += 1
            continue
        url = item.strip()
        if not url:
            continue
        if not (url.startswith('http://') or url.startswith('https://')):
            dropped_invalid += 1
            continue
        if url in seen:
            continue
        seen.add(url)
        cleaned.append(url)

    if len(cleaned) > max_urls:
        dropped_over_cap = len(cleaned) - max_urls
        cleaned = cleaned[:max_urls]
    else:
        dropped_over_cap = 0

    return cleaned, dropped_invalid, dropped_over_cap
