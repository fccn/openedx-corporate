"""
Allowed courses service for corporate partner catalogs.

This module provides utilities to determine which course runs a user can see
for a given catalog, including functions to retrieve course run querysets and IDs
based on catalog visibility and user eligibility policies.
"""

from __future__ import annotations

from corporate_partner_access.edxapp_wrapper.course_module import course_overview
from corporate_partner_access.policies.catalogs import can_user_see_catalog_courses


class CatalogAllowedCoursesService:
    @staticmethod
    def course_runs_for_user(*, catalog, user):
        """
        Return a queryset of course runs the user can see for the given catalog.
        No selectors: use catalog.courses directly.
        """
        if can_user_see_catalog_courses(user=user, catalog=catalog):
            return catalog.courses.all()
        return course_overview().objects.none()

    @staticmethod
    def course_run_ids_for_user(*, catalog, user):
        """
        Convenience: get course IDs only (useful for search-engine post-filtering).
        """
        return CatalogAllowedCoursesService.course_runs_for_user(
            catalog=catalog, user=user
        ).values_list("id", flat=True)
