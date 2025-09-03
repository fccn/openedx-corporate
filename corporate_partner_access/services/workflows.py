"""
Workflows for corporate partner access domain logic.

This module defines high-level workflows that orchestrate side effects and business logic
for catalog course enrollment invitations, such as accepting an invite and ensuring
the corresponding enrollments are created. These workflows are intended to be idempotent
and encapsulate the steps required to transition between business states.
"""

from __future__ import annotations

import logging

from corporate_partner_access.services.enrollments import ensure_enrollment_exists
from corporate_partner_access.services.platform_enrollment import ensure_edx_platform_enrollment

logger = logging.getLogger(__name__)


def accept_invite_workflow(*, user_id: int, catalog_course_id: int) -> None:
    """
    Domain workflow for: invite accepted → CPA enrollment → LMS enrollment.

    Idempotent behavior:
      - CPA: get_or_create enrollment row (no-op if exists)
      - LMS: CourseEnrollment.enroll(...) is idempotent (create/reactivate/no-op)
    """

    enrollment, created = ensure_enrollment_exists(
        user_id=user_id,
        catalog_course_id=catalog_course_id,
    )
    logger.info(
        "CPA enrollment %s (id=%s) user=%s course=%s",
        "created" if created else "already-existed",
        enrollment.id, user_id, catalog_course_id
    )
    ensure_edx_platform_enrollment(user_id=user_id, catalog_course_id=catalog_course_id)
