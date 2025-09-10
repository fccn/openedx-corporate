"""Progress calculation services."""

from opaque_keys.edx.keys import CourseKey

from corporate_partner_access.edxapp_wrapper.courseware_module import get_course_blocks_completion_summary


def compute_progress_percent(course_key_str: str, user) -> float | None:
    """Compute progress percent for a user in the given course run.

    Returns a float 0..100 or None if progress cannot be computed.
    """
    course_key = CourseKey.from_string(course_key_str)
    summary = get_course_blocks_completion_summary(course_key, user)
    if not summary:
        return None

    complete = int(summary.get("complete_count", 0))
    incomplete = int(summary.get("incomplete_count", 0))
    denom = complete + incomplete
    if denom <= 0:
        return 0.0
    return (complete / denom) * 100.0
