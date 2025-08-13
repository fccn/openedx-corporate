"""Backend abstraction for course module from edx-platform."""


from openedx.core.djangoapps.content.course_overviews.models import CourseOverview  # pylint: disable=import-error


def course_overview_backend():
    """Return CourseOverview class."""

    return CourseOverview
