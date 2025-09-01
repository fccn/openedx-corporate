"""
Utilities for caching and compiling email regex patterns for corporate partner catalogs.

This module provides functions to retrieve and cache compiled regular expressions
associated with each catalog, used for matching user emails against catalog-specific
patterns. It also provides a cache clearing utility for use in signal handlers or
administrative actions.
"""

from __future__ import annotations

import functools

import regex
from django.apps import apps


@functools.lru_cache(maxsize=1024)
def compiled_email_regexes_for_catalog(catalog_id: int):
    """
    Retrieve and cache compiled email regex patterns for a given catalog.

    Args:
        catalog_id: The ID of the catalog whose email regex patterns to retrieve.

    Returns:
        Tuple of compiled regex patterns (case-insensitive) for the catalog.
        Patterns are anchored with ^ and $ if not already present.

    Notes:
        - Results are cached for performance.
        - Invalid regex patterns are skipped.
    """
    CatalogEmailRegex = apps.get_model(
        'corporate_partner_access', 'CorporatePartnerCatalogEmailRegex'
    )
    patterns = (CatalogEmailRegex.objects
                .filter(catalog_id=catalog_id)
                .values_list("regex", flat=True))
    compiled = []
    for p in patterns:
        try:
            anchored = p if p.startswith("^") or p.endswith("$") else f"^{p}$"
            compiled.append(regex.compile(anchored, flags=regex.IGNORECASE))
        except regex.error:
            continue
    return tuple(compiled)


def clear_email_regex_cache():
    """
    Clear the cache of compiled email regex patterns for all catalogs.

    This function should be called when email regex patterns are added, updated,
    or deleted for any catalog, to ensure that subsequent lookups use the latest
    patterns from the database.

    Typical use cases include signal handlers for model changes or administrative
    actions that modify catalog email regexes.
    """
    compiled_email_regexes_for_catalog.cache_clear()
