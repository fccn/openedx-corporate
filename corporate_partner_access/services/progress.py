"""Progress calculation services."""

from opaque_keys.edx.keys import CourseKey

from corporate_partner_access.edxapp_wrapper.courseware_module import get_course_blocks_completion_summary
from corporate_partner_access.models import (
    CatalogCourseEnrollment,
    CorporatePartnerCatalogCourse,
    CorporatePartnerCatalogLearner,
)


def compute_progress_percent_by_user(course_key_str: str, user) -> float | None:
    """Compute progress percent for a user in the given course run.

    Returns a float 0..100 or None if progress cannot be computed.
    """
    course_key = CourseKey.from_string(course_key_str)
    summary = get_course_blocks_completion_summary(course_key, user)
    if not summary:
        return 0.0

    complete = int(summary.get("complete_count", 0))
    incomplete = int(summary.get("incomplete_count", 0))

    total = complete + incomplete
    if total <= 0:
        return 0.0
    return (complete / total) * 100.0


def compute_catalog_course_completion_rate(catalog_course_id: int) -> float:
    """Compute completion rate for a catalog course given its ID."""

    catalog_course = CorporatePartnerCatalogCourse.objects.filter(
        id=catalog_course_id
    ).first()
    course_key_str = str(catalog_course.course_overview.id)

    enrollments_qs = CatalogCourseEnrollment.objects.select_related("user").filter(
        catalog_course_id=catalog_course_id, active=True
    )

    total = 0
    completed = 0

    for enrollment in enrollments_qs:
        total += 1
        progress = compute_progress_percent_by_user(course_key_str, enrollment.user)

        if progress >= 99.999:
            completed += 1

    if total == 0:
        return 0.0

    return {
        "total_enrollments": total,
        "completed": completed,
        "completion_rate": (completed / total) * 100.0,
    }


def compute_catalog_completion_rate(catalog_id: str) -> float:
    """Compute catalog completion rate for a catalog.

    The catalog completion rate is defined as the percentage of learners
    who have completed all courses in the catalog.
    If there are no learners or no courses, the completion rate is 0.0.
    """

    courses_qs = CorporatePartnerCatalogCourse.objects.select_related(
        "course_overview"
    ).filter(catalog_id=catalog_id)
    total_courses = courses_qs.count()

    course_keys = [str(c.course_overview.id) for c in courses_qs]

    learners_qs = CorporatePartnerCatalogLearner.objects.select_related("user").filter(
        catalog_id=catalog_id, active=True
    )
    total_learners = learners_qs.count()

    if total_learners == 0 or total_courses == 0:
        return {
            "total_learners": total_learners,
            "learners_completed_all": 0,
            "completion_rate": 0.0,
        }

    learners_completed_all = 0
    for learner in learners_qs:
        if all(
            (progress := compute_progress_percent_by_user(ck, learner.user))
            and progress >= 99.999
            for ck in course_keys
        ):
            learners_completed_all += 1

    rate = (learners_completed_all / total_learners) * 100.0

    return {
        "total_learners": total_learners,
        "learners_completed_all": learners_completed_all,
        "completion_rate": rate,
    }
