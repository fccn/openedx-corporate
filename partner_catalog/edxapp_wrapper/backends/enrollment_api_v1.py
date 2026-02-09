"""Enrollment API v1 backend wrapper."""

from typing import Any, Dict, List, Optional

# pylint: disable=import-error
from openedx.core.djangoapps.enrollments.api import add_enrollment as api_add_enrollment
from openedx.core.djangoapps.enrollments.api import get_enrollment as api_get_enrollment
from openedx.core.djangoapps.enrollments.api import update_enrollment as api_update_enrollment


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


def get_enrollment(
    *,
    username,
    course_id,
):
    """
    Retrieves the enrollment for a specific user and course.

    Args:
        username: The username of the user.
        course_id: The course key identifying the course.

    Returns:
        The enrollment object if found, None otherwise.
    """
    enrollment = api_get_enrollment(
        username=username,
        course_id=course_id,
    )
    return enrollment


def update_enrollment(
    *,
    username,
    course_id,
    mode: Optional[str] = None,
    is_active: Optional[bool] = None,
    enrollment_attributes: Optional[List[Dict[str, Any]]] = None,
):
    """
    Update an existing enrollment for a user and course.

    Args:
        username: The username of the learner.
        course_id: The course key identifying the course.
        mode: Optional new enrollment mode.
        is_active: Optional flag to activate/deactivate the enrollment.
        enrollment_attributes: Optional list of extra attributes.

    Returns:
        The updated enrollment object returned by the enrollment API.
    """
    enrollment = api_update_enrollment(
        username=username,
        course_id=course_id,
        mode=mode,
        is_active=is_active,
        enrollment_attributes=enrollment_attributes,
    )
    return enrollment
