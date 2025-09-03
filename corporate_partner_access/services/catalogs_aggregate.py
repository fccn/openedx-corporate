"""
Service: Aggregate allowed courses across ALL FlexibleCatalogModel subclasses.

- Iterates all FlexibleCatalogModel subclasses.
- Calls catalog.get_course_runs() (eligibility resolved inside each catalog).
- Aggregates course IDs across catalogs.
- Uses short cache per-user for performance.
"""

from __future__ import annotations

import logging
from typing import Set

from django.conf import settings
from django.core.cache import cache

from corporate_partner_access.edxapp_wrapper.course_module import course_overview
from corporate_partner_access.helpers.current_user import safe_get_current_user
from flex_catalog.models import FlexibleCatalogModel

logger = logging.getLogger(__name__)
CourseOverview = course_overview()

DEFAULT_CACHE_TTL = getattr(settings, "FLEXCATALOG_ALLOWED_IDS_TTL", 90)


def allowed_course_ids_for_current_user(skip_cache: bool = False) -> Set[str]:
    """
    Return a set of allowed course IDs for the current user.

    Args:
        skip_cache (bool): If True, bypass the cache and recompute the allowed course IDs.

    Returns:
        Set[str]: A set of course ID strings the current user is allowed to access.
    """
    user = safe_get_current_user()
    cache_key = f"flex_allowed_ids:v1:{'anon' if not user.is_authenticated else user.id}"

    if not skip_cache:
        cached = cache.get(cache_key)
        if cached is not None:
            return set(cached)

    ids: Set[str] = set()
    catalogs = FlexibleCatalogModel.objects.select_subclasses().distinct()

    # pylint: disable=broad-exception-caught
    for catalog in catalogs:
        try:
            qs = catalog.get_course_runs()
            ids.update(qs.values_list("id", flat=True))
        except Exception:  # noqa: BLE001  # we want to continue even if one catalog fails
            logger.exception("get_course_runs() failed for catalog %r", catalog)
    # pylint: enable=broad-exception-caught

    cache.set(cache_key, list(ids), DEFAULT_CACHE_TTL)
    return ids


def allowed_courses_qs_for_current_user(skip_cache: bool = False):
    """
    Return a queryset of allowed CourseOverview objects for the current user.

    This method filters CourseOverview objects to only those courses the current user is allowed to access,
    as determined by aggregating allowed course IDs across all FlexibleCatalogModel subclasses.

    Args:
        skip_cache (bool): If True, bypass the cache and recompute the allowed course IDs.

    Returns:
        QuerySet: A queryset of CourseOverview objects the current user is allowed to access.
    """
    ids = allowed_course_ids_for_current_user(skip_cache=skip_cache)
    if not ids:
        return CourseOverview.objects.none()
    return CourseOverview.objects.filter(id__in=ids)
