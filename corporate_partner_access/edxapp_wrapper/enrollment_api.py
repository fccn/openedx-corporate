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
        "corporate_partner_access.edxapp_wrapper.backends.enrollment_api_v1",
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
