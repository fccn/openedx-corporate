"""Backend abstraction for courseware completion from edx-platform."""

# pylint: disable=import-error
from lms.djangoapps.courseware.courses import \
    get_course_blocks_completion_summary as _get_course_blocks_completion_summary


def get_course_blocks_completion_summary(course_key, user):
    """Proxy to edxapp function to get completion summary for a user in a course."""
    return _get_course_blocks_completion_summary(course_key, user)
