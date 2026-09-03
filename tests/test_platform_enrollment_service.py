"""
Unit tests (NO DB) for partner_catalog.services.platform_enrollment.

The LMS enrollment API validates the requested mode against the modes
configured for the course and raises CourseModeNotFoundError on a mismatch.
NAU courses are configured with "honor" instead of "audit", so open-access
targets must resolve to the mode the course actually offers.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import partner_catalog.services.platform_enrollment as pe

# pytest fixtures intentionally reuse and shadow names; avoid noisy pylint warnings.
# pylint: disable=redefined-outer-name


@pytest.fixture
def orm(mocker):
    """Mock the User/CatalogCourse lookups done by ensure_edx_platform_enrollment."""
    fake_user_model = mocker.MagicMock()
    fake_user_model.objects.only.return_value.get.return_value = SimpleNamespace(id=1, username="bob")
    mocker.patch(
        "partner_catalog.services.platform_enrollment.get_user_model",
        return_value=fake_user_model,
    )

    cc = SimpleNamespace(
        id=999,
        catalog_id=500,
        catalog=SimpleNamespace(id=500),
        course_overview=SimpleNamespace(id="course-v1:NAU+CB101+2026"),
    )
    cc_get = mocker.patch("partner_catalog.services.platform_enrollment.CatalogCourse.objects.select_related")
    cc_get.return_value.only.return_value.get.return_value = cc
    return cc


def test_resolve_open_mode_prefers_audit(mocker):
    mocker.patch(
        "partner_catalog.services.platform_enrollment.available_modes",
        return_value=["audit", "honor", "verified"],
    )
    assert pe._resolve_open_mode("course-key") == "audit"  # pylint: disable=protected-access


def test_resolve_open_mode_falls_back_to_honor(mocker):
    mocker.patch(
        "partner_catalog.services.platform_enrollment.available_modes",
        return_value=["Honor", "verified"],
    )
    assert pe._resolve_open_mode("course-key") == "honor"  # pylint: disable=protected-access


def test_resolve_open_mode_defaults_to_audit_when_no_open_modes(mocker):
    mocker.patch(
        "partner_catalog.services.platform_enrollment.available_modes",
        return_value=["verified"],
    )
    assert pe._resolve_open_mode("course-key") == "audit"  # pylint: disable=protected-access


def test_ensure_enrollment_open_target_uses_honor_when_audit_unavailable(mocker, orm):
    """NAU regression: enrolling in an honor-only course must not request 'audit'."""
    _ = orm
    mocker.patch(
        "partner_catalog.services.platform_enrollment.available_modes",
        return_value=["honor"],
    )
    mocker.patch("partner_catalog.services.platform_enrollment.get_enrollment", return_value=None)
    add = mocker.patch("partner_catalog.services.platform_enrollment.add_enrollment")

    effective = pe.ensure_edx_platform_enrollment(user_id=1, catalog_course_id=999, target_mode="audit")

    add.assert_called_once_with(
        username="bob",
        course_id="course-v1:NAU+CB101+2026",
        mode="honor",
    )
    assert effective == "honor"


def test_ensure_enrollment_open_target_keeps_existing_open_mode(mocker, orm):
    """A honor enrollment already satisfies an open-access (audit) target."""
    _ = orm
    mocker.patch(
        "partner_catalog.services.platform_enrollment.available_modes",
        return_value=["audit", "honor"],
    )
    mocker.patch(
        "partner_catalog.services.platform_enrollment.get_enrollment",
        return_value={"mode": "honor"},
    )
    add = mocker.patch("partner_catalog.services.platform_enrollment.add_enrollment")
    update = mocker.patch("partner_catalog.services.platform_enrollment.update_enrollment")

    effective = pe.ensure_edx_platform_enrollment(user_id=1, catalog_course_id=999, target_mode="audit")

    add.assert_not_called()
    update.assert_not_called()
    assert effective == "honor"


def test_ensure_enrollment_downgrade_from_verified_targets_available_open_mode(mocker, orm):
    _ = orm
    mocker.patch(
        "partner_catalog.services.platform_enrollment.available_modes",
        return_value=["honor", "verified"],
    )
    mocker.patch(
        "partner_catalog.services.platform_enrollment.get_enrollment",
        return_value={"mode": "verified"},
    )
    update = mocker.patch("partner_catalog.services.platform_enrollment.update_enrollment")

    effective = pe.ensure_edx_platform_enrollment(user_id=1, catalog_course_id=999, target_mode="audit")

    update.assert_called_once_with(
        username="bob",
        course_id="course-v1:NAU+CB101+2026",
        mode="honor",
    )
    assert effective == "honor"


def test_ensure_enrollment_paid_target_unchanged(mocker, orm):
    """Paid (verified) targets are not rewritten by the open-mode resolution."""
    _ = orm
    modes = mocker.patch("partner_catalog.services.platform_enrollment.available_modes")
    mocker.patch("partner_catalog.services.platform_enrollment.get_enrollment", return_value=None)
    add = mocker.patch("partner_catalog.services.platform_enrollment.add_enrollment")

    effective = pe.ensure_edx_platform_enrollment(user_id=1, catalog_course_id=999, target_mode="verified")

    modes.assert_not_called()
    add.assert_called_once_with(
        username="bob",
        course_id="course-v1:NAU+CB101+2026",
        mode="verified",
    )
    assert effective == "verified"
