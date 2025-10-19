"""Progress calculation services."""

from django.conf import settings
from django.core.cache import cache
from opaque_keys.edx.keys import CourseKey

from partner_catalog.edxapp_wrapper.courseware_module import get_course_blocks_completion_summary
from partner_catalog.models import CatalogCourse, CatalogCourseEnrollment, CatalogLearner

COURSE_COMPLETION_TTL = getattr(settings, "CP_COURSE_COMPLETION_TTL", 120)
CATALOG_COMPLETION_TTL = getattr(settings, "CP_CATALOG_COMPLETION_TTL", 180)
PROGRESS_COMPLETION_THRESHOLD = 99.999


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


def compute_catalog_course_completion_rate(
    catalog_course_id: int, skip_cache: bool = False
):
    """Compute (and cache) completion stats for a catalog course."""

    cache_key = f"cp:course_completion:v1:{catalog_course_id}"
    if not skip_cache:
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

    catalog_course = CatalogCourse.objects.filter(
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

        if progress >= PROGRESS_COMPLETION_THRESHOLD:
            completed += 1

    completion_rate = (completed / total) * 100.0 if total > 0 else 0.0

    result = {
        "total_enrollments": total,
        "completed": completed,
        "completion_rate": completion_rate,
    }
    cache.set(cache_key, result, COURSE_COMPLETION_TTL)
    return result


def compute_catalog_completion_rate(catalog_id: str, skip_cache: bool = False):
    """Compute (and cache) catalog completion stats.

    The catalog completion rate is defined as the percentage of learners
    who have completed all courses in the catalog.
    If there are no learners or no courses, the completion rate is 0.0.
    """

    cache_key = f"cp:catalog_completion:v1:{catalog_id}"
    if not skip_cache:
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

    courses_qs = CatalogCourse.objects.select_related(
        "course_overview"
    ).filter(catalog_id=catalog_id)

    course_keys = [str(c.course_overview.id) for c in courses_qs]

    learners_qs = CatalogLearner.objects.select_related("user").filter(
        catalog_id=catalog_id, active=True
    )
    total_learners = learners_qs.count()

    learners_completed_all = 0
    for learner in learners_qs:
        if all(
            (progress := compute_progress_percent_by_user(ck, learner.user))
            and progress >= PROGRESS_COMPLETION_THRESHOLD
            for ck in course_keys
        ):
            learners_completed_all += 1

    rate = (learners_completed_all / total_learners) * 100.0 if total_learners > 0 else 0.0

    result = {
        "total_learners": total_learners,
        "learners_completed_all": learners_completed_all,
        "completion_rate": rate,
    }
    cache.set(cache_key, result, CATALOG_COMPLETION_TTL)
    return result
