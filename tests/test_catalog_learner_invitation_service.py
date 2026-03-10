"""
Unit tests (NO DB) for CatalogLearnerInvitationService xAPI channel wiring.
"""

from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from partner_catalog.xapi import constants as xapi_constants

# Fixtures are intentionally injected by name in tests.
# pylint: disable=redefined-outer-name


@contextmanager
def _noop_atomic(*args, **kwargs):
    yield


def _immediate_on_commit(func, *args, **kwargs):
    """Execute on_commit callbacks immediately in NO-DB unit tests."""
    del args, kwargs
    func()


@pytest.fixture
def invitations_module_no_atomic(monkeypatch):
    """
    Import partner_catalog.services.invitations and neutralize transaction.atomic.
    """
    import partner_catalog.services.invitations as m  # pylint: disable=import-outside-toplevel
    import partner_catalog.xapi.emitter as xapi_emitter  # pylint: disable=import-outside-toplevel

    monkeypatch.setattr(m.transaction, "atomic", _noop_atomic)
    monkeypatch.setattr(m.transaction, "on_commit", _immediate_on_commit)
    monkeypatch.setattr(xapi_emitter.transaction, "on_commit", _immediate_on_commit)
    monkeypatch.setattr(xapi_emitter, "tracker", None)

    Service = m.CatalogLearnerInvitationService
    fn = getattr(Service, "create_new_invitation", None)
    if fn and hasattr(fn, "__wrapped__"):
        monkeypatch.setattr(Service, "create_new_invitation", fn.__wrapped__)

    return m


def test_create_new_invitation_uses_manual_channel_by_default(mocker, invitations_module_no_atomic):
    service = invitations_module_no_atomic.CatalogLearnerInvitationService()

    mocker.patch.object(service, "_has_active_invitations", return_value=False)
    mocker.patch.object(service, "_get_user_by_email", return_value=SimpleNamespace(id=7))

    fake_invitation = SimpleNamespace(id=10)
    mocker.patch(
        "partner_catalog.services.invitations.CatalogLearnerInvitation.objects.create",
        return_value=fake_invitation,
    )
    emit_invitation_event = mocker.patch.object(service, "_emit_invitation_event")

    service.create_new_invitation(
        invite_email="test@example.com",
        catalog_id=1,
        invited_by=SimpleNamespace(id=3),
    )

    emit_invitation_event.assert_called_once_with(
        fake_invitation,
        actor_user_id=3,
        invitation_channel=xapi_constants.INVITATION_CHANNEL_MANUAL,
    )


def test_create_new_invitation_propagates_explicit_channel(mocker, invitations_module_no_atomic):
    service = invitations_module_no_atomic.CatalogLearnerInvitationService()

    mocker.patch.object(service, "_has_active_invitations", return_value=False)
    mocker.patch.object(service, "_get_user_by_email", return_value=SimpleNamespace(id=7))

    fake_invitation = SimpleNamespace(id=11)
    mocker.patch(
        "partner_catalog.services.invitations.CatalogLearnerInvitation.objects.create",
        return_value=fake_invitation,
    )
    emit_invitation_event = mocker.patch.object(service, "_emit_invitation_event")

    service.create_new_invitation(
        invite_email="test@example.com",
        catalog_id=1,
        invited_by=SimpleNamespace(id=4),
        invitation_channel=xapi_constants.INVITATION_CHANNEL_BULK_CSV,
    )

    emit_invitation_event.assert_called_once_with(
        fake_invitation,
        actor_user_id=4,
        invitation_channel=xapi_constants.INVITATION_CHANNEL_BULK_CSV,
    )


def test_emit_invitation_event_passes_channel_to_tracking_emitter(
    mocker,
    monkeypatch,
    invitations_module_no_atomic,
):
    service = invitations_module_no_atomic.CatalogLearnerInvitationService()
    Status = invitations_module_no_atomic.Status

    # Avoid signal side effects in this unit test.
    monkeypatch.setattr(
        invitations_module_no_atomic.CatalogLearnerInvitationService,
        "_EVENT_MAP",
        {Status.SENT: None},
        raising=False,
    )

    tracking_emit = mocker.patch("partner_catalog.services.invitations.emit_catalog_invitation_tracking_event")

    invitation = SimpleNamespace(status=Status.SENT)

    service._emit_invitation_event(  # pylint: disable=protected-access
        invitation,
        actor_user_id=9,
        invitation_channel=xapi_constants.INVITATION_CHANNEL_SELF_ENROLL,
    )

    tracking_emit.assert_called_once_with(
        event_name=invitations_module_no_atomic.EVENT_NAME_INVITATION_SENT,
        invitation=invitation,
        actor_user_id=9,
        invitation_channel=xapi_constants.INVITATION_CHANNEL_SELF_ENROLL,
    )
