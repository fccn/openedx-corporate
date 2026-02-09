"""Policies for checking catalog enrollment limits."""
from partner_catalog.models import CatalogCourseEnrollment


def can_consume_user_limit(*, catalog) -> bool:
    """
    Return True if the catalog has remaining user-level quota.

    A zero or null limit means "unlimited".
    """
    if getattr(catalog, "user_limit", 0) in (0, None):
        return True
    used = (
        CatalogCourseEnrollment.objects
        .filter(active=True, catalog_course__catalog_id=catalog.id)
        .values("user_id").distinct().count()
    )
    return used < catalog.user_limit


def can_consume_course_limit(*, catalog, course_overview_id) -> bool:
    """
    Return True if the catalog has remaining per-course enrollment quota.

    A zero or null limit means "unlimited".
    """
    if getattr(catalog, "course_enrollments_limit", 0) in (0, None):
        return True
    used = (
        CatalogCourseEnrollment.objects
        .filter(
            active=True,
            catalog_course__catalog_id=catalog.id,
            course_overview_id=course_overview_id,
        )
        .count()
    )
    return used < catalog.course_enrollments_limit
