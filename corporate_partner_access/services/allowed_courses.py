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
    """
    Service class for determining which course runs a user is allowed to see for a specific catalog.

    This class provides static methods to:
      - Retrieve a queryset of course runs visible to a user for a given catalog,
        based on catalog visibility and user eligibility policies.
      - Retrieve a list of course run IDs the user is allowed to access for a catalog.

    All logic is policy-driven and does not use selectors; it operates directly on catalog.courses.
    """

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
