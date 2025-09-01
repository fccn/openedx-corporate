"""
Backend v1 for student models/operations. Adjust imports for your fork if paths differ.
"""

# pylint: disable=import-error
from common.djangoapps.student.models import CourseEnrollment, CourseMode


def course_enrollment_model():
    return CourseEnrollment


def course_mode_model():
    return CourseMode


def enroll_user(*, user, course_key, mode=None):
    """
    Wrap CourseEnrollment.enroll(...) so callers don't depend on exact signature.
    The underlying call is idempotent (create/reactivate/no-op).
    """
    chosen_mode = mode or _pick_default_mode(course_key)
    return CourseEnrollment.enroll(
        user=user,
        course_key=course_key,
        mode=chosen_mode,
    )


def available_modes(course_key):
    modes = CourseMode.modes_for_course(course_key) or []
    return [m.slug for m in modes if getattr(m, "slug", None)]


def _pick_default_mode(course_key):
    slugs = available_modes(course_key)
    if "audit" in slugs:
        return "audit"
    return slugs[0] if slugs else getattr(CourseMode, "DEFAULT_MODE_SLUG", "audit")
