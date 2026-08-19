"""
Tests for the new Invitations tab backend work:
  - cancel_invitation service method
  - resend_invitation service method
  - _validate_invitation_status_access fixes
  - CatalogInvitationListSerializer is_registered trap
  - CatalogLearnerInvitationViewSet list/filter/search/cancel/resend actions
  - catalog_exception_handler
"""

# pylint: disable=redefined-outer-name

import pytest
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from partner_catalog.models import CatalogLearnerInvitation, CatalogManager
from partner_catalog.services.invitations import CatalogLearnerInvitationService
from tests.factories import make_catalog, make_invitation, make_learner, make_user

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


@pytest.fixture
def manager_user(catalog):
    user = make_user()
    CatalogManager.objects.create(catalog=catalog, user=user, active=True)
    return user


# ---------------------------------------------------------------------------
# cancel_invitation
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_cancel_invitation_transitions_to_cancelled(service, catalog, learner_user):
    """cancel_invitation should transition SENT → CANCELLED and set cancelled_at/cancelled_by."""
    invitation = make_invitation(catalog, invite_email=learner_user.email, user=learner_user)
    manager = make_user(is_staff=True)

    cancelled = service.cancel_invitation(invitation.id, user=manager)

    assert cancelled.status == Status.CANCELLED
    assert cancelled.cancelled_at is not None
    assert cancelled.cancelled_by == manager


@pytest.mark.django_db
def test_cancel_invitation_rejected_from_accepted(service, catalog, learner_user):
    """cancel_invitation must raise when invitation is ACCEPTED."""
    invitation = make_invitation(
        catalog, invite_email=learner_user.email, user=learner_user,
        accepted_at=timezone.now(),
    )
    manager = make_user(is_staff=True)

    with pytest.raises(ValidationError, match=service.ERROR_CANCEL_NOT_ALLOWED):
        service.cancel_invitation(invitation.id, user=manager)


@pytest.mark.django_db
def test_cancel_invitation_rejected_from_declined(service, catalog, learner_user):
    """cancel_invitation must raise when invitation is DECLINED."""
    invitation = make_invitation(
        catalog, invite_email=learner_user.email, user=learner_user,
        declined_at=timezone.now(),
    )
    manager = make_user(is_staff=True)

    with pytest.raises(ValidationError, match=service.ERROR_CANCEL_NOT_ALLOWED):
        service.cancel_invitation(invitation.id, user=manager)


@pytest.mark.django_db
def test_cancel_invitation_rejected_from_removed(service, catalog, learner_user):
    """cancel_invitation must raise when invitation is REMOVED."""
    invitation = make_invitation(
        catalog, invite_email=learner_user.email, user=learner_user,
        accepted_at=timezone.now(), removed_at=timezone.now(),
    )
    manager = make_user(is_staff=True)

    with pytest.raises(ValidationError, match=service.ERROR_CANCEL_NOT_ALLOWED):
        service.cancel_invitation(invitation.id, user=manager)


@pytest.mark.django_db
def test_reinvite_after_cancel_succeeds(service, catalog, learner_user):
    """Re-inviting a cancelled email must succeed (unique constraint must not block it)."""
    invitation = make_invitation(catalog, invite_email=learner_user.email, user=learner_user)
    manager = make_user(is_staff=True)
    service.cancel_invitation(invitation.id, user=manager)

    new_invitation = service.create_new_invitation(
        invite_email=learner_user.email,
        catalog_id=catalog.id,
        emit_event=False,
    )

    assert new_invitation.status == Status.SENT
    assert new_invitation.id != invitation.id


# ---------------------------------------------------------------------------
# resend_invitation
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_resend_invitation_enqueues_email(service, catalog, learner_user, mocker):
    """resend_invitation should call the email task for a SENT invitation."""
    invitation = make_invitation(catalog, invite_email=learner_user.email, user=learner_user)
    mock_delay = mocker.patch(
        "partner_catalog.tasks.emails.send_catalog_invitation_created_email.delay"
    )
    manager = make_user(is_staff=True)

    result = service.resend_invitation(invitation.id, user=manager)

    assert result.id == invitation.id
    mock_delay.assert_called_once_with(invitation.id)


@pytest.mark.django_db
def test_resend_invitation_rejected_for_non_sent(service, catalog, learner_user):
    """resend_invitation must raise for non-SENT invitations."""
    invitation = make_invitation(
        catalog, invite_email=learner_user.email, user=learner_user,
        declined_at=timezone.now(),
    )
    manager = make_user(is_staff=True)

    with pytest.raises(ValidationError, match=r"Only pending \(sent\) invitations can be resent\."):
        service.resend_invitation(invitation.id, user=manager)


# ---------------------------------------------------------------------------
# _validate_invitation_status_access – CatalogManager can cancel/remove
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_ordinary_manager_can_cancel(service, catalog, learner_user, manager_user):
    """An ordinary CatalogManager (not staff) must be allowed to cancel."""
    invitation = make_invitation(catalog, invite_email=learner_user.email, user=learner_user)

    cancelled = service.cancel_invitation(invitation.id, user=manager_user)

    assert cancelled.status == Status.CANCELLED


@pytest.mark.django_db
def test_ordinary_manager_can_remove(service, catalog, learner_user, manager_user):
    """An ordinary CatalogManager (not staff) must be allowed to remove an accepted invitation."""
    invitation = make_invitation(
        catalog, invite_email=learner_user.email, user=learner_user,
        accepted_at=timezone.now(),
    )
    learner = make_learner(catalog=catalog, user=learner_user, invitation=invitation)
    invitation.learner = learner
    invitation.save(update_fields=["learner"])

    removed = service.remove_invitation(invitation.id, user=manager_user)

    assert removed.status == Status.REMOVED


# ---------------------------------------------------------------------------
# CatalogInvitationListSerializer – is_registered trap
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_is_registered_true_for_user_who_registered_after_invite(catalog):
    """
    is_registered must return True even when invitation.user is NULL because
    the invitee registered after receiving the invite.
    """
    from partner_catalog.api.v1.serializers import CatalogInvitationListSerializer  # pylint: disable=import-outside-toplevel

    late_registrant = make_user(email="late@example.com")
    invitation = make_invitation(catalog, invite_email=late_registrant.email, user=None)

    assert invitation.user is None

    serializer = CatalogInvitationListSerializer(invitation)
    data = serializer.data

    assert data["is_registered"] is True
    assert data["username"] == late_registrant.username


# ---------------------------------------------------------------------------
# catalog_exception_handler – returns code alongside detail
# ---------------------------------------------------------------------------

def test_exception_handler_adds_code_to_response():
    """catalog_exception_handler must add 'code' to the response body."""
    from partner_catalog.api.exception_handlers import catalog_exception_handler  # pylint: disable=import-outside-toplevel
    from partner_catalog.exceptions import UserLimitReached  # pylint: disable=import-outside-toplevel

    exc = UserLimitReached()
    context = {"view": None, "request": None}
    response = catalog_exception_handler(exc, context)

    assert response is not None
    assert response.data.get("code") == "user_limit_reached"
    assert "detail" in response.data


# ---------------------------------------------------------------------------
# API endpoint tests using APIRequestFactory (bypasses full middleware stack)
# ---------------------------------------------------------------------------

@pytest.fixture
def rf_manager(manager_user):
    """APIRequestFactory with pre-authenticated manager user."""
    from rest_framework.test import APIRequestFactory  # pylint: disable=import-outside-toplevel
    factory = APIRequestFactory()
    factory.user = manager_user
    return factory, manager_user


@pytest.mark.django_db
def test_invitation_list_returns_all_invitations(catalog, manager_user):
    """The list viewset should return invitations scoped to the catalog."""
    from rest_framework.test import APIRequestFactory  # pylint: disable=import-outside-toplevel
    from partner_catalog.api.v1.views import CatalogLearnerInvitationViewSet  # pylint: disable=import-outside-toplevel

    make_invitation(catalog, invite_email="a@example.com")
    make_invitation(catalog, invite_email="b@example.com")

    factory = APIRequestFactory()
    request = factory.get(f"/api/v1/manage/catalogs/{catalog.id}/invitations/")
    request.user = manager_user

    view = CatalogLearnerInvitationViewSet.as_view({"get": "list"})
    response = view(request, catalog_pk=str(catalog.id))

    assert response.status_code == 200
    results = response.data.get("results", response.data) if isinstance(response.data, dict) else response.data
    assert len(results) == 2


@pytest.mark.django_db
def test_invitation_list_status_filter(catalog, manager_user):
    """status filter should narrow results to matching status value."""
    from rest_framework.test import APIRequestFactory  # pylint: disable=import-outside-toplevel
    from partner_catalog.api.v1.views import CatalogLearnerInvitationViewSet  # pylint: disable=import-outside-toplevel

    make_invitation(catalog, invite_email="pending@example.com")
    make_invitation(catalog, invite_email="cancelled@example.com", cancelled_at=timezone.now())

    factory = APIRequestFactory()
    request = factory.get(f"/api/v1/manage/catalogs/{catalog.id}/invitations/", {"status": "10"})
    request.user = manager_user

    view = CatalogLearnerInvitationViewSet.as_view({"get": "list"})
    response = view(request, catalog_pk=str(catalog.id))

    assert response.status_code == 200
    results = response.data.get("results", response.data) if isinstance(response.data, dict) else response.data
    assert len(results) == 1
    assert results[0]["status"] == "pending"


@pytest.mark.django_db
def test_invitation_list_search(catalog, manager_user):
    """search should filter invitations by email substring."""
    from rest_framework.test import APIRequestFactory  # pylint: disable=import-outside-toplevel
    from partner_catalog.api.v1.views import CatalogLearnerInvitationViewSet  # pylint: disable=import-outside-toplevel

    make_invitation(catalog, invite_email="searchme@example.com")
    make_invitation(catalog, invite_email="other@example.com")

    factory = APIRequestFactory()
    request = factory.get(
        f"/api/v1/manage/catalogs/{catalog.id}/invitations/", {"search": "searchme"}
    )
    request.user = manager_user

    view = CatalogLearnerInvitationViewSet.as_view({"get": "list"})
    response = view(request, catalog_pk=str(catalog.id))

    assert response.status_code == 200
    results = response.data.get("results", response.data) if isinstance(response.data, dict) else response.data
    assert len(results) == 1


@pytest.mark.django_db
def test_cancel_action_endpoint(catalog, manager_user):
    """POST .../invitations/{pk}/cancel/ must cancel a pending invitation."""
    from rest_framework.test import APIRequestFactory  # pylint: disable=import-outside-toplevel
    from partner_catalog.api.v1.views import CatalogLearnerInvitationViewSet  # pylint: disable=import-outside-toplevel

    invitation = make_invitation(catalog, invite_email="to_cancel@example.com")

    factory = APIRequestFactory()
    request = factory.post(
        f"/api/v1/manage/catalogs/{catalog.id}/invitations/{invitation.id}/cancel/"
    )
    request.user = manager_user

    view = CatalogLearnerInvitationViewSet.as_view({"post": "cancel"})
    response = view(request, catalog_pk=str(catalog.id), pk=str(invitation.id))

    assert response.status_code == 200
    assert response.data["status"] == "cancelled"


@pytest.mark.django_db
def test_resend_action_endpoint(catalog, manager_user, mocker):
    """POST .../invitations/{pk}/resend/ must enqueue the email task."""
    from rest_framework.test import APIRequestFactory  # pylint: disable=import-outside-toplevel
    from partner_catalog.api.v1.views import CatalogLearnerInvitationViewSet  # pylint: disable=import-outside-toplevel

    mocker.patch("partner_catalog.tasks.emails.send_catalog_invitation_created_email.delay")
    invitation = make_invitation(catalog, invite_email="to_resend@example.com")

    factory = APIRequestFactory()
    request = factory.post(
        f"/api/v1/manage/catalogs/{catalog.id}/invitations/{invitation.id}/resend/"
    )
    request.user = manager_user

    view = CatalogLearnerInvitationViewSet.as_view({"post": "resend"})
    response = view(request, catalog_pk=str(catalog.id), pk=str(invitation.id))

    assert response.status_code == 200
