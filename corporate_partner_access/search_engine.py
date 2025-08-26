"""
Flexible Catalog Compatible Search Engine.

This adapter delegates to the real search engine (Meili, ES, etc.) and then
post-filters results to include only courses visible to the current user
(according to Flexible Catalog policies).

Configuration:
    SEARCH_ENGINE = "corporate_partner_access.search_engine.FlexibleCatalogCompatibleSearchEngine"

Optional:
    FLEXCATALOG_UNDERLYING_SEARCH_ENGINE = "search.meilisearch.MeilisearchEngine"
"""

from __future__ import annotations

from copy import deepcopy
from importlib import import_module
from typing import Any, Dict, List, Optional

from django.conf import settings
from opaque_keys.edx.keys import CourseKey
from search.search_engine_base import SearchEngine  # third-party import before first-party

from corporate_partner_access.policy.aggregate import allowed_courses_qs_for_current_user


def _load_engine_class() -> type:
    """
    Load the underlying engine class from settings.

    Default: Meilisearch.
    """
    path = getattr(
        settings,
        "FLEXCATALOG_UNDERLYING_SEARCH_ENGINE",
        "search.meilisearch.MeilisearchEngine",
    )
    module_path, class_name = path.rsplit(".", 1)
    module = import_module(module_path)
    return getattr(module, class_name)


_ENGINE_CLS = _load_engine_class()


def _extract_candidate_key(item: Dict[str, Any]) -> Optional[CourseKey]:
    """
    Extract a course identifier from a search item and normalize to CourseKey.

    Supported structures: item["data"]["id"], item["data"]["course"], item["_id"].
    """
    data = item.get("data") or {}
    raw = data.get("id") or data.get("course") or item.get("_id")
    if not raw:
        return None

    if isinstance(raw, CourseKey):
        return raw
    if isinstance(raw, str):
        try:
            return CourseKey.from_string(raw)
        except Exception:  # pylint: disable=broad-exception-caught
            return None
    return None


class FlexibleCatalogCompatibleSearchEngine(SearchEngine):
    """
    Adapter that delegates to the real engine and filters by allowed CourseKeys.

    The engine first executes the underlying search, then results are filtered
    so that only courses visible to the current user are returned.
    """

    def __init__(self, index: Optional[str] = None):
        """Initialize the adapter with the selected index and underlying engine."""
        super().__init__(index=index)
        self._engine: SearchEngine = _ENGINE_CLS(index=index)

    # -----------------------------------------------------------------------
    # Direct proxy methods (keep names/signatures as-is)
    # -----------------------------------------------------------------------

    def index(self, sources, **kwargs):
        """Delegate to the underlying engine."""
        return self._engine.index(sources, **kwargs)

    def remove(self, doc_ids, **kwargs):
        """Delegate to the underlying engine."""
        return self._engine.remove(doc_ids, **kwargs)

    # -----------------------------------------------------------------------
    # Search + post-filter by allowed courses
    # -----------------------------------------------------------------------

    def search(  # pylint: disable=too-many-positional-arguments
        self,
        query_string: Optional[str] = None,
        field_dictionary: Optional[Dict[str, Any]] = None,
        filter_dictionary: Optional[Dict[str, Any]] = None,
        exclude_dictionary: Optional[Dict[str, Any]] = None,
        aggregation_terms: Optional[List[str]] = None,
        log_search_params: bool = False,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Run the underlying engine and filter results to keep only allowed courses.

        The original return structure is preserved, including "results",
        "total", and "max_score".
        """
        raw = self._engine.search(
            query_string=query_string,
            field_dictionary=field_dictionary,
            filter_dictionary=filter_dictionary,
            exclude_dictionary=exclude_dictionary,
            aggregation_terms=aggregation_terms,
            log_search_params=log_search_params,
            **kwargs,
        )

        # Visible CourseKeys for the current user
        allowed_keys = set(
            allowed_courses_qs_for_current_user().values_list("id", flat=True)
        )

        results = deepcopy(raw)
        items = results.get("results") or []

        filtered: List[Dict[str, Any]] = []
        max_score = results.get("max_score", 0) or 0

        for item in items:
            ck = _extract_candidate_key(item)
            if ck and ck in allowed_keys:
                filtered.append(item)
                item_score = item.get("score") or 0
                max_score = max(max_score, item_score)

        results["results"] = filtered
        results["total"] = len(filtered)
        results["max_score"] = max_score

        return results
