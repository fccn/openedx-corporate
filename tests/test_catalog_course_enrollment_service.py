"""
Unit tests (NO DB) for CatalogCourseEnrollmentService.

Goals:
- Run without creating/using a Django test DB.
- Avoid @transaction.atomic touching the DB.
- Mock all ORM + external LMS calls.

Refactor highlights:
- Use `mocker` (pytest-mock) instead of stacking many @patch decorators.
- Patch only *stable* entrypoints (e.g., `.objects.select_for_update`) and build
  the chain on the returned mock (less brittle than patching "...select_for_update().get").
- Keep a single fixture that:
  - makes `transaction.atomic` a no-op
  - unwraps already-decorated methods (so calls won’t enter atomic)
  - returns the Service class + module for constants/exceptions
"""

from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from partner_catalog.exceptions import (
    CourseLimitReached,
    HonorSelfEnrollment,
    NotAllowedToEnroll,
    UserNotEnrolled,
)

# pytest fixtures intentionally reuse and shadow names; avoid noisy pylint warnings.
# pylint: disable=redefined-outer-name


# --------------------------------------------------------------------
# Atomic no-op + service import/unwrap
# --------------------------------------------------------------------

@contextmanager
def _noop_atomic(*args, **kwargs):
    yield


@pytest.fixture
def enrollments_module_no_atomic(monkeypatch):
    """
    Import partner_catalog.services.enrollments and:
    1) replace transaction.atomic with a no-op
    2) unwrap methods already decorated with @transaction.atomic
       so calling them doesn't try to connect to DB.
    """
    import partner_catalog.services.enrollments as m  # pylint: disable=import-outside-toplevel

    monkeypatch.setattr(m.transaction, "atomic", _noop_atomic)

    Service = m.CatalogCourseEnrollmentService

    for name in (
        "create_or_activate_course_enrollment",
        "deactivate_course_enrollment",
        "deactivate_enrollments_by_catalog",
    ):
        fn = getattr(Service, name, None)
        if fn and hasattr(fn, "__wrapped__"):
            monkeypatch.setattr(Service, name, fn.__wrapped__)

    return m


# --------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------

def _fake_catalog_course(*, course_overview_id=101, catalog_id=500, catalog_course_id=999):
    """
    Minimal shape used by the service:
    - id
    - course_overview_id
    - catalog (with id)
    """
    return SimpleNamespace(
        id=catalog_course_id,
        course_overview_id=course_overview_id,
        catalog=SimpleNamespace(id=catalog_id),
    )


@pytest.fixture
def svc(enrollments_module_no_atomic):
    """Convenience: instantiate the service from the imported module."""
    Service = enrollments_module_no_atomic.CatalogCourseEnrollmentService
    return Service()


# --------------------------------------------------------------------
# Tests: create_or_activate_course_enrollment
# --------------------------------------------------------------------

def test_create_or_activate_access_denied_raises_and_no_lms_calls(
    mocker,
    enrollments_module_no_atomic,
    svc,
):
    # Fixture is required for side effects (monkeypatching), even if not referenced below.
    _ = enrollments_module_no_atomic

    user_get = mocker.patch("partner_catalog.services.enrollments.User.objects.get")
    cc_select_related = mocker.patch("partner_catalog.services.enrollments.CatalogCourse.objects.select_related")
    cce_select_for_update = mocker.patch(
        "partner_catalog.services.enrollments.CatalogCourseEnrollment.objects.select_for_update"
    )

    can_enroll = mocker.patch("partner_catalog.services.enrollments.can_user_enroll_in_catalog_course")
    platform_mode = mocker.patch("partner_catalog.services.enrollments.get_platform_enrollment_mode")
    ensure = mocker.patch("partner_catalog.services.enrollments.ensure_edx_platform_enrollment")
    upgrade = mocker.patch("partner_catalog.services.enrollments.upgrade_to_verified")
    tracking_emit = mocker.patch("partner_catalog.services.enrollments.emit_catalog_course_enrollment_tracking_event")

    user_get.return_value = SimpleNamespace(id=1)
    cc_select_related.return_value.get.return_value = _fake_catalog_course(course_overview_id=101)

    can_enroll.return_value = False  # access denied
    # Safety: chain exists but should not matter
    cce_select_for_update.return_value.filter.return_value.first.return_value = None

    with pytest.raises(NotAllowedToEnroll):
        svc.create_or_activate_course_enrollment(user_id=1, catalog_course_id=999)

    can_enroll.assert_called_once()
    platform_mode.assert_not_called()
    ensure.assert_not_called()
    upgrade.assert_not_called()
    tracking_emit.assert_called_once_with(
        event_name=enrollments_module_no_atomic.EVENT_NAME_COURSE_ENROLLMENT_BLOCKED,
        user_id=1,
        catalog_id=500,
        partner_id=None,
        course_id="101",
        catalog_course_id=999,
        enrollment_mode=None,
        blocked_reason=NotAllowedToEnroll.default_code,
        on_commit=False,
    )


def test_create_or_activate_honor_mode_raises_and_no_lms_calls(
    mocker,
    enrollments_module_no_atomic,
    svc,
):
    user_get = mocker.patch("partner_catalog.services.enrollments.User.objects.get")
    cc_select_related = mocker.patch("partner_catalog.services.enrollments.CatalogCourse.objects.select_related")
    cce_select_for_update = mocker.patch(
        "partner_catalog.services.enrollments.CatalogCourseEnrollment.objects.select_for_update"
    )

    can_enroll = mocker.patch("partner_catalog.services.enrollments.can_user_enroll_in_catalog_course")
    platform_mode = mocker.patch("partner_catalog.services.enrollments.get_platform_enrollment_mode")
    ensure = mocker.patch("partner_catalog.services.enrollments.ensure_edx_platform_enrollment")
    upgrade = mocker.patch("partner_catalog.services.enrollments.upgrade_to_verified")
    tracking_emit = mocker.patch("partner_catalog.services.enrollments.emit_catalog_course_enrollment_tracking_event")

    user_get.return_value = SimpleNamespace(id=1)
    cc_select_related.return_value.get.return_value = _fake_catalog_course(course_overview_id=101)

    can_enroll.return_value = True
    platform_mode.return_value = "honor"

    # Safety chain (shouldn't be used beyond "first")
    cce_select_for_update.return_value.filter.return_value.first.return_value = None

    with pytest.raises(HonorSelfEnrollment):
        svc.create_or_activate_course_enrollment(user_id=1, catalog_course_id=999)

    can_enroll.assert_called_once()
    platform_mode.assert_called_once()
    ensure.assert_not_called()
    upgrade.assert_not_called()
    tracking_emit.assert_called_once_with(
        event_name=enrollments_module_no_atomic.EVENT_NAME_COURSE_ENROLLMENT_BLOCKED,
        user_id=1,
        catalog_id=500,
        partner_id=None,
        course_id="101",
        catalog_course_id=999,
        enrollment_mode="honor",
        blocked_reason=HonorSelfEnrollment.default_code,
        on_commit=False,
    )


def test_create_or_activate_existing_inactive_enrollment_reactivates(
    mocker,
    svc,
):
    user_get = mocker.patch("partner_catalog.services.enrollments.User.objects.get")
    cc_select_related = mocker.patch("partner_catalog.services.enrollments.CatalogCourse.objects.select_related")
    cce_select_for_update = mocker.patch(
        "partner_catalog.services.enrollments.CatalogCourseEnrollment.objects.select_for_update"
    )

    can_enroll = mocker.patch("partner_catalog.services.enrollments.can_user_enroll_in_catalog_course")
    platform_mode = mocker.patch("partner_catalog.services.enrollments.get_platform_enrollment_mode")
    ensure = mocker.patch("partner_catalog.services.enrollments.ensure_edx_platform_enrollment")
    upgrade = mocker.patch("partner_catalog.services.enrollments.upgrade_to_verified")

    user_get.return_value = SimpleNamespace(id=1)
    fake_course = _fake_catalog_course(course_overview_id=101)
    cc_select_related.return_value.get.return_value = fake_course

    can_enroll.return_value = True
    platform_mode.return_value = "verified"

    fake_enrollment = SimpleNamespace(
        id=55,
        active=False,
        catalog_course_id=fake_course.id,
        save=MagicMock(),
    )
    cce_select_for_update.return_value.filter.return_value.first.return_value = fake_enrollment

    result = svc.create_or_activate_course_enrollment(user_id=1, catalog_course_id=fake_course.id)

    assert result is fake_enrollment
    assert fake_enrollment.active is True
    fake_enrollment.save.assert_called_once_with(update_fields=["active"])

    ensure.assert_not_called()
    upgrade.assert_not_called()


def test_create_or_activate_new_enrollment_mode_none_creates_and_ensures(
    mocker,
    svc,
):
    user_get = mocker.patch("partner_catalog.services.enrollments.User.objects.get")
    cc_select_related = mocker.patch("partner_catalog.services.enrollments.CatalogCourse.objects.select_related")
    cce_select_for_update = mocker.patch(
        "partner_catalog.services.enrollments.CatalogCourseEnrollment.objects.select_for_update"
    )
    cce_create = mocker.patch("partner_catalog.services.enrollments.CatalogCourseEnrollment.objects.create")

    can_enroll = mocker.patch("partner_catalog.services.enrollments.can_user_enroll_in_catalog_course")
    platform_mode = mocker.patch("partner_catalog.services.enrollments.get_platform_enrollment_mode")
    ensure = mocker.patch("partner_catalog.services.enrollments.ensure_edx_platform_enrollment")
    upgrade = mocker.patch("partner_catalog.services.enrollments.upgrade_to_verified")

    course_limit = mocker.patch("partner_catalog.services.enrollments.can_consume_course_limit")
    is_paid = mocker.patch("partner_catalog.services.enrollments.is_paid_course")

    user_get.return_value = SimpleNamespace(id=1)
    fake_course = _fake_catalog_course(course_overview_id=101)
    cc_select_related.return_value.get.return_value = fake_course

    can_enroll.return_value = True
    platform_mode.return_value = "none"
    course_limit.return_value = True
    is_paid.return_value = True

    # No existing enrollment
    cce_select_for_update.return_value.filter.return_value.first.return_value = None

    fake_created_enrollment = SimpleNamespace(
        id=777,
        user_id=1,
        catalog_course_id=fake_course.id,
        course_overview_id=fake_course.course_overview_id,
        active=True,
    )
    cce_create.return_value = fake_created_enrollment

    result = svc.create_or_activate_course_enrollment(user_id=1, catalog_course_id=fake_course.id)

    ensure.assert_called_once_with(user_id=1, catalog_course_id=fake_course.id, target_mode="verified")
    upgrade.assert_not_called()

    cce_create.assert_called_once_with(
        user_id=1,
        catalog_course_id=fake_course.id,
        course_overview_id=fake_course.course_overview_id,
        active=True,
    )
    assert result is fake_created_enrollment


def test_create_or_activate_new_enrollment_mode_audit_creates_and_upgrades(
    mocker,
    svc,
):
    user_get = mocker.patch("partner_catalog.services.enrollments.User.objects.get")
    cc_select_related = mocker.patch("partner_catalog.services.enrollments.CatalogCourse.objects.select_related")
    cce_select_for_update = mocker.patch(
        "partner_catalog.services.enrollments.CatalogCourseEnrollment.objects.select_for_update"
    )
    cce_create = mocker.patch("partner_catalog.services.enrollments.CatalogCourseEnrollment.objects.create")

    can_enroll = mocker.patch("partner_catalog.services.enrollments.can_user_enroll_in_catalog_course")
    platform_mode = mocker.patch("partner_catalog.services.enrollments.get_platform_enrollment_mode")
    ensure = mocker.patch("partner_catalog.services.enrollments.ensure_edx_platform_enrollment")
    upgrade = mocker.patch("partner_catalog.services.enrollments.upgrade_to_verified")

    course_limit = mocker.patch("partner_catalog.services.enrollments.can_consume_course_limit")
    is_paid = mocker.patch("partner_catalog.services.enrollments.is_paid_course")

    user_get.return_value = SimpleNamespace(id=1)
    fake_course = _fake_catalog_course(course_overview_id=101)
    cc_select_related.return_value.get.return_value = fake_course

    can_enroll.return_value = True
    platform_mode.return_value = "audit"
    course_limit.return_value = True
    is_paid.return_value = True

    cce_select_for_update.return_value.filter.return_value.first.return_value = None

    fake_created_enrollment = SimpleNamespace(
        id=778,
        user_id=1,
        catalog_course_id=fake_course.id,
        course_overview_id=fake_course.course_overview_id,
        active=True,
    )
    cce_create.return_value = fake_created_enrollment

    result = svc.create_or_activate_course_enrollment(user_id=1, catalog_course_id=fake_course.id)

    upgrade.assert_called_once_with(user_id=1, catalog_course_id=fake_course.id)
    ensure.assert_not_called()

    cce_create.assert_called_once_with(
        user_id=1,
        catalog_course_id=fake_course.id,
        course_overview_id=fake_course.course_overview_id,
        active=True,
    )
    assert result is fake_created_enrollment


def test_existing_enrollment_mode_none_calls_ensure_not_create(
    mocker,
    svc,
):
    user_get = mocker.patch("partner_catalog.services.enrollments.User.objects.get")
    cc_select_related = mocker.patch("partner_catalog.services.enrollments.CatalogCourse.objects.select_related")
    cce_select_for_update = mocker.patch(
        "partner_catalog.services.enrollments.CatalogCourseEnrollment.objects.select_for_update"
    )
    cce_create = mocker.patch("partner_catalog.services.enrollments.CatalogCourseEnrollment.objects.create")

    can_enroll = mocker.patch("partner_catalog.services.enrollments.can_user_enroll_in_catalog_course")
    platform_mode = mocker.patch("partner_catalog.services.enrollments.get_platform_enrollment_mode")
    ensure = mocker.patch("partner_catalog.services.enrollments.ensure_edx_platform_enrollment")
    upgrade = mocker.patch("partner_catalog.services.enrollments.upgrade_to_verified")

    user_get.return_value = SimpleNamespace(id=1)
    fake_course = _fake_catalog_course(course_overview_id=101, catalog_course_id=999)
    cc_select_related.return_value.get.return_value = fake_course

    can_enroll.return_value = True
    platform_mode.return_value = "none"

    fake_enrollment = SimpleNamespace(
        id=10,
        active=True,
        catalog_course_id=fake_course.id,
        save=MagicMock(),
    )
    cce_select_for_update.return_value.filter.return_value.first.return_value = fake_enrollment

    result = svc.create_or_activate_course_enrollment(user_id=1, catalog_course_id=fake_course.id)

    assert result is fake_enrollment
    ensure.assert_called_once_with(
        user_id=1,
        catalog_course_id=fake_enrollment.catalog_course_id,
        target_mode="verified",
    )
    upgrade.assert_not_called()
    cce_create.assert_not_called()


def test_existing_enrollment_mode_audit_calls_upgrade_not_create(
    mocker,
    svc,
):
    user_get = mocker.patch("partner_catalog.services.enrollments.User.objects.get")
    cc_select_related = mocker.patch("partner_catalog.services.enrollments.CatalogCourse.objects.select_related")
    cce_select_for_update = mocker.patch(
        "partner_catalog.services.enrollments.CatalogCourseEnrollment.objects.select_for_update"
    )
    cce_create = mocker.patch("partner_catalog.services.enrollments.CatalogCourseEnrollment.objects.create")

    can_enroll = mocker.patch("partner_catalog.services.enrollments.can_user_enroll_in_catalog_course")
    platform_mode = mocker.patch("partner_catalog.services.enrollments.get_platform_enrollment_mode")
    ensure = mocker.patch("partner_catalog.services.enrollments.ensure_edx_platform_enrollment")
    upgrade = mocker.patch("partner_catalog.services.enrollments.upgrade_to_verified")

    user_get.return_value = SimpleNamespace(id=1)
    fake_course = _fake_catalog_course(course_overview_id=101, catalog_course_id=999)
    cc_select_related.return_value.get.return_value = fake_course

    can_enroll.return_value = True
    platform_mode.return_value = "audit"

    fake_enrollment = SimpleNamespace(
        id=11,
        active=True,
        catalog_course_id=fake_course.id,
        save=MagicMock(),
    )
    cce_select_for_update.return_value.filter.return_value.first.return_value = fake_enrollment

    result = svc.create_or_activate_course_enrollment(user_id=1, catalog_course_id=fake_course.id)

    assert result is fake_enrollment
    upgrade.assert_called_once_with(user_id=1, catalog_course_id=fake_enrollment.catalog_course_id)
    ensure.assert_not_called()
    cce_create.assert_not_called()


def test_new_enrollment_open_course_does_not_consume_bag_and_no_create(
    mocker,
    svc,
):
    user_get = mocker.patch("partner_catalog.services.enrollments.User.objects.get")
    cc_select_related = mocker.patch("partner_catalog.services.enrollments.CatalogCourse.objects.select_related")
    cce_select_for_update = mocker.patch(
        "partner_catalog.services.enrollments.CatalogCourseEnrollment.objects.select_for_update"
    )
    cce_create = mocker.patch("partner_catalog.services.enrollments.CatalogCourseEnrollment.objects.create")

    can_enroll = mocker.patch("partner_catalog.services.enrollments.can_user_enroll_in_catalog_course")
    platform_mode = mocker.patch("partner_catalog.services.enrollments.get_platform_enrollment_mode")
    ensure = mocker.patch("partner_catalog.services.enrollments.ensure_edx_platform_enrollment")
    upgrade = mocker.patch("partner_catalog.services.enrollments.upgrade_to_verified")

    course_limit = mocker.patch("partner_catalog.services.enrollments.can_consume_course_limit")
    is_paid = mocker.patch("partner_catalog.services.enrollments.is_paid_course")

    user_get.return_value = SimpleNamespace(id=1)
    fake_course = _fake_catalog_course(course_overview_id=101, catalog_course_id=999)
    cc_select_related.return_value.get.return_value = fake_course

    can_enroll.return_value = True
    platform_mode.return_value = "none"

    cce_select_for_update.return_value.filter.return_value.first.return_value = None

    is_paid.return_value = False
    course_limit.return_value = True  # should not be used for open courses

    result = svc.create_or_activate_course_enrollment(user_id=1, catalog_course_id=fake_course.id)

    assert result is None
    ensure.assert_called_once_with(user_id=1, catalog_course_id=fake_course.id, target_mode="audit")
    upgrade.assert_not_called()
    course_limit.assert_not_called()
    cce_create.assert_not_called()


def test_new_enrollment_course_limit_reached_raises_and_no_lms_no_create(
    mocker,
    enrollments_module_no_atomic,
    svc,
):
    user_get = mocker.patch("partner_catalog.services.enrollments.User.objects.get")
    cc_select_related = mocker.patch("partner_catalog.services.enrollments.CatalogCourse.objects.select_related")
    cce_select_for_update = mocker.patch(
        "partner_catalog.services.enrollments.CatalogCourseEnrollment.objects.select_for_update"
    )
    cce_create = mocker.patch("partner_catalog.services.enrollments.CatalogCourseEnrollment.objects.create")

    can_enroll = mocker.patch("partner_catalog.services.enrollments.can_user_enroll_in_catalog_course")
    platform_mode = mocker.patch("partner_catalog.services.enrollments.get_platform_enrollment_mode")
    ensure = mocker.patch("partner_catalog.services.enrollments.ensure_edx_platform_enrollment")
    upgrade = mocker.patch("partner_catalog.services.enrollments.upgrade_to_verified")
    tracking_emit = mocker.patch("partner_catalog.services.enrollments.emit_catalog_course_enrollment_tracking_event")

    course_limit = mocker.patch("partner_catalog.services.enrollments.can_consume_course_limit")
    is_paid = mocker.patch("partner_catalog.services.enrollments.is_paid_course")

    user_get.return_value = SimpleNamespace(id=1)
    fake_course = _fake_catalog_course(course_overview_id=101, catalog_course_id=999)
    cc_select_related.return_value.get.return_value = fake_course

    can_enroll.return_value = True
    platform_mode.return_value = "none"

    cce_select_for_update.return_value.filter.return_value.first.return_value = None

    course_limit.return_value = False
    is_paid.return_value = True

    with pytest.raises(CourseLimitReached):
        svc.create_or_activate_course_enrollment(user_id=1, catalog_course_id=fake_course.id)
    ensure.assert_not_called()
    upgrade.assert_not_called()
    cce_create.assert_not_called()
    tracking_emit.assert_called_once_with(
        event_name=enrollments_module_no_atomic.EVENT_NAME_COURSE_ENROLLMENT_BLOCKED,
        user_id=1,
        catalog_id=500,
        partner_id=None,
        course_id="101",
        catalog_course_id=999,
        enrollment_mode="none",
        blocked_reason=CourseLimitReached.default_code,
        on_commit=False,
    )


# --------------------------------------------------------------------
# Tests: deactivate_course_enrollment
# --------------------------------------------------------------------

def test_deactivate_course_enrollment_sets_inactive_and_downgrades(
    mocker,
    svc,
):
    cce_select_related = mocker.patch(
        "partner_catalog.services.enrollments.CatalogCourseEnrollment.objects.select_related"
    )
    downgrade = mocker.patch("partner_catalog.services.enrollments.downgrade_to_audit")

    fake = SimpleNamespace(
        id=123,
        user_id=1,
        catalog_course_id=999,
        active=True,
        save=MagicMock(),
    )

    # IMPORTANT: service does objects.select_related(...).get(...)
    cce_select_related.return_value.get.return_value = fake

    svc.deactivate_course_enrollment(catalog_course_enrollment_id=123)

    assert fake.active is False
    fake.save.assert_called_once_with(update_fields=["active"])

    downgrade.assert_called_once_with(user_id=1, catalog_course_id=999)


def test_deactivate_course_enrollment_not_found_raises_validation_error(
    mocker,
    enrollments_module_no_atomic,
    svc,
):
    cce_select_related = mocker.patch(
        "partner_catalog.services.enrollments.CatalogCourseEnrollment.objects.select_related"
    )

    DoesNotExist = enrollments_module_no_atomic.CatalogCourseEnrollment.DoesNotExist
    cce_select_related.return_value.get.side_effect = DoesNotExist()

    with pytest.raises(UserNotEnrolled):
        svc.deactivate_course_enrollment(catalog_course_enrollment_id=9999)


# --------------------------------------------------------------------
# Tests: deactivate_enrollments_by_catalog
# --------------------------------------------------------------------

def test_deactivate_enrollments_by_catalog_updates_and_downgrades_each_owned(
    mocker,
    svc,
):
    cce_filter = mocker.patch("partner_catalog.services.enrollments.CatalogCourseEnrollment.objects.filter")
    downgrade = mocker.patch("partner_catalog.services.enrollments.downgrade_to_audit")

    # First filter().values_list(...) call
    qs1 = MagicMock()
    qs1.values_list.return_value = [111, 222]

    # Second filter().update(...) call
    qs2 = MagicMock()
    qs2.update.return_value = 2

    # Service calls filter twice with same args; return qs1 then qs2
    cce_filter.side_effect = [qs1, qs2]

    svc.deactivate_enrollments_by_catalog(user_id=1, catalog_id=500)

    qs2.update.assert_called_once_with(active=False)

    assert downgrade.call_count == 2
    called_ids = {c.kwargs["catalog_course_id"] for c in downgrade.call_args_list}
    assert called_ids == {111, 222}
