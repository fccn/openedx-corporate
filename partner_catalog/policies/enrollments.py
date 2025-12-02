"""Policy module for catalog courses."""

from django.contrib.auth import get_user_model

from partner_catalog.edxapp_wrapper.enrollment_api import get_enrollment
from partner_catalog.policies.catalogs import is_user_an_active_catalog_learner


def can_user_enroll_in_catalog_course(*, user, catalog_course) -> bool:
    """
    Determine if a user is allowed to enroll in an specific catalog course.

    Args:
        user: The user object to check.
        catalog_course: The catalog course instance to check access against.
    Returns:
        True if the user can enroll in the catalog course, False otherwise.

    Access is granted if:
        - The user is an active learner in the catalog associated.
        - The catalog is currently active.
        - The catalog has remaining course enrollment capacity.
    """

    catalog = catalog_course.catalog
    if not getattr(catalog, "active", False):
        return False

    if not is_user_an_active_catalog_learner(user=user, catalog=catalog):
        return False
    return True


def has_an_edx_platform_enrollment(*, user_id: int, course_id) -> bool:
    """
    Check if the user has an enrollment in the given edX platform course.

    Args:
        user_id (int): The ID of the user to check.
        course_id (str): The ID of the course to check enrollment for.

    Returns:
        bool: True if the user is enrolled in the course, False otherwise.
    """

    User = get_user_model()
    user = User.objects.only("id", "username").get(pk=user_id)
    enrollment = get_enrollment(username=user.username, course_id=course_id)

    return enrollment is not None
