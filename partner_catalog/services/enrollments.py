"""
This module provides services for managing enrollments in catalog courses for corporate partners.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from partner_catalog.models import CatalogCourse, CatalogCourseEnrollment
from partner_catalog.policies.enrollments import can_user_enroll_in_catalog_course, has_an_edx_platform_enrollment
from partner_catalog.services.platform_enrollment import ensure_edx_platform_enrollment

User = get_user_model()


class CatalogCourseEnrollmentService:
    """Service class for managing catalog courses enrollments logic."""

    ERROR_USER_NOT_ENROLLED = "User is not enrolled in the specified catalog course."
    ERROR_USER_NOT_ALLOWED_TO_ENROLL = "User is not allowed to enroll in this catalog course."

    @transaction.atomic
    def create_or_activate_course_enrollment(
        self, *, user_id, catalog_course_id, gdpr_required=True
    ) -> CatalogCourseEnrollment:
        """
        Create or activate a catalog course enrollment for a user.

        Creates a new enrollment if it doesn't exist, or reactivates an existing inactive one.
        Validates that the user has an edX platform enrollment and is allowed to enroll.

        Args:
            user_id: The user ID to enroll.
            catalog_course_id: The CatalogCourse ID to enroll the user in.
        Returns:
            The CatalogCourseEnrollment instance.
        """
        catalog_course = CatalogCourse.objects.get(id=catalog_course_id)

        if not can_user_enroll_in_catalog_course(
            user=User.objects.get(id=user_id),
            catalog_course=catalog_course,
            gdpr_required=gdpr_required,
        ):
            raise ValidationError(self.ERROR_USER_NOT_ALLOWED_TO_ENROLL)

        if not has_an_edx_platform_enrollment(
            user_id=user_id,
            course_id=catalog_course.course_overview_id,
        ):
            ensure_edx_platform_enrollment(
                user_id=user_id,
                catalog_course_id=catalog_course_id,
            )

        try:
            enrollment = CatalogCourseEnrollment.objects.create(
                user_id=user_id,
                catalog_course_id=catalog_course_id,
                active=True,
            )
        except IntegrityError:
            enrollment = CatalogCourseEnrollment.objects.get(
                user_id=user_id,
                catalog_course_id=catalog_course_id,
            )
            enrollment.active = True
            enrollment.save(update_fields=["active"])

        return enrollment

    @transaction.atomic
    def deactivate_course_enrollment(self, *, catalog_course_enrollment_id) -> None:
        """
        Deactivate a specific catalog course enrollment.

        Args:
            catalog_course_enrollment_id: The CatalogCourseEnrollment ID to deactivate.
        """
        try:
            catalog_course_enrollment = CatalogCourseEnrollment.objects.get(
                id=catalog_course_enrollment_id,
            )
        except CatalogCourseEnrollment.DoesNotExist as exc:
            raise ValidationError(self.ERROR_USER_NOT_ENROLLED) from exc

        catalog_course_enrollment.active = False
        catalog_course_enrollment.save(update_fields=["active"])

    @transaction.atomic
    def deactivate_enrollments_by_catalog(self, *, user_id, catalog_id) -> None:
        """
        Deactivate multiple catalog course enrollments for a user.

        Args:
            user_id: The user ID to deactivate enrollments for.
            catalog_course_ids: A list of catalog course IDs to deactivate enrollments from.
        """
        catalog_course_ids = CatalogCourse.objects.filter(
            catalog_id=catalog_id
        ).values_list("id", flat=True)

        CatalogCourseEnrollment.objects.filter(
            user_id=user_id,
            catalog_course_id__in=catalog_course_ids,
            active=True,
        ).update(active=False)
