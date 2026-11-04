"""Progress calculation services."""

from opaque_keys.edx.keys import CourseKey

from partner_catalog.edxapp_wrapper.courseware_module import get_course_blocks_completion_summary, item_not_found_error

ItemNotFoundError = item_not_found_error()


def compute_progress_percent_by_user(course_key_str: str, user) -> float | None:
    """Compute progress percent for a user in the given course run.

    Returns a float 0..100 or None if progress cannot be computed.
    """
    course_key = CourseKey.from_string(course_key_str)
    try:
        summary = get_course_blocks_completion_summary(course_key, user)
    except ItemNotFoundError:
        # The course run has no content in the modulestore (e.g. a
        # CourseOverview left behind after a course deletion). Treat it as
        # no measurable progress instead of failing the whole dashboard.
        return 0.0
    if not summary:
        return 0.0

    complete = int(summary.get("complete_count", 0))
    incomplete = int(summary.get("incomplete_count", 0))

    total = complete + incomplete
    if total <= 0:
        return 0.0
    return (complete / total) * 100.0
