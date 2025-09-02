"""
Factory functions to access CourseEnrollment/CourseMode and stable operations
(e.g., enroll_user) via a pluggable backend.
"""

from importlib import import_module

from django.conf import settings


def _backend():
    """Return the backend module for student module operations."""
    path = getattr(
        settings,
        "STUDENT_MODULE_BACKEND",
        "corporate_partner_access.edxapp_wrapper.backends.student_module_v1",
    )
    return import_module(path)


def course_enrollment_model():
    """Return the CourseEnrollment model class."""
    return _backend().course_enrollment_model()


def course_mode_model():
    """Return the CourseMode model class."""
    return _backend().course_mode_model()


def enroll_user(*, user, course_key, mode=None, check_access=False):
    """
    Idempotent enroll operation. Backend hides signature/path differences between releases.
    """
    return _backend().enroll_user(
        user=user, course_key=course_key, mode=mode, check_access=check_access
    )


def available_modes(course_key):
    """
    Return a list of available mode slugs (e.g., ['audit', 'verified']) for the course.
    """
    return _backend().available_modes(course_key)
