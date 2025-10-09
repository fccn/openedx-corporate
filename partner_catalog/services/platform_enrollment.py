"""
Services to enroll a user in edX (LMS) from a CorporatePartnerCatalogCourse,
setting the enrollment attribute cpa/catalog_id. No return value.
"""

from __future__ import annotations

import logging

from django.contrib.auth import get_user_model

from partner_catalog.edxapp_wrapper.enrollment_api import add_enrollment
from partner_catalog.models import CorporatePartnerCatalogCourse

logger = logging.getLogger(__name__)


def ensure_edx_platform_enrollment(*, user_id: int, catalog_course_id: str) -> None:
    """
    Ensures that a user is enrolled in the edX platform course corresponding to the given
    CorporatePartnerCatalogCourse, and sets the enrollment attribute 'cpa/catalog_id'.

    This function is idempotent and can be called multiple times for the same user and course.
    It will create the enrollment if it does not exist, and update the enrollment attributes
    as needed.

    Args:
        user_id (int): The ID of the user to enroll.
        catalog_course_id (str): The ID of the CorporatePartnerCatalogCourse.

    Returns:
        None

    Raises:
        Exception: If enrollment creation or update fails.
    """

    User = get_user_model()
    user = User.objects.only("id", "username").get(pk=user_id)

    cc = (
        CorporatePartnerCatalogCourse.objects
        .select_related("course_overview", "catalog")
        .only("id", "course_overview__id", "catalog__id", "catalog_id")
        .get(id=catalog_course_id)
    )

    course_id = str(cc.course_overview.id)
    catalog_id = str(getattr(cc, "catalog_id", None) or cc.catalog.id)

    payload = {
        "username": user.username,
        "course_id": course_id,
        "enrollment_attributes": [
            {"namespace": "cpa", "name": "catalog_id", "value": catalog_id}
        ],
    }

    try:
        add_enrollment(**payload)
        logger.info(
            "Enrollment ensured (user_id=%s, course_id=%s, catalog_id=%s)",
            user_id, course_id, catalog_id
        )
    except Exception:
        logger.exception(
            "Failed to ensure enrollment (user_id=%s, course_id=%s, catalog_id=%s)",
            user_id, course_id, catalog_id
        )
        raise
