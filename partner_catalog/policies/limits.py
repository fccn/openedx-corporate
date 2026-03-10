"""Policies for checking catalog enrollment limits."""

from partner_catalog.edxapp_wrapper.student_module import available_modes
from partner_catalog.models import CatalogCourseEnrollment, CatalogLearner

OPEN_ENROLLMENT_MODES = frozenset({"audit", "honor"})


def can_consume_user_limit(*, catalog) -> bool:
    """
    Return True if the catalog has remaining active-learner quota.

    A zero or null limit means "unlimited".
    """
    if getattr(catalog, "user_limit", 0) in (0, None):
        return True

    used = CatalogLearner.objects.filter(catalog_id=catalog.id, active=True).count()
    return used < catalog.user_limit


def is_paid_course(*, course_overview_id) -> bool:
    """
    Return True when the course exposes at least one non-open enrollment mode.
    """
    modes = {
        (slug or "").strip().lower()
        for slug in (available_modes(course_overview_id) or [])
        if slug
    }
    return bool(modes - OPEN_ENROLLMENT_MODES)


def can_consume_course_limit(*, catalog) -> bool:
    """
    Return True if the catalog has remaining paid-enrollment bag quota.

    A zero or null limit means "unlimited".
    """
    if getattr(catalog, "course_enrollments_limit", 0) in (0, None):
        return True

    enrolled_course_ids = list(
        CatalogCourseEnrollment.objects.filter(
            catalog_course__catalog_id=catalog.id,
        ).values_list("course_overview_id", flat=True).distinct()
    )
    paid_course_ids = [
        course_overview_id
        for course_overview_id in enrolled_course_ids
        if is_paid_course(course_overview_id=course_overview_id)
    ]

    # This is a "bag" of paid licenses consumed by first ownership catalog.
    used = CatalogCourseEnrollment.objects.filter(
        catalog_course__catalog_id=catalog.id,
        course_overview_id__in=paid_course_ids,
    ).count()
    return used < catalog.course_enrollments_limit
