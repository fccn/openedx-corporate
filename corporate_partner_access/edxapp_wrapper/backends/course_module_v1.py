"""Backend abstraction for course module from edx-platform."""

# pylint: disable=import-error
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
from openedx.core.djangoapps.content.course_overviews.serializers import CourseOverviewBaseSerializer


def course_overview_model():
    """Return CourseOverview class."""

    return CourseOverview


def course_overview_base_serializer():
    """Return CourseOverview serializer class."""

    return CourseOverviewBaseSerializer
