"""
Tests for CatalogLearner Activation (Suite 2).

Covers:
- CatalogLearner.active computed field based on current_invitation.status
- PartnerCatalogService.create_or_update_learner_from_invitation
- PartnerCatalogService.deactivate_learner_from_invitation
"""

import pytest
from django.utils import timezone

from partner_catalog.models import CatalogLearner, CatalogLearnerInvitation
from partner_catalog.services.catalogs import PartnerCatalogService

from tests.factories import make_catalog, make_invitation, make_learner, make_user

Status = CatalogLearnerInvitation.Status


@pytest.fixture
def service():
    return PartnerCatalogService()


@pytest.fixture
def user():
    return make_user()


@pytest.fixture
def catalog():
    return make_catalog()


# ---------------------------------------------------------------------------
# CatalogLearner.active — derived from current_invitation.status
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_learner_active_when_invitation_is_accepted(user, catalog):
    """CatalogLearner.active is True when current_invitation status is ACCEPTED."""
    invitation = make_invitation(catalog, user=user, invite_email=user.email, accepted_at=timezone.now())

    learner = make_learner(catalog, user, invitation)

    assert learner.active is True


@pytest.mark.django_db
def test_learner_inactive_when_invitation_is_sent(user, catalog):
    """CatalogLearner.active is False when current_invitation status is SENT (not yet accepted)."""
    invitation = make_invitation(catalog, user=user, invite_email=user.email)
    # No timestamps set → status == SENT

    learner = make_learner(catalog, user, invitation)

    assert learner.active is False


@pytest.mark.django_db
def test_learner_inactive_when_invitation_is_removed(user, catalog):
    """CatalogLearner.active is False when current_invitation status is REMOVED."""
    # DB constraint cla_removed_implies_accepted requires accepted_at when removed_at is set
    invitation = make_invitation(
        catalog,
        user=user,
        invite_email=user.email,
        accepted_at=timezone.now(),
        removed_at=timezone.now(),
    )
    # _compute_status: removed_at is set → status == REMOVED

    learner = make_learner(catalog, user, invitation)

    assert learner.active is False


@pytest.mark.django_db
def test_learner_inactive_when_invitation_is_declined(user, catalog):
    """CatalogLearner.active is False when current_invitation status is DECLINED."""
    invitation = make_invitation(
        catalog,
        user=user,
        invite_email=user.email,
        declined_at=timezone.now(),
    )
    # _compute_status: declined_at is set → status == DECLINED

    learner = make_learner(catalog, user, invitation)

    assert learner.active is False


# ---------------------------------------------------------------------------
# PartnerCatalogService.create_or_update_learner_from_invitation
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_create_or_update_creates_new_learner(service, user, catalog):
    """create_or_update_learner_from_invitation creates a new CatalogLearner when none exists."""
    invitation = make_invitation(catalog, user=user, invite_email=user.email, accepted_at=timezone.now())

    learner, created = service.create_or_update_learner_from_invitation(invitation.id)

    assert created is True
    assert learner.user == user
    assert learner.catalog == catalog
    assert learner.active is True


@pytest.mark.django_db
def test_create_or_update_reactivates_existing_inactive_learner(service, user, catalog):
    """create_or_update_learner_from_invitation reactivates an existing inactive CatalogLearner."""
    # Step 1: create learner via an ACCEPTED invitation
    invitation_1 = make_invitation(catalog, user=user, invite_email=user.email, accepted_at=timezone.now())
    learner = make_learner(catalog, user, invitation_1)
    # Link invitation_1 to the learner for history tracking (as the service does)
    invitation_1.learner = learner
    invitation_1.save(update_fields=['learner'])
    assert learner.active is True

    # Step 2: transition invitation_1 to REMOVED → learner becomes inactive
    invitation_1.removed_at = timezone.now()
    invitation_1.save()
    learner.save()
    learner.refresh_from_db()
    assert learner.active is False

    # Step 3: create a fresh ACCEPTED invitation for the same user+catalog
    # (invitation_1 is REMOVED/status=40, outside the unique-active constraint on [10, 20])
    invitation_2 = make_invitation(catalog, user=user, invite_email=user.email, accepted_at=timezone.now())

    updated_learner, created = service.create_or_update_learner_from_invitation(invitation_2.id)

    assert created is False                    # existing record was found
    assert updated_learner.id == learner.id    # same CatalogLearner row
    assert updated_learner.active is True      # reactivated


# ---------------------------------------------------------------------------
# PartnerCatalogService.deactivate_learner_from_invitation
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_deactivate_learner_sets_active_false(service, user, catalog):
    """deactivate_learner_from_invitation sets CatalogLearner.active to False."""
    invitation = make_invitation(catalog, user=user, invite_email=user.email, accepted_at=timezone.now())
    learner = make_learner(catalog, user, invitation)
    assert learner.active is True

    # Link invitation → learner so the service can navigate to the learner
    invitation.learner = learner
    invitation.save(update_fields=['learner'])

    # Transition invitation to REMOVED so _compute_active() returns False on next save
    invitation.removed_at = timezone.now()
    invitation.save()

    deactivated = service.deactivate_learner_from_invitation(invitation.id)

    deactivated.refresh_from_db()
    assert deactivated.active is False
