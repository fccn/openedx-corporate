"""
This module provides services for managing enrollments in catalog courses for corporate partners.
"""

from __future__ import annotations

from typing import Tuple

from django.db import IntegrityError

from corporate_partner_access.models import CatalogCourseEnrollment


def ensure_enrollment_exists(*, user_id: int, catalog_course_id: int) -> Tuple[CatalogCourseEnrollment, bool]:
    """
    Ensure a CatalogCourseEnrollment row exists for (user_id, catalog_course_id).

    Behavior:
      - If it doesn't exist: create it with defaults (active=True by model default).
      - If it exists (active or not): no-op (do NOT modify any field).

    Returns:
      (enrollment, created)
        - created=True only when a new row was inserted.
    """
    try:
        enrollment, created = CatalogCourseEnrollment.objects.get_or_create(
            user_id=user_id,
            catalog_course_id=catalog_course_id,
        )
        return enrollment, created
    except IntegrityError:
        enrollment = CatalogCourseEnrollment.objects.get(
            user_id=user_id,
            catalog_course_id=catalog_course_id,
        )
        return enrollment, False
