"""
Factory functions to access CourseEnrollment/CourseMode and stable operations
(e.g., enroll_user) via a pluggable backend.
"""

from importlib import import_module
from typing import Any, Dict, List, Optional

from django.conf import settings


def _backend():
    """Return the backend module for student module operations."""
    path = getattr(
        settings,
        "ENROLLMENT_API_BACKEND",
        "partner_catalog.edxapp_wrapper.backends.enrollment_api_v1",
    )
    return import_module(path)


def add_enrollment(
    *,
    username,
    course_id,
    mode: Optional[str] = None,
    enrollment_attributes: Optional[List[Dict[str, Any]]] = None,
):
    """
    Idempotent enroll operation. Backend hides signature/path differences between releases.
    """
    return _backend().add_enrollment(
        username=username, course_id=course_id, mode=mode, enrollment_attributes=enrollment_attributes
    )


def get_enrollment(
    *,
    username,
    course_id,
):
    """
    Retrieve enrollment for a user in a course. Backend hides signature/path differences between releases.
    """
    return _backend().get_enrollment(
        username=username,
        course_id=course_id,
    )


def update_enrollment(
    *,
    username,
    course_id,
    mode: Optional[str] = None,
    is_active: Optional[bool] = None,
    enrollment_attributes: Optional[List[Dict[str, Any]]] = None,
):
    """
    Update an existing enrollment for a user in a course.

    This delegates to the configured backend so that caller code does not
    depend on the concrete LMS implementation or API version.
    """
    return _backend().update_enrollment(
        username=username,
        course_id=course_id,
        mode=mode,
        is_active=is_active,
        enrollment_attributes=enrollment_attributes,
    )
