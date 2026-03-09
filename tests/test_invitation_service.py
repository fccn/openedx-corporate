"""
Tests for CatalogLearnerInvitationService - Invitation Lifecycle (Suite 1).

Covers business logic for invitation creation, status transitions, and model-level
constraints (accepted/declined mutual exclusion, unique active invitation).
"""

# pylint: disable=redefined-outer-name

import pytest
from django.db import IntegrityError
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from partner_catalog.models import CatalogLearnerInvitation
from partner_catalog.services.invitations import CatalogLearnerInvitationService
from tests.factories import make_catalog, make_invitation, make_user

Status = CatalogLearnerInvitation.Status


@pytest.fixture
def service():
    return CatalogLearnerInvitationService()


@pytest.fixture
def catalog():
    return make_catalog()


@pytest.fixture
def learner_user():
    return make_user(email="learner@example.com")


# ---------------------------------------------------------------------------
# create_new_invitation
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_create_invitation_has_status_sent(service, catalog, learner_user):
    """create_new_invitation should return an invitation with status SENT."""
    invitation = service.create_new_invitation(
        invite_email=learner_user.email,
        catalog_id=catalog.id,
        emit_event=False,
    )

    assert invitation.status == Status.SENT


@pytest.mark.django_db
def test_create_invitation_raises_if_sent_already_exists(service, catalog, learner_user):
    """create_new_invitation raises ValidationError when a SENT invitation already exists
    for the same (catalog, email)."""
    service.create_new_invitation(
        invite_email=learner_user.email,
        catalog_id=catalog.id,
        emit_event=False,
    )

    with pytest.raises(ValidationError, match=service.ERROR_ACTIVE_INVITATION_EXISTS):
        service.create_new_invitation(
            invite_email=learner_user.email,
            catalog_id=catalog.id,
            emit_event=False,
        )


@pytest.mark.django_db
def test_create_invitation_raises_if_accepted_already_exists(service, catalog, learner_user):
    """create_new_invitation raises ValidationError when an ACCEPTED invitation already exists
    for the same (catalog, email)."""
    # Create and accept an invitation
    invitation = service.create_new_invitation(
        invite_email=learner_user.email,
        catalog_id=catalog.id,
        emit_event=False,
    )
    service.accept_invitation(invitation.id, user=learner_user)

    with pytest.raises(ValidationError, match=service.ERROR_ACTIVE_INVITATION_EXISTS):
        service.create_new_invitation(
            invite_email=learner_user.email,
            catalog_id=catalog.id,
            emit_event=False,
        )


# ---------------------------------------------------------------------------
# accept_invitation
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_accept_invitation_transitions_to_accepted(service, catalog, learner_user):
    """accept_invitation should transition the status from SENT to ACCEPTED and set accepted_at."""
    invitation = service.create_new_invitation(
        invite_email=learner_user.email,
        catalog_id=catalog.id,
        emit_event=False,
    )

    accepted = service.accept_invitation(invitation.id, user=learner_user)

    assert accepted.status == Status.ACCEPTED
    assert accepted.accepted_at is not None


@pytest.mark.django_db
def test_accept_invitation_raises_when_already_declined(service, catalog, learner_user):
    """accept_invitation raises ValidationError when the invitation status is DECLINED."""
    invitation = service.create_new_invitation(
        invite_email=learner_user.email,
        catalog_id=catalog.id,
        emit_event=False,
    )
    service.decline_invitation(invitation.id, user=learner_user)

    with pytest.raises(ValidationError, match=service.ERROR_ACCEPT_NOT_ALLOWED):
        service.accept_invitation(invitation.id, user=learner_user)


@pytest.mark.django_db
def test_accept_invitation_raises_when_already_removed(service, catalog, learner_user):
    """accept_invitation raises ValidationError when the invitation status is REMOVED."""
    invitation = service.create_new_invitation(
        invite_email=learner_user.email,
        catalog_id=catalog.id,
        emit_event=False,
    )
    # accept → remove
    service.accept_invitation(invitation.id, user=learner_user)
    service.remove_invitation(invitation.id, user=learner_user)

    with pytest.raises(ValidationError, match=service.ERROR_ACCEPT_NOT_ALLOWED):
        service.accept_invitation(invitation.id, user=learner_user)


# ---------------------------------------------------------------------------
# decline_invitation
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_decline_invitation_transitions_to_declined(service, catalog, learner_user):
    """decline_invitation should transition the status from SENT to DECLINED and set declined_at."""
    invitation = service.create_new_invitation(
        invite_email=learner_user.email,
        catalog_id=catalog.id,
        emit_event=False,
    )

    declined = service.decline_invitation(invitation.id, user=learner_user)

    assert declined.status == Status.DECLINED
    assert declined.declined_at is not None


@pytest.mark.django_db
def test_decline_invitation_raises_when_already_accepted(service, catalog, learner_user):
    """decline_invitation raises ValidationError when the invitation status is ACCEPTED."""
    invitation = service.create_new_invitation(
        invite_email=learner_user.email,
        catalog_id=catalog.id,
        emit_event=False,
    )
    service.accept_invitation(invitation.id, user=learner_user)

    with pytest.raises(ValidationError, match=service.ERROR_DECLINE_NOT_ALLOWED):
        service.decline_invitation(invitation.id, user=learner_user)


@pytest.mark.django_db
def test_decline_invitation_raises_when_already_removed(service, catalog, learner_user):
    """decline_invitation raises ValidationError when the invitation status is REMOVED."""
    invitation = service.create_new_invitation(
        invite_email=learner_user.email,
        catalog_id=catalog.id,
        emit_event=False,
    )
    service.accept_invitation(invitation.id, user=learner_user)
    service.remove_invitation(invitation.id, user=learner_user)

    with pytest.raises(ValidationError, match=service.ERROR_DECLINE_NOT_ALLOWED):
        service.decline_invitation(invitation.id, user=learner_user)


# ---------------------------------------------------------------------------
# remove_invitation
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_remove_invitation_transitions_to_removed(service, catalog, learner_user):
    """remove_invitation should transition the status from ACCEPTED to REMOVED, setting removed_at and removed_by."""
    invitation = service.create_new_invitation(
        invite_email=learner_user.email,
        catalog_id=catalog.id,
        emit_event=False,
    )
    service.accept_invitation(invitation.id, user=learner_user)

    removed = service.remove_invitation(invitation.id, user=learner_user)

    assert removed.status == Status.REMOVED
    assert removed.removed_at is not None
    assert removed.removed_by == learner_user


@pytest.mark.django_db
def test_remove_invitation_allowed_by_staff(service, catalog, learner_user):
    """remove_invitation should be allowed when a staff user performs the removal."""
    staff = make_user(is_staff=True)
    invitation = service.create_new_invitation(
        invite_email=learner_user.email,
        catalog_id=catalog.id,
        emit_event=False,
    )
    service.accept_invitation(invitation.id, user=learner_user)

    removed = service.remove_invitation(invitation.id, user=staff)

    assert removed.status == Status.REMOVED


@pytest.mark.django_db
def test_remove_invitation_raises_when_sent(service, catalog, learner_user):
    """remove_invitation raises ValidationError when the invitation has not been accepted yet (status SENT)."""
    invitation = service.create_new_invitation(
        invite_email=learner_user.email,
        catalog_id=catalog.id,
        emit_event=False,
    )

    with pytest.raises(ValidationError, match=service.ERROR_REMOVE_NOT_ALLOWED):
        service.remove_invitation(invitation.id, user=learner_user)


@pytest.mark.django_db
def test_remove_invitation_raises_when_declined(service, catalog, learner_user):
    """remove_invitation raises ValidationError when the invitation status is DECLINED."""
    invitation = service.create_new_invitation(
        invite_email=learner_user.email,
        catalog_id=catalog.id,
        emit_event=False,
    )
    service.decline_invitation(invitation.id, user=learner_user)

    with pytest.raises(ValidationError, match=service.ERROR_REMOVE_NOT_ALLOWED):
        service.remove_invitation(invitation.id, user=learner_user)


# ---------------------------------------------------------------------------
# Status derivation from timestamps (_compute_status)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_status_is_sent_when_no_timestamps(catalog):
    """An invitation with no timestamps should have status SENT."""
    invitation = make_invitation(catalog, invite_email="new@example.com")
    assert invitation.status == Status.SENT


@pytest.mark.django_db
def test_status_is_accepted_when_accepted_at_is_set(catalog):
    """An invitation with accepted_at set (and no other timestamps) should have status ACCEPTED."""
    invitation = make_invitation(
        catalog,
        invite_email="accepted@example.com",
        accepted_at=timezone.now(),
    )
    assert invitation.status == Status.ACCEPTED


@pytest.mark.django_db
def test_status_is_declined_when_declined_at_is_set(catalog):
    """An invitation with declined_at set (and no accepted/removed timestamps) should have status DECLINED."""
    invitation = make_invitation(
        catalog,
        invite_email="declined@example.com",
        declined_at=timezone.now(),
    )
    assert invitation.status == Status.DECLINED


@pytest.mark.django_db
def test_status_is_removed_when_removed_at_is_set(catalog):
    """An invitation with removed_at set should have status REMOVED (takes priority)."""
    invitation = make_invitation(
        catalog,
        invite_email="removed@example.com",
        accepted_at=timezone.now(),
        removed_at=timezone.now(),
    )
    assert invitation.status == Status.REMOVED


# ---------------------------------------------------------------------------
# Model constraint: accepted_at and declined_at cannot both be set
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_cannot_set_both_accepted_and_declined_at(catalog):
    """DB check constraint should prevent an invitation from having both accepted_at and declined_at set."""
    with pytest.raises((IntegrityError, Exception)):
        make_invitation(
            catalog,
            invite_email="conflict@example.com",
            accepted_at=timezone.now(),
            declined_at=timezone.now(),
        )
