"""
Provides services for managing user enrollments in edX platform courses.

This module contains functions to ensure that users are properly enrolled in edX platform courses
associated with corporate partners. It uses wrapper modules to interact with edX app models and APIs,
avoiding direct imports from edX-platform code.
"""

from __future__ import annotations

import logging
from typing import Any, Optional, Tuple

from django.contrib.auth import get_user_model

from corporate_partner_access.edxapp_wrapper.student_module import course_enrollment_model, enroll_user
from corporate_partner_access.models import CorporatePartnerCatalogCourse

logger = logging.getLogger(__name__)


def ensure_edx_platform_enrollment(
    *,
    user_id: int,
    catalog_course_id: str,
    mode: Optional[str] = None,
) -> Tuple[Any, bool]:
    """
    Ensure the user is enrolled in edx-platform for `course_key_str`.
    Uses the student wrapper; no direct imports from edx-platform in services.
    """
    User = get_user_model()
    user = User.objects.only("id").get(pk=user_id)

    catalog_course = CorporatePartnerCatalogCourse.objects.get(id=catalog_course_id)
    course_key = catalog_course.course_overview.id

    CourseEnrollment = course_enrollment_model()

    had_active_before = CourseEnrollment.objects.filter(
        user=user, course_id=course_key, is_active=True
    ).exists()

    enrollment = enroll_user(user=user, course_key=course_key, mode=mode)

    created = not had_active_before
    logger.info(
        "LMS enrollment ensured: user_id=%s course=%s mode=%s created=%s is_active=%s",
        user_id, course_key, mode or "auto", created, getattr(enrollment, "is_active", True)
    )
    return enrollment, created
