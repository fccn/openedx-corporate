"""Throttles for the partner catalog API."""

from rest_framework.throttling import UserRateThrottle


class CourseLoadFailuresThrottle(UserRateThrottle):
    """
    Limit how often one user can report courses that failed to load.

    Each accepted report writes one log entry, so this caps the entries a user can write.
    The rate is set here rather than in ``DEFAULT_THROTTLE_RATES``, so no LMS setting is needed.
    """

    scope = "partner_catalog_course_load_failures"
    rate = "30/hour"
