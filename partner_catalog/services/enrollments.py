"""
This module provides services for managing enrollments in catalog courses for corporate partners.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction

from partner_catalog.exceptions import (
    CourseLimitReached,
    HonorSelfEnrollment,
    NotAllowedToEnroll,
    UnsupportedEnrollmentMode,
    UserNotEnrolled,
)
from partner_catalog.models import CatalogCourse, CatalogCourseEnrollment
from partner_catalog.policies.enrollments import can_user_enroll_in_catalog_course
from partner_catalog.policies.limits import can_consume_course_limit, is_paid_course
from partner_catalog.policies.platform_enrollment import get_platform_enrollment_mode
from partner_catalog.services.platform_enrollment import (
    downgrade_to_audit,
    ensure_edx_platform_enrollment,
    upgrade_to_verified,
)

User = get_user_model()


class CatalogCourseEnrollmentService:
    """Service class for managing catalog courses enrollments logic."""

    def _get_platform_mode(self, *, user_id: int, course_overview_id) -> str:
        """
        Wrapper to fetch LMS enrollment mode for a user/course.

        Returns: 'none' | open modes ('honor'/'audit') | paid modes | 'unknown'
        """
        return get_platform_enrollment_mode(
            user_id=user_id,
            course_id=str(course_overview_id),
        )

    def _sync_lms_for_catalog_access(
        self,
        *,
        user_id: int,
        catalog_course_id: int,
        course_overview_id,
        target_mode: str = "verified",
    ) -> str:
        """
        Ensure LMS enrollment matches catalog entitlement,
        based on current LMS mode.

        Returns the mode observed (after refresh).
        """
        mode = self._get_platform_mode(user_id=user_id, course_overview_id=course_overview_id)

        if mode == "honor":
            # honor self-enroll: do not touch
            return mode

        if mode == "unknown":
            raise UnsupportedEnrollmentMode()

        if target_mode == "audit":
            if mode == "none":
                ensure_edx_platform_enrollment(
                    user_id=user_id,
                    catalog_course_id=catalog_course_id,
                    target_mode="audit",
                )
            return mode

        if mode == "none":
            ensure_edx_platform_enrollment(
                user_id=user_id,
                catalog_course_id=catalog_course_id,
                target_mode="verified",
            )
        elif mode == "audit":
            upgrade_to_verified(user_id=user_id, catalog_course_id=catalog_course_id)
        # paid modes (e.g., verified/professional/...) => no-op

        return mode

    @transaction.atomic
    def create_or_activate_course_enrollment(
        self, *, user_id, catalog_course_id
    ) -> CatalogCourseEnrollment | None:
        """
        Create or activate a catalog course enrollment for a user.

        - Uses (user, course_overview) uniqueness (one license per course).
        - First catalog to grant license prevails (does not reassign catalog_course).
        - Enforces course-enrollment bag limits only for paid courses and only
          when a new license would be created.
        - Syncs LMS enrollment:
            * none -> verified (create)
            * audit -> verified (upgrade)
            * paid modes -> no-op
            * honor -> do not consume license (no-op for catalog; caller can redirect)
        - Open courses are handled in audit mode and do not create a catalog license.
        """
        user = User.objects.get(id=user_id)
        catalog_course = (
            CatalogCourse.objects
            .select_related("course_overview", "catalog")
            .get(id=catalog_course_id)
        )
        course_overview_id = catalog_course.course_overview_id

        if not can_user_enroll_in_catalog_course(user=user, catalog_course=catalog_course):
            raise NotAllowedToEnroll()

        # Early honor/unknown check (so we don't consume licenses)
        mode = self._get_platform_mode(user_id=user_id, course_overview_id=course_overview_id)
        if mode == "honor":
            raise HonorSelfEnrollment()
        if mode == "unknown":
            raise UnsupportedEnrollmentMode()

        enrollment = (
            CatalogCourseEnrollment.objects
            .select_for_update()
            .filter(user_id=user_id, course_overview_id=course_overview_id)
            .first()
        )

        if enrollment:
            if not enrollment.active:
                enrollment.active = True
                enrollment.save(update_fields=["active"])

            # Re-check mode close to LMS sync to reduce race issues
            self._sync_lms_for_catalog_access(
                user_id=user_id,
                catalog_course_id=enrollment.catalog_course_id,
                course_overview_id=course_overview_id,
            )
            return enrollment

        is_paid = is_paid_course(course_overview_id=course_overview_id)
        if not is_paid:
            # Open courses are not license-managed, and do not consume bag budget.
            self._sync_lms_for_catalog_access(
                user_id=user_id,
                catalog_course_id=catalog_course_id,
                course_overview_id=course_overview_id,
                target_mode="audit",
            )
            return None

        # New paid-license creation path: enforce bag limits
        catalog = catalog_course.catalog

        if not can_consume_course_limit(catalog=catalog):
            raise CourseLimitReached()

        # Re-check mode close to LMS sync to reduce race issues
        self._sync_lms_for_catalog_access(
            user_id=user_id,
            catalog_course_id=catalog_course_id,
            course_overview_id=course_overview_id,
        )

        try:
            return CatalogCourseEnrollment.objects.create(
                user_id=user_id,
                catalog_course_id=catalog_course_id,
                course_overview_id=course_overview_id,
                active=True,
            )
        except IntegrityError:
            # Race: another request created the license concurrently
            enrollment = (
                CatalogCourseEnrollment.objects
                .select_for_update()
                .get(user_id=user_id, course_overview_id=course_overview_id)
            )
            if not enrollment.active:
                enrollment.active = True
                enrollment.save(update_fields=["active"])
            return enrollment

    @transaction.atomic
    def deactivate_course_enrollment(self, *, catalog_course_enrollment_id) -> None:
        """
        Deactivate a specific catalog course enrollment (license).

        Also applies LMS downgrade to audit for the owner catalog-course.
        """
        try:
            e = CatalogCourseEnrollment.objects.select_related("catalog_course", "course_overview").get(
                id=catalog_course_enrollment_id,
            )
        except CatalogCourseEnrollment.DoesNotExist as exc:
            raise UserNotEnrolled() from exc

        if e.active:
            e.active = False
            e.save(update_fields=["active"])

        downgrade_to_audit(user_id=e.user_id, catalog_course_id=e.catalog_course_id)

    @transaction.atomic
    def deactivate_enrollments_by_catalog(self, *, user_id, catalog_id) -> None:
        """
        Deactivate all *owned* licenses for a user by catalog.

        Only affects enrollments whose owner (catalog_course.catalog_id) matches catalog_id.
        Applies LMS downgrade to audit for each affected enrollment.
        """
        owned_catalog_course_ids = list(
            CatalogCourseEnrollment.objects.filter(
                user_id=user_id,
                active=True,
                catalog_course__catalog_id=catalog_id,
            ).values_list("catalog_course_id", flat=True)
        )

        CatalogCourseEnrollment.objects.filter(
            user_id=user_id,
            active=True,
            catalog_course__catalog_id=catalog_id,
        ).update(active=False)

        for cc_id in owned_catalog_course_ids:
            downgrade_to_audit(user_id=user_id, catalog_course_id=cc_id)
