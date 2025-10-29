"""
This module provides services for managing enrollments in catalog courses for corporate partners.
"""
from __future__ import annotations

from typing import Optional, Tuple

from django.db import IntegrityError, transaction

from partner_catalog.edxapp_wrapper.student_module import course_enrollment_model
from partner_catalog.models import CatalogCourse, CatalogCourseEnrollment

CourseEnrollment = course_enrollment_model()


def add_catalog_course_enrollment(
    *, user_id: int, catalog_course_id: int
) -> Tuple[Optional[CatalogCourseEnrollment], bool]:
    """
    Creates a CatalogCourseEnrollment for the given user and catalog course if it does not already exist.

    Args:
        user_id (int): The ID of the user to enroll.
        catalog_course_id (int): The ID of the CorporatePartnerCatalogCourse to enroll the user in.

    Returns:
        Tuple[Optional[CatalogCourseEnrollment], bool]: A tuple containing the CatalogCourseEnrollment object (or None)
        and a boolean indicating whether the enrollment was created (True) or already existed (False).
    """

    try:
        with transaction.atomic():
            obj, created = CatalogCourseEnrollment.objects.get_or_create(
                user_id=user_id,
                catalog_course_id=catalog_course_id,
            )
        return obj, created
    except IntegrityError:
        obj = CatalogCourseEnrollment.objects.get(
            user_id=user_id,
            catalog_course_id=catalog_course_id,
        )
        return obj, False


def ensure_catalog_enrollment_exists_by_catalog_course(
    *, user_id: int, catalog_course_id: int
) -> Tuple[Optional[CatalogCourseEnrollment], bool]:
    """
    Ensures a CatalogCourseEnrollment exists for the given user and catalog course.

    This function creates a CatalogCourseEnrollment if it doesn't already exist.

    Args:
        user_id (int): The ID of the user to enroll.
        catalog_course_id (int): The ID of the CorporatePartnerCatalogCourse to enroll the user in.

    Returns:
        Tuple[Optional[CatalogCourseEnrollment], bool]: A tuple containing the CatalogCourseEnrollment object (or None)
        and a boolean indicating whether the enrollment was created (True) or already existed (False).
    """

    add_catalog_course_enrollment(user_id=user_id, catalog_course_id=catalog_course_id)


def get_catalog_course_id(*, user_id: int, course_id: str) -> Optional[int]:
    """Return catalog_course_id linked to the user's CourseEnrollment via cpa.catalog_id attribute.

    Returns None if the platform course enrollment, the attribute, or the catalog mapping doesn't exist.
    """
    try:
        ce = CourseEnrollment.objects.get(user_id=user_id, course_id=course_id)
    except CourseEnrollment.DoesNotExist:
        return None

    catalog_id_raw = (
        ce.attributes
          .filter(namespace="cpa", name="catalog_id")
          .values_list("value", flat=True)
          .first()
    )
    if not catalog_id_raw:
        return None

    catalog_id_str = str(catalog_id_raw).strip()
    try:
        catalog_id_lookup = int(catalog_id_str)
    except (TypeError, ValueError):
        catalog_id_lookup = catalog_id_str

    return (
        CatalogCourse.objects
        .filter(course_overview__id=course_id, catalog_id=catalog_id_lookup)
        .values_list("id", flat=True)
        .first()
    )


def set_catalog_enrollment_active(
    *, user_id: int, course_id: str, active: bool
) -> Tuple[Optional[CatalogCourseEnrollment], bool]:
    """Create/update CatalogCourseEnrollment setting desired active state."""
    catalog_course_id = get_catalog_course_id(user_id=user_id, course_id=course_id)
    if not catalog_course_id:
        return None, False

    if active:
        obj, created = add_catalog_course_enrollment(user_id=user_id, catalog_course_id=catalog_course_id)
        if obj and not obj.active:
            obj.active = True
            obj.save(update_fields=["active"])
        return obj, created

    try:
        obj = CatalogCourseEnrollment.objects.get(user_id=user_id, catalog_course_id=catalog_course_id)
    except CatalogCourseEnrollment.DoesNotExist:
        return None, False
    if obj.active:
        obj.active = False
        obj.save(update_fields=["active"])
        return obj, True
    return obj, False


def ensure_catalog_enrollment_exists(
    *, user_id: int, course_id: str
) -> Tuple[Optional[CatalogCourseEnrollment], bool]:
    """Ensure enrollment exists & active. Wrapper over set_catalog_enrollment_active(active=True)."""
    return set_catalog_enrollment_active(user_id=user_id, course_id=course_id, active=True)


def deactivate_catalog_enrollment(
    *, user_id: int, course_id: str
) -> Tuple[Optional[CatalogCourseEnrollment], bool]:
    """Deactivate enrollment (no creation). Wrapper over set_catalog_enrollment_active(active=False)."""
    return set_catalog_enrollment_active(user_id=user_id, course_id=course_id, active=False)
