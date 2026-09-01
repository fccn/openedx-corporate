"""
This module provides services for managing enrollments in catalog courses for corporate partners.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction

from partner_catalog.exceptions import (
    CourseLimitReached,
    NotAllowedToEnroll,
    UnsupportedEnrollmentMode,
    UserNotEnrolled,
)
from partner_catalog.models import CatalogCourse, CatalogCourseEnrollment
from partner_catalog.policies.enrollments import can_user_enroll_in_catalog_course
from partner_catalog.policies.limits import can_consume_course_limit, is_paid_course
from partner_catalog.policies.platform_enrollment import get_platform_enrollment_mode
from partner_catalog.services.platform_enrollment import downgrade_to_audit, ensure_edx_platform_enrollment
from partner_catalog.xapi.constants import (
    EVENT_NAME_COURSE_ENROLLMENT_ACTIVATED,
    EVENT_NAME_COURSE_ENROLLMENT_BLOCKED,
    EVENT_NAME_COURSE_ENROLLMENT_DEACTIVATED,
)
from partner_catalog.xapi.emitter import emit_catalog_course_enrollment_tracking_event

User = get_user_model()
OPEN_ENROLLMENT_MODES = frozenset({"audit", "honor"})
DEFAULT_PAID_TARGET_MODE = "verified"


@dataclass(frozen=True)
class CourseEnrollmentAttemptResult:
    """Outcome for learner-facing catalog course enrollment requests."""

    detail: str
    lms_enrollment_mode: str
    access_granted: bool = True
    warning_code: str | None = None
    warning_detail: str | None = None
    catalog_course_enrollment_id: int | None = None
    catalog_course_enrollment_active: bool = False
    catalog_course_enrollment_created: bool = False


class CatalogCourseEnrollmentService:
    """Service class for managing catalog courses enrollments logic."""

    @staticmethod
    def _catalog_dimensions(catalog_course=None, fallback_catalog=None):
        """
        Return ``(catalog_id, partner_id)`` for tracking payloads.
        """
        catalog_id = None
        partner_id = None

        if catalog_course is not None:
            catalog_id = getattr(catalog_course, "catalog_id", None)
            catalog = getattr(catalog_course, "catalog", None)
            if catalog is not None:
                catalog_id = catalog_id or getattr(catalog, "id", None)
                partner_id = getattr(catalog, "partner_id", None)

        if fallback_catalog is not None:
            catalog_id = catalog_id or getattr(fallback_catalog, "id", None)
            partner_id = partner_id or getattr(fallback_catalog, "partner_id", None)

        return catalog_id, partner_id

    def _get_platform_mode(self, *, user_id: int, course_overview_id) -> str:
        """
        Wrapper to fetch LMS enrollment mode for a user/course.

        Returns: 'none' | open modes ('honor'/'audit') | paid modes | 'unknown'
        """
        return get_platform_enrollment_mode(
            user_id=user_id,
            course_id=str(course_overview_id),
        )

    def _emit_blocked_enrollment_event(
        self,
        *,
        user_id: int,
        catalog_course,
        course_overview_id,
        blocked_reason: str,
        enrollment_mode: str | None = None,
    ) -> None:
        """
        Emit a blocked enrollment tracking event for functional analytics.
        """
        catalog = getattr(catalog_course, "catalog", None)
        catalog_id, partner_id = self._catalog_dimensions(
            catalog_course=catalog_course,
            fallback_catalog=catalog,
        )
        emit_catalog_course_enrollment_tracking_event(
            event_name=EVENT_NAME_COURSE_ENROLLMENT_BLOCKED,
            user_id=user_id,
            catalog_id=catalog_id,
            partner_id=partner_id,
            course_id=str(course_overview_id),
            catalog_course_id=getattr(catalog_course, "id", None),
            enrollment_mode=enrollment_mode,
            blocked_reason=blocked_reason,
            on_commit=False,
        )

    def _sync_lms_for_catalog_access(
        self,
        *,
        user_id: int,
        catalog_course_id: int,
        course_overview_id,
        target_mode: str = DEFAULT_PAID_TARGET_MODE,
    ) -> str:
        """
        Ensure LMS enrollment matches catalog entitlement,
        based on current LMS mode.

        Returns the effective LMS mode after applying the requested sync.
        """
        mode = self._get_platform_mode(user_id=user_id, course_overview_id=course_overview_id)

        if mode == "unknown":
            raise UnsupportedEnrollmentMode()

        if target_mode == "audit":
            if mode == "none":
                ensure_edx_platform_enrollment(
                    user_id=user_id,
                    catalog_course_id=catalog_course_id,
                    target_mode="audit",
                )
                return "audit"
            return mode

        if mode == "none":
            ensure_edx_platform_enrollment(
                user_id=user_id,
                catalog_course_id=catalog_course_id,
                target_mode=target_mode,
            )
            return target_mode
        if mode in OPEN_ENROLLMENT_MODES:
            ensure_edx_platform_enrollment(
                user_id=user_id,
                catalog_course_id=catalog_course_id,
                target_mode=target_mode,
            )
            return target_mode
        # paid modes (e.g., verified/professional/...) => no-op

        return mode

    @staticmethod
    def _is_paid_platform_mode(mode: str) -> bool:
        """Return True when the LMS enrollment already grants paid access."""
        return mode not in {"none", "unknown", *OPEN_ENROLLMENT_MODES}

    @staticmethod
    def _build_result(
        *,
        detail: str,
        lms_enrollment_mode: str,
        enrollment: CatalogCourseEnrollment | None = None,
        warning_code: str | None = None,
        warning_detail: str | None = None,
        created: bool = False,
    ) -> CourseEnrollmentAttemptResult:
        """Build a stable response payload for learner-facing course enrollments."""
        return CourseEnrollmentAttemptResult(
            detail=detail,
            lms_enrollment_mode=lms_enrollment_mode,
            warning_code=warning_code,
            warning_detail=warning_detail,
            catalog_course_enrollment_id=getattr(enrollment, "id", None),
            catalog_course_enrollment_active=bool(getattr(enrollment, "active", False)),
            catalog_course_enrollment_created=created,
        )

    def _emit_activation_event(
        self,
        *,
        user_id: int,
        course_overview_id,
        enrollment: CatalogCourseEnrollment,
        fallback_catalog,
        enrollment_mode: str,
    ) -> None:
        """Emit analytics for a newly created or reactivated catalog license."""
        enrollment_catalog_course = getattr(enrollment, "catalog_course", None)
        catalog_id, partner_id = self._catalog_dimensions(
            catalog_course=enrollment_catalog_course,
            fallback_catalog=fallback_catalog,
        )
        emit_catalog_course_enrollment_tracking_event(
            event_name=EVENT_NAME_COURSE_ENROLLMENT_ACTIVATED,
            user_id=user_id,
            catalog_id=catalog_id,
            partner_id=partner_id,
            course_id=str(course_overview_id),
            catalog_course_id=enrollment.catalog_course_id,
            enrollment_mode=enrollment_mode,
        )

    def _raise_course_limit_reached(
        self,
        *,
        user_id: int,
        catalog_course,
        course_overview_id,
        enrollment_mode: str,
    ) -> None:
        """Emit a blocked event and raise when a paid seat is required but unavailable."""
        self._emit_blocked_enrollment_event(
            user_id=user_id,
            catalog_course=catalog_course,
            course_overview_id=course_overview_id,
            blocked_reason=CourseLimitReached.default_code,
            enrollment_mode=enrollment_mode,
        )
        raise CourseLimitReached()

    def _course_limit_warning_result(
        self,
        *,
        user_id: int,
        catalog_course,
        course_overview_id,
        enrollment_mode: str,
        enrollment: CatalogCourseEnrollment | None = None,
    ) -> CourseEnrollmentAttemptResult:
        """Return a non-failing response when a user keeps open-mode access."""
        self._emit_blocked_enrollment_event(
            user_id=user_id,
            catalog_course=catalog_course,
            course_overview_id=course_overview_id,
            blocked_reason=CourseLimitReached.default_code,
            enrollment_mode=enrollment_mode,
        )
        return self._build_result(
            detail="Course access granted without paid-mode upgrade.",
            lms_enrollment_mode=enrollment_mode,
            enrollment=enrollment,
            warning_code=CourseLimitReached.default_code,
            warning_detail=CourseLimitReached.default_detail,
        )

    @transaction.atomic
    def create_or_activate_course_enrollment(
        self, *, user_id, catalog_course_id
    ) -> CourseEnrollmentAttemptResult:
        """
        Grant learner-facing access to a catalog course.

        For paid courses:
        - Existing LMS paid access is respected and no catalog license is created/changed.
        - Existing LMS audit/honor access attempts an upgrade to the configured
          paid target mode only when
          the catalog has bag capacity. If not, access remains audit/honor and the
          response carries a warning instead of failing.
        - No LMS enrollment creates paid-target access and a catalog license when the
          catalog has bag capacity.

        For open courses:
        - Access is handled in audit mode. The CatalogCourseEnrollment record is
          still created/activated so dashboard metrics count the enrollment, but
          it does not consume the catalog's paid enrollment bag (the limit only
          counts enrollments in paid courses).
        """
        user = User.objects.get(id=user_id)
        catalog_course = (
            CatalogCourse.objects
            .select_related("course_overview", "catalog")
            .get(id=catalog_course_id)
        )
        course_overview_id = catalog_course.course_overview_id
        catalog = catalog_course.catalog
        target_mode = DEFAULT_PAID_TARGET_MODE

        if not can_user_enroll_in_catalog_course(user=user, catalog_course=catalog_course):
            self._emit_blocked_enrollment_event(
                user_id=user_id,
                catalog_course=catalog_course,
                course_overview_id=course_overview_id,
                blocked_reason=NotAllowedToEnroll.default_code,
            )
            raise NotAllowedToEnroll()

        mode = self._get_platform_mode(user_id=user_id, course_overview_id=course_overview_id)
        if mode == "unknown":
            self._emit_blocked_enrollment_event(
                user_id=user_id,
                catalog_course=catalog_course,
                course_overview_id=course_overview_id,
                blocked_reason=UnsupportedEnrollmentMode.default_code,
                enrollment_mode=mode,
            )
            raise UnsupportedEnrollmentMode()

        enrollment = (
            CatalogCourseEnrollment.objects
            .select_for_update()
            .filter(user_id=user_id, course_overview_id=course_overview_id)
            .first()
        )
        is_paid = is_paid_course(course_overview_id=course_overview_id)

        if not is_paid:
            effective_mode = self._sync_lms_for_catalog_access(
                user_id=user_id,
                catalog_course_id=catalog_course_id,
                course_overview_id=course_overview_id,
                target_mode="audit",
            )
            # The CatalogCourseEnrollment record must be persisted for open
            # courses too: it is what the corporate dashboards and course
            # cards count. Skipping it left the metrics frozen at 0 for
            # free/audit enrollments.
            return self._persist_enrollment_record(
                user_id=user_id,
                catalog_course_id=catalog_course_id,
                course_overview_id=course_overview_id,
                catalog=catalog,
                enrollment=enrollment,
                effective_mode=effective_mode,
                event_mode="audit",
            )

        if self._is_paid_platform_mode(mode):
            return self._build_result(
                detail="Course access granted with existing LMS enrollment.",
                lms_enrollment_mode=mode,
                enrollment=enrollment,
            )

        if enrollment and enrollment.active:
            effective_mode = self._sync_lms_for_catalog_access(
                user_id=user_id,
                catalog_course_id=enrollment.catalog_course_id,
                course_overview_id=course_overview_id,
                target_mode=target_mode,
            )
            return self._build_result(
                detail="Successfully enrolled in the course.",
                lms_enrollment_mode=effective_mode,
                enrollment=enrollment,
            )

        if mode in OPEN_ENROLLMENT_MODES and not can_consume_course_limit(catalog=catalog):
            return self._course_limit_warning_result(
                user_id=user_id,
                catalog_course=catalog_course,
                course_overview_id=course_overview_id,
                enrollment_mode=mode,
                enrollment=enrollment,
            )

        if mode == "none" and not can_consume_course_limit(catalog=catalog):
            self._raise_course_limit_reached(
                user_id=user_id,
                catalog_course=catalog_course,
                course_overview_id=course_overview_id,
                enrollment_mode=mode,
            )

        target_catalog_course_id = getattr(enrollment, "catalog_course_id", None) or catalog_course_id
        effective_mode = self._sync_lms_for_catalog_access(
            user_id=user_id,
            catalog_course_id=target_catalog_course_id,
            course_overview_id=course_overview_id,
            target_mode=target_mode,
        )
        return self._persist_enrollment_record(
            user_id=user_id,
            catalog_course_id=catalog_course_id,
            course_overview_id=course_overview_id,
            catalog=catalog,
            enrollment=enrollment,
            effective_mode=effective_mode,
            event_mode=target_mode,
        )

    def _persist_enrollment_record(
        self, *, user_id, catalog_course_id, course_overview_id,
        catalog, enrollment, effective_mode, event_mode,
    ) -> CourseEnrollmentAttemptResult:
        """
        Create or (re)activate the CatalogCourseEnrollment record.

        This record is the source of truth for the corporate dashboard
        metrics (enrollments, completion rate, certified learners), so it is
        persisted for every successful enrollment, free or paid.
        """
        if enrollment:
            if not enrollment.active:
                enrollment.active = True
                enrollment.save(update_fields=["active"])
                self._emit_activation_event(
                    user_id=user_id,
                    course_overview_id=course_overview_id,
                    enrollment=enrollment,
                    fallback_catalog=catalog,
                    enrollment_mode=event_mode,
                )
            return self._build_result(
                detail="Successfully enrolled in the course.",
                lms_enrollment_mode=effective_mode,
                enrollment=enrollment,
            )

        try:
            created_enrollment = CatalogCourseEnrollment.objects.create(
                user_id=user_id,
                catalog_course_id=catalog_course_id,
                course_overview_id=course_overview_id,
                active=True,
            )
            self._emit_activation_event(
                user_id=user_id,
                course_overview_id=course_overview_id,
                enrollment=created_enrollment,
                fallback_catalog=catalog,
                enrollment_mode=event_mode,
            )
            return self._build_result(
                detail="Successfully enrolled in the course.",
                lms_enrollment_mode=effective_mode,
                enrollment=created_enrollment,
                created=True,
            )
        except IntegrityError:
            # Race: another request created the license concurrently
            enrollment = (
                CatalogCourseEnrollment.objects
                .select_for_update()
                .get(user_id=user_id, course_overview_id=course_overview_id)
            )
            created = False
            if not enrollment.active:
                enrollment.active = True
                enrollment.save(update_fields=["active"])
                created = True
            if created:
                self._emit_activation_event(
                    user_id=user_id,
                    course_overview_id=course_overview_id,
                    enrollment=enrollment,
                    fallback_catalog=catalog,
                    enrollment_mode=event_mode,
                )
            return self._build_result(
                detail="Successfully enrolled in the course.",
                lms_enrollment_mode=effective_mode,
                enrollment=enrollment,
            )

    @transaction.atomic
    def deactivate_course_enrollment(self, *, catalog_course_enrollment_id) -> None:
        """
        Deactivate a specific catalog course enrollment (license).

        Also applies LMS downgrade to audit for the owner catalog-course.
        """
        try:
            e = CatalogCourseEnrollment.objects.select_related(
                "catalog_course",
                "catalog_course__catalog",
                "course_overview",
            ).get(
                id=catalog_course_enrollment_id,
            )
        except CatalogCourseEnrollment.DoesNotExist as exc:
            raise UserNotEnrolled() from exc

        was_active = e.active
        if e.active:
            e.active = False
            e.save(update_fields=["active"])

        if was_active:
            catalog_id, partner_id = self._catalog_dimensions(
                catalog_course=getattr(e, "catalog_course", None),
            )
            emit_catalog_course_enrollment_tracking_event(
                event_name=EVENT_NAME_COURSE_ENROLLMENT_DEACTIVATED,
                user_id=e.user_id,
                catalog_id=catalog_id,
                partner_id=partner_id,
                course_id=str(e.course_overview_id),
                catalog_course_id=e.catalog_course_id,
                enrollment_mode="audit",
            )

        downgrade_to_audit(user_id=e.user_id, catalog_course_id=e.catalog_course_id)

    @transaction.atomic
    def deactivate_enrollments_by_catalog(self, *, user_id, catalog_id) -> None:
        """
        Deactivate all *owned* licenses for a user by catalog.

        Only affects enrollments whose owner (catalog_course.catalog_id) matches catalog_id.
        Applies LMS downgrade to audit for each affected enrollment.
        """
        owned_enrollments = list(
            CatalogCourseEnrollment.objects.filter(
                user_id=user_id,
                active=True,
                catalog_course__catalog_id=catalog_id,
            ).select_related("catalog_course", "catalog_course__catalog")
        )
        owned_catalog_course_ids = [enrollment.catalog_course_id for enrollment in owned_enrollments]

        CatalogCourseEnrollment.objects.filter(
            user_id=user_id,
            active=True,
            catalog_course__catalog_id=catalog_id,
        ).update(active=False)

        for enrollment, cc_id in zip(owned_enrollments, owned_catalog_course_ids):
            catalog_id_value, partner_id = self._catalog_dimensions(
                catalog_course=getattr(enrollment, "catalog_course", None),
            )
            emit_catalog_course_enrollment_tracking_event(
                event_name=EVENT_NAME_COURSE_ENROLLMENT_DEACTIVATED,
                user_id=user_id,
                catalog_id=catalog_id_value or catalog_id,
                partner_id=partner_id,
                course_id=str(enrollment.course_overview_id),
                catalog_course_id=cc_id,
                enrollment_mode="audit",
            )
            downgrade_to_audit(user_id=user_id, catalog_course_id=cc_id)
