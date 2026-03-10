"""
Utilities for inspecting a user's enrollment mode in the LMS.
"""

from django.contrib.auth import get_user_model

from partner_catalog.edxapp_wrapper.enrollment_api import get_enrollment


def get_platform_enrollment_mode(*, user_id: int, course_id: str) -> str:
    """
    Returns:
      - 'none' when no enrollment exists
      - known open modes ('honor', 'audit')
      - paid modes (e.g., 'verified', 'professional', ...)
      - 'unknown' when the mode is empty/unreadable
    """
    User = get_user_model()
    user = User.objects.only("id", "username").get(pk=user_id)
    enrollment = get_enrollment(username=user.username, course_id=str(course_id))
    if not enrollment:
        return "none"

    mode = (enrollment.get("mode") or "").lower()
    if mode:
        return mode
    return "unknown"
