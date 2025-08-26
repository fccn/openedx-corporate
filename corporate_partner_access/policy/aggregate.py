# corporate_partner_access/policy/aggregate.py
"""
Minimal aggregation for Flexible Catalog:
- Fetch ALL FlexibleCatalogModel subclasses.
- Call each catalog.get_course_runs() (eligibility is enforced inside each catalog via CRUM).
- Return the union as course IDs or a CourseOverview queryset.

This keeps all eligibility inside each catalog's get_course_runs() and does not
add any extra policy logic here.
"""

from __future__ import annotations

import logging
from typing import Set

from crum import get_current_user
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache

from corporate_partner_access.edxapp_wrapper.course_module import course_overview
from flex_catalog.models import FlexibleCatalogModel

logger = logging.getLogger(__name__)
CourseOverview = course_overview()

DEFAULT_CACHE_TTL = getattr(settings, "FLEXCATALOG_ALLOWED_IDS_TTL", 90)


def _current_user():
    """
    Return the current user using CRUM; fall back to AnonymousUser so callers
    can rely on user.is_authenticated without extra None checks.
    """
    try:
        user = get_current_user()
    except Exception:
        user = None
    if user and getattr(user, "is_authenticated", False):
        return user
    return AnonymousUser()


def allowed_course_ids_for_current_user(skip_cache: bool = False) -> Set[str]:
    """
    Iterate ALL catalogs, call get_course_runs() on each (eligibility inside),
    and return the union of course IDs. Short cache to avoid recomputation.
    """
    user = _current_user()
    cache_key = f"flex_allowed_ids:v1:{'anon' if not user.is_authenticated else user.id}"

    if not skip_cache:
        cached = cache.get(cache_key)
        if cached is not None:
            return set(cached)

    ids: Set[str] = set()
    catalogs = FlexibleCatalogModel.objects.select_subclasses().distinct()

    for catalog in catalogs:
        try:
            ids.update(catalog.get_course_runs().values_list("id", flat=True))
        except Exception:
            logger.exception("get_course_runs() failed for catalog %r", catalog)

    cache.set(cache_key, list(ids), DEFAULT_CACHE_TTL)
    return ids


def allowed_courses_qs_for_current_user(skip_cache: bool = False):
    """
    Convenience queryset for templates/endpoints that need CourseOverview objects.
    """
    ids = allowed_course_ids_for_current_user(skip_cache=skip_cache)
    if not ids:
        return CourseOverview.objects.none()
    return CourseOverview.objects.filter(id__in=ids)
