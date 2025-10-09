"""Enrollment API v1 backend wrapper."""

from typing import Any, Dict, List, Optional

# pylint: disable=import-error
from openedx.core.djangoapps.enrollments.api import add_enrollment as api_add_enrollment


def add_enrollment(
    *,
    username,
    course_id,
    mode: Optional[str] = None,
    enrollment_attributes: Optional[List[Dict[str, Any]]] = None,
):
    """
    Enrolls a user in a course with the specified enrollment mode and optional attributes.

    Args:
        user: The user object to enroll.
        course_key: The course key identifying the course to enroll in.
        mode (Optional[str]): The enrollment mode (e.g., 'audit', 'verified'). Defaults to None.
        enrollment_attributes (Optional[List[Dict[str, Any]]]):
            Additional attributes for the enrollment. Defaults to None.

    Returns:
        The enrollment object returned by the underlying enrollment API.
    """

    enrollment = api_add_enrollment(
        username=username,
        course_id=course_id,
        mode=mode,
        enrollment_attributes=enrollment_attributes or [],
    )
    return enrollment
