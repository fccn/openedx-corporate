"""
This module provides services for managing enrollments in catalog courses for corporate partners.
"""
from __future__ import annotations

from typing import Optional, Tuple

from django.db import IntegrityError, transaction

from corporate_partner_access.edxapp_wrapper.student_module import course_enrollment_model
from corporate_partner_access.models import CatalogCourseEnrollment, CorporatePartnerCatalogCourse

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


def ensure_catalog_enrollment_exists(
    *, user_id: int, course_id: str
) -> Tuple[Optional[CatalogCourseEnrollment], bool]:
    """
    Ensures a CatalogCourseEnrollment exists for the given user and course.

    This function looks up the course enrollment, extracts the catalog_id from the enrollment
    attributes, finds the corresponding CorporatePartnerCatalogCourse, and creates a
    CatalogCourseEnrollment if it doesn't already exist.

    Args:
        user_id (int): The ID of the user to enroll.
        course_id (str): The ID of the course to find the catalog enrollment for.

    Returns:
        Tuple[Optional[CatalogCourseEnrollment], bool]: A tuple containing the CatalogCourseEnrollment object (or None)
        and a boolean indicating whether the enrollment was created (True) or already existed (False).
        Returns (None, False) if the course enrollment doesn't exist, has no catalog_id attribute,
        or no matching CorporatePartnerCatalogCourse is found.
    """

    try:
        ce = CourseEnrollment.objects.get(user_id=user_id, course_id=course_id)
    except CourseEnrollment.DoesNotExist:
        return None, False

    catalog_id_raw = (
        ce.attributes
          .filter(namespace="cpa", name="catalog_id")
          .values_list("value", flat=True)
          .first()
    )
    if not catalog_id_raw:
        return None, False

    catalog_id_str = str(catalog_id_raw).strip()
    try:
        catalog_id_lookup = int(catalog_id_str)
    except (TypeError, ValueError):
        catalog_id_lookup = catalog_id_str

    catalog_course_id = (
        CorporatePartnerCatalogCourse.objects
        .filter(course_overview__id=course_id, catalog_id=catalog_id_lookup)
        .values_list("id", flat=True)
        .first()
    )
    if not catalog_course_id:
        return None, False

    return add_catalog_course_enrollment(user_id=user_id, catalog_course_id=catalog_course_id)
