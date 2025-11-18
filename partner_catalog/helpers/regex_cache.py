"""
Utilities for caching and compiling email regex patterns for corporate partner catalogs.

This module provides functions to retrieve and cache compiled regular expressions
associated with each catalog, used for matching user emails against catalog-specific
patterns. It also provides a cache clearing utility for use in signal handlers or
administrative actions.
"""

import logging
from threading import RLock

import regex
from cachetools import LRUCache, cached
from django.apps import apps

logger = logging.getLogger(__name__)

_regex_cache = LRUCache(maxsize=1024)
_cache_lock = RLock()


@cached(cache=_regex_cache, lock=_cache_lock)
def compiled_email_regexes_for_catalog(catalog_id: str):
    """
    Retrieve and cache compiled email regex patterns for a given catalog.

    Args:
        catalog_id: The ID of the catalog whose email regex patterns to retrieve.

    Returns:
        Tuple of compiled regex patterns (case-insensitive) for the catalog.

    Notes:
        - Results are cached for performance.
        - Invalid regex patterns are skipped.
    """
    CatalogEmailRegex = apps.get_model('partner_catalog', 'CatalogEmailRegex')
    patterns = (CatalogEmailRegex.objects
                .filter(catalog_id=catalog_id)
                .values_list("regex", flat=True))
    compiled = []
    for pattern in patterns:
        try:
            compiled.append(regex.compile(pattern, flags=regex.IGNORECASE))
        except regex.error:
            continue
    return tuple(compiled)


def clear_email_regex_cache(catalog_id: str | None = None):
    """
    Clear the cache of compiled email regex patterns.

    Args:
        catalog_id: If provided, only clears cache for this specific catalog.
                   If None, clears cache for all catalogs.

    This function should be called when email regex patterns are added, updated,
    or deleted for any catalog, to ensure that subsequent lookups use the latest
    patterns from the database.

    """
    with _cache_lock:
        if catalog_id is not None:
            _regex_cache.pop((catalog_id,), None)
        else:
            _regex_cache.clear()
