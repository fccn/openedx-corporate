"""
Tests for partner_catalog.services.progress.compute_progress_percent_by_user.
"""

import pytest

from partner_catalog.api.v1.serializers import CatalogCourseEnrollmentSerializer
from partner_catalog.edxapp_wrapper.course_module import course_overview
from partner_catalog.models import CatalogCourse, CatalogCourseEnrollment
from partner_catalog.services import progress
from tests.factories import make_catalog, make_user

COURSE_KEY = "course-v1:TestX+CS101+2026"


def test_returns_percentage_of_completed_blocks(mocker):
    mocker.patch.object(
        progress,
        "get_course_blocks_completion_summary",
        return_value={"complete_count": 3, "incomplete_count": 1},
    )

    assert progress.compute_progress_percent_by_user(COURSE_KEY, user=object()) == 75.0


def test_course_without_modulestore_content_returns_zero(mocker):
    mocker.patch.object(
        progress,
        "get_course_blocks_completion_summary",
        side_effect=progress.ItemNotFoundError("course has no content"),
    )

    assert progress.compute_progress_percent_by_user(COURSE_KEY, user=object()) == 0.0


def test_unrelated_errors_are_not_swallowed(mocker):
    mocker.patch.object(
        progress,
        "get_course_blocks_completion_summary",
        side_effect=RuntimeError("boom"),
    )

    with pytest.raises(RuntimeError):
        progress.compute_progress_percent_by_user(COURSE_KEY, user=object())


@pytest.mark.django_db
def test_enrollment_list_progress_is_the_unit_completion_percentage(mocker):
    """The per-learner progress of the enrollment list is still the unit completion percentage."""
    catalog_course = CatalogCourse.objects.create(
        catalog=make_catalog(), course_overview=course_overview().objects.create()
    )
    enrollment = CatalogCourseEnrollment.objects.create(user=make_user(), catalog_course=catalog_course)
    # The test CourseOverview id is an integer, not a course key.
    mocker.patch.object(progress.CourseKey, "from_string", side_effect=lambda key: key)
    summary = mocker.patch.object(
        progress,
        "get_course_blocks_completion_summary",
        return_value={"complete_count": 7, "incomplete_count": 3},
    )

    assert CatalogCourseEnrollmentSerializer(enrollment).data["progress"] == 70.0
    summary.assert_called_once_with(str(catalog_course.course_overview_id), enrollment.user)
