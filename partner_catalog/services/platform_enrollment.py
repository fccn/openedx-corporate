"""Helpers for keeping LMS enrollments in sync with catalog enrollments."""

import logging

from django.contrib.auth import get_user_model

from partner_catalog.edxapp_wrapper.enrollment_api import add_enrollment, get_enrollment, update_enrollment
from partner_catalog.edxapp_wrapper.student_module import available_modes
from partner_catalog.models import CatalogCourse

logger = logging.getLogger(__name__)

HONOR = "honor"
AUDIT = "audit"
VERIFIED = "verified"
OPEN_MODES = (AUDIT, HONOR)


def _resolve_open_mode(course_key) -> str:
    """
    Return the open-access mode actually configured for the course.

    Some platforms (e.g. NAU) configure courses with "honor" instead of
    "audit". The LMS enrollment API validates the requested mode against the
    course's configured modes and raises CourseModeNotFoundError on a
    mismatch, so a hardcoded "audit" cannot be used.
    """
    modes = {
        (slug or "").strip().lower()
        for slug in (available_modes(course_key) or [])
    }
    for candidate in OPEN_MODES:
        if candidate in modes:
            return candidate
    return AUDIT


def ensure_edx_platform_enrollment(*, user_id: int, catalog_course_id: int, target_mode: str = VERIFIED) -> str:
    """
    Ensure LMS enrollment exists and (if applicable) is in target_mode.

    - If none: add_enrollment(mode=target_mode)
    - If audit/honor and target_mode=verified: update_enrollment(mode=verified)
    - If verified already: no-op

    When target_mode is an open mode, it is resolved to the open mode the
    course actually offers (audit or honor).

    Returns the effective LMS enrollment mode after the sync.
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

    if target_mode in OPEN_MODES:
        target_mode = _resolve_open_mode(cc.course_overview.id)

    try:
        existing = get_enrollment(username=user.username, course_id=course_id)

        if existing:
            mode = (existing.get("mode") or "").lower()

            # already in target mode
            if mode == target_mode:
                return mode

            # Open-access target with open-access enrollment: nothing to change.
            if target_mode in OPEN_MODES and mode in OPEN_MODES:
                return mode

            # upgrade/downgrade
            update_enrollment(username=user.username, course_id=course_id, mode=target_mode)
            logger.info(
                "Enrollment updated (user_id=%s, course_id=%s, %s -> %s, catalog_id=%s)",
                user_id, course_id, mode, target_mode, catalog_id
            )
            return target_mode

        # no enrollment => create with target mode
        add_enrollment(username=user.username, course_id=course_id, mode=target_mode)
        logger.info(
            "Enrollment created (user_id=%s, course_id=%s, mode=%s, catalog_id=%s)",
            user_id, course_id, target_mode, catalog_id
        )
        return target_mode

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
