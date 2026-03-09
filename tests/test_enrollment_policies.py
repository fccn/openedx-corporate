"""
Tests for Catalog Enrollment Policies (Suite 6).

Covers:
- validate_catalog_enrollment_request: raises on unavailable catalog or non-ACCEPTED invitation
- has_catalog_capacity: user_limit=0 means no limit; blocks when limit is reached
- is_catalog_available: combines catalog.active + has_catalog_capacity

Note: course_enrollments_limit is a model field but is not enforced by any
policy function in the current code — those test plan items are N/A.
"""

from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from partner_catalog.policies.catalogs import (
    has_catalog_capacity,
    is_catalog_available,
    validate_catalog_enrollment_request,
)
from tests.factories import make_catalog, make_invitation, make_learner, make_user


# ---------------------------------------------------------------------------
# has_catalog_capacity
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_catalog_has_capacity_when_user_limit_is_zero():
    """has_catalog_capacity returns True when user_limit=0 (no limit enforced)."""
    catalog = make_catalog(user_limit=0)

    assert has_catalog_capacity(catalog=catalog) is True


@pytest.mark.django_db
def test_catalog_has_capacity_when_below_user_limit():
    """has_catalog_capacity returns True when active learner count is below user_limit."""
    catalog = make_catalog(user_limit=5)
    # 2 active learners, limit is 5 → still capacity
    for _ in range(2):
        user = make_user()
        invitation = make_invitation(catalog, user=user, invite_email=user.email, accepted_at=timezone.now())
        make_learner(catalog, user, invitation)

    assert has_catalog_capacity(catalog=catalog) is True


@pytest.mark.django_db
def test_catalog_at_capacity_when_user_limit_reached():
    """has_catalog_capacity returns False when active learner count equals user_limit."""
    catalog = make_catalog(user_limit=2)
    for _ in range(2):
        user = make_user()
        invitation = make_invitation(catalog, user=user, invite_email=user.email, accepted_at=timezone.now())
        make_learner(catalog, user, invitation)

    assert has_catalog_capacity(catalog=catalog) is False


# ---------------------------------------------------------------------------
# is_catalog_available
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_catalog_available_when_active_and_has_capacity():
    """is_catalog_available returns True when catalog is active and has remaining capacity."""
    now = timezone.now()
    catalog = make_catalog(
        available_start_date=now - timedelta(days=1),
        available_end_date=now + timedelta(days=1),
        user_limit=0,
    )

    assert is_catalog_available(catalog=catalog) is True


@pytest.mark.django_db
def test_catalog_unavailable_when_outside_date_window():
    """is_catalog_available returns False when catalog is not active (past end date)."""
    now = timezone.now()
    catalog = make_catalog(
        available_start_date=now - timedelta(days=2),
        available_end_date=now - timedelta(days=1),
        user_limit=0,
    )

    assert is_catalog_available(catalog=catalog) is False


@pytest.mark.django_db
def test_catalog_unavailable_when_user_limit_reached():
    """is_catalog_available returns False when the catalog has reached its user limit."""
    now = timezone.now()
    catalog = make_catalog(
        available_start_date=now - timedelta(days=1),
        available_end_date=now + timedelta(days=1),
        user_limit=1,
    )
    user = make_user()
    invitation = make_invitation(catalog, user=user, invite_email=user.email, accepted_at=timezone.now())
    make_learner(catalog, user, invitation)

    assert is_catalog_available(catalog=catalog) is False


# ---------------------------------------------------------------------------
# validate_catalog_enrollment_request
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_enrollment_allowed_when_catalog_available_and_invitation_accepted():
    """validate_catalog_enrollment_request does not raise when catalog is available and invitation is ACCEPTED."""
    now = timezone.now()
    catalog = make_catalog(
        available_start_date=now - timedelta(days=1),
        available_end_date=now + timedelta(days=1),
        user_limit=0,
    )
    user = make_user()
    invitation = make_invitation(catalog, user=user, invite_email=user.email, accepted_at=timezone.now())

    # Should not raise
    validate_catalog_enrollment_request(invitation=invitation)


@pytest.mark.django_db
def test_enrollment_blocked_when_catalog_not_active():
    """validate_catalog_enrollment_request raises ValidationError when catalog is outside its date window."""
    now = timezone.now()
    catalog = make_catalog(
        available_start_date=now - timedelta(days=2),
        available_end_date=now - timedelta(days=1),
        user_limit=0,
    )
    user = make_user()
    invitation = make_invitation(catalog, user=user, invite_email=user.email, accepted_at=timezone.now())

    with pytest.raises(ValidationError, match="not available"):
        validate_catalog_enrollment_request(invitation=invitation)


@pytest.mark.django_db
def test_enrollment_blocked_when_catalog_at_user_limit():
    """validate_catalog_enrollment_request raises ValidationError when catalog has reached its user limit."""
    now = timezone.now()
    catalog = make_catalog(
        available_start_date=now - timedelta(days=1),
        available_end_date=now + timedelta(days=1),
        user_limit=1,
    )
    # Fill the one slot
    existing_user = make_user()
    existing_invitation = make_invitation(
        catalog, user=existing_user, invite_email=existing_user.email, accepted_at=timezone.now()
    )
    make_learner(catalog, existing_user, existing_invitation)

    # A second user tries to enroll
    new_user = make_user()
    new_invitation = make_invitation(
        catalog, user=new_user, invite_email=new_user.email, accepted_at=timezone.now()
    )

    with pytest.raises(ValidationError, match="not available"):
        validate_catalog_enrollment_request(invitation=new_invitation)


@pytest.mark.django_db
def test_enrollment_blocked_when_invitation_not_accepted():
    """validate_catalog_enrollment_request raises ValidationError when invitation status is not ACCEPTED."""
    now = timezone.now()
    catalog = make_catalog(
        available_start_date=now - timedelta(days=1),
        available_end_date=now + timedelta(days=1),
        user_limit=0,
    )
    user = make_user()
    # Invitation in SENT state (no accepted_at)
    invitation = make_invitation(catalog, user=user, invite_email=user.email)

    with pytest.raises(ValidationError, match="must be accepted"):
        validate_catalog_enrollment_request(invitation=invitation)
