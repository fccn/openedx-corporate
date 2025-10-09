"""
Workflows for partner catalog domain logic.

This module defines high-level workflows that orchestrate side effects and business logic
for catalog course enrollment invitations, such as accepting an invite and ensuring
the corresponding enrollments are created. These workflows are intended to be idempotent
and encapsulate the steps required to transition between business states.
"""

from __future__ import annotations

import logging

from partner_catalog.services.enrollments import ensure_catalog_enrollment_exists_by_catalog_course
from partner_catalog.services.platform_enrollment import ensure_edx_platform_enrollment

logger = logging.getLogger(__name__)


def accept_invite_workflow(*, user_id: int, catalog_course_id: int) -> None:
    """
    Accepts an invitation for a user to enroll in a corporate partner catalog course.

    This workflow ensures that the user is enrolled in the internal catalog course enrollment
    and also enrolled in the edX platform course with the appropriate enrollment attributes.
    The workflow is idempotent and can be safely called multiple times for the same user and course.

    Args:
        user_id (int): The ID of the user accepting the invite.
        catalog_course_id (int): The ID of the CorporatePartnerCatalogCourse to enroll in.

    Returns:
        None
    """

    ensure_catalog_enrollment_exists_by_catalog_course(user_id=user_id, catalog_course_id=catalog_course_id)
    ensure_edx_platform_enrollment(user_id=user_id, catalog_course_id=catalog_course_id)
