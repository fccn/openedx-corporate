"""
Tests for partner_catalog.services.progress.compute_progress_percent_by_user.
"""

import pytest

from partner_catalog.services import progress

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
