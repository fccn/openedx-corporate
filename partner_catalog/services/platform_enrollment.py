from __future__ import annotations

import logging

from django.contrib.auth import get_user_model

from partner_catalog.edxapp_wrapper.enrollment_api import add_enrollment, update_enrollment, get_enrollment
from partner_catalog.models import CatalogCourse

logger = logging.getLogger(__name__)

HONOR = "honor"
AUDIT = "audit"
VERIFIED = "verified"


def ensure_edx_platform_enrollment(*, user_id: int, catalog_course_id: int, target_mode: str = VERIFIED) -> None:
    """
    Ensure LMS enrollment exists and (if applicable) is in target_mode.

    - If honor: do nothing
    - If none: add_enrollment(mode=target_mode)
    - If audit and target_mode=verified: update_enrollment(mode=verified)
    - If verified already: no-op
    """
    User = get_user_model()
    user = User.objects.only("id", "username").get(pk=user_id)

    cc = (
        CatalogCourse.objects
        .select_related("course_overview", "catalog")
        .only("id", "course_overview__id", "catalog__id", "catalog_id")
        .get(id=catalog_course_id)
    )

    course_id = str(cc.course_overview.id)
    catalog_id = str(getattr(cc, "catalog_id", None) or cc.catalog.id)

    try:
        existing = get_enrollment(username=user.username, course_id=course_id)

        if existing:
            mode = (existing.get("mode") or "").lower()

            # honor self-enroll: do not touch
            if mode == HONOR:
                logger.info(
                    "Honor enrollment detected; skipping LMS changes (user_id=%s, course_id=%s, catalog_id=%s)",
                    user_id, course_id, catalog_id
                )
                return

            # already in target mode
            if mode == target_mode:
                return

            # upgrade/downgrade
            update_enrollment(username=user.username, course_id=course_id, mode=target_mode)
            logger.info(
                "Enrollment updated (user_id=%s, course_id=%s, %s -> %s, catalog_id=%s)",
                user_id, course_id, mode, target_mode, catalog_id
            )
            return

        # no enrollment => create with target mode
        add_enrollment(username=user.username, course_id=course_id, mode=target_mode)
        logger.info(
            "Enrollment created (user_id=%s, course_id=%s, mode=%s, catalog_id=%s)",
            user_id, course_id, target_mode, catalog_id
        )

    except Exception:
        logger.exception(
            "Failed to ensure enrollment (user_id=%s, course_id=%s, target_mode=%s, catalog_id=%s)",
            user_id, course_id, target_mode, catalog_id
        )
        raise


def upgrade_to_verified(*, user_id: int, catalog_course_id: int) -> None:
    ensure_edx_platform_enrollment(user_id=user_id, catalog_course_id=catalog_course_id, target_mode=VERIFIED)


def downgrade_to_audit(*, user_id: int, catalog_course_id: int) -> None:
    ensure_edx_platform_enrollment(user_id=user_id, catalog_course_id=catalog_course_id, target_mode=AUDIT)
