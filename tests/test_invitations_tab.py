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
from partner_catalog.xapi.constants import EVENT_NAME_INVITATION_RESENT
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
    from partner_catalog.api.v1.serializers import (  # pylint: disable=import-outside-toplevel
        CatalogInvitationListSerializer,
    )

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
    from partner_catalog.api.exception_handlers import (  # pylint: disable=import-outside-toplevel
        catalog_exception_handler,
    )
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


# ---------------------------------------------------------------------------
# Permission regression tests
#
# `CatalogLearnerInvitationViewSet` used to declare a `get_permission_classes()`
# method, which is not a DRF hook, so `IsPartnerCatalogManager` was never applied
# and every endpoint was reachable by any authenticated user. These tests pin the
# fix so a future "simplification" back to `IsAuthenticated` fails CI.
# ---------------------------------------------------------------------------

@pytest.fixture
def stranger():
    """An authenticated user who is neither staff nor a manager of any catalog."""
    return make_user()


def _call_invitation_view(action_map, method, path, user, **view_kwargs):
    """Dispatch a CatalogLearnerInvitationViewSet action with the given user."""
    from rest_framework.test import APIRequestFactory  # pylint: disable=import-outside-toplevel

    from partner_catalog.api.v1.views import CatalogLearnerInvitationViewSet  # pylint: disable=import-outside-toplevel

    factory = APIRequestFactory()
    request = getattr(factory, method)(path)
    request.user = user

    view = CatalogLearnerInvitationViewSet.as_view(action_map)
    return view(request, **view_kwargs)


@pytest.mark.django_db
def test_non_manager_cannot_list_invitations(catalog, stranger):
    """A plain authenticated user must get 403 from the invitations list."""
    make_invitation(catalog, invite_email="a@example.com")

    response = _call_invitation_view(
        {"get": "list"},
        "get",
        f"/api/v1/manage/catalogs/{catalog.id}/invitations/",
        stranger,
        catalog_pk=str(catalog.id),
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_non_manager_cannot_cancel_invitation(catalog, stranger):
    """A plain authenticated user must get 403 from the cancel action."""
    invitation = make_invitation(catalog, invite_email="cancel_me@example.com")

    response = _call_invitation_view(
        {"post": "cancel"},
        "post",
        f"/api/v1/manage/catalogs/{catalog.id}/invitations/{invitation.id}/cancel/",
        stranger,
        catalog_pk=str(catalog.id),
        pk=str(invitation.id),
    )

    assert response.status_code == 403
    invitation.refresh_from_db()
    assert invitation.status == Status.SENT


@pytest.mark.django_db
def test_non_manager_cannot_resend_invitation(catalog, stranger, mocker):
    """A plain authenticated user must get 403 from the resend action."""
    mock_delay = mocker.patch(
        "partner_catalog.tasks.emails.send_catalog_invitation_created_email.delay"
    )
    invitation = make_invitation(catalog, invite_email="resend_me@example.com")

    response = _call_invitation_view(
        {"post": "resend"},
        "post",
        f"/api/v1/manage/catalogs/{catalog.id}/invitations/{invitation.id}/resend/",
        stranger,
        catalog_pk=str(catalog.id),
        pk=str(invitation.id),
    )

    assert response.status_code == 403
    mock_delay.assert_not_called()


@pytest.mark.django_db
def test_non_manager_cannot_remove_invitation(catalog, stranger, learner_user):
    """A plain authenticated user must get 403 from the remove action."""
    invitation = make_invitation(
        catalog, invite_email=learner_user.email, user=learner_user,
        accepted_at=timezone.now(),
    )

    response = _call_invitation_view(
        {"post": "remove_invite"},
        "post",
        f"/api/v1/manage/catalogs/{catalog.id}/invitations/{invitation.id}/remove/",
        stranger,
        catalog_pk=str(catalog.id),
        pk=str(invitation.id),
    )

    assert response.status_code == 403
    invitation.refresh_from_db()
    assert invitation.status == Status.ACCEPTED


@pytest.mark.django_db
def test_manager_of_another_catalog_cannot_list_invitations(catalog):
    """Being a manager elsewhere must not grant access to this catalog."""
    other_manager = make_user()
    CatalogManager.objects.create(catalog=make_catalog(), user=other_manager, active=True)
    make_invitation(catalog, invite_email="a@example.com")

    response = _call_invitation_view(
        {"get": "list"},
        "get",
        f"/api/v1/manage/catalogs/{catalog.id}/invitations/",
        other_manager,
        catalog_pk=str(catalog.id),
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_inactive_manager_cannot_list_invitations(catalog):
    """A deactivated CatalogManager must lose access."""
    former_manager = make_user()
    CatalogManager.objects.create(catalog=catalog, user=former_manager, active=False)

    response = _call_invitation_view(
        {"get": "list"},
        "get",
        f"/api/v1/manage/catalogs/{catalog.id}/invitations/",
        former_manager,
        catalog_pk=str(catalog.id),
    )

    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Service-level permission checks for resend
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_resend_invitation_rejected_for_non_manager(service, catalog, mocker):
    """resend_invitation must refuse a user with no claim on the invitation."""
    mock_delay = mocker.patch(
        "partner_catalog.tasks.emails.send_catalog_invitation_created_email.delay"
    )
    invitation = make_invitation(catalog, invite_email="someone@example.com")
    stranger_user = make_user()

    with pytest.raises(ValidationError, match=r"Only pending \(sent\) invitations can be resent\."):
        service.resend_invitation(invitation.id, user=stranger_user)

    mock_delay.assert_not_called()


@pytest.mark.django_db
def test_resend_invitation_allowed_for_ordinary_manager(service, catalog, manager_user, mocker):
    """An ordinary CatalogManager (not staff) must be allowed to resend."""
    mock_delay = mocker.patch(
        "partner_catalog.tasks.emails.send_catalog_invitation_created_email.delay"
    )
    invitation = make_invitation(catalog, invite_email="someone@example.com")

    service.resend_invitation(invitation.id, user=manager_user)

    mock_delay.assert_called_once_with(invitation.id)


@pytest.mark.django_db
def test_resend_invitation_emits_tracking_event(service, catalog, manager_user, mocker):
    """resend_invitation must leave an audit trail even though status is unchanged."""
    mocker.patch("partner_catalog.tasks.emails.send_catalog_invitation_created_email.delay")
    mock_emit = mocker.patch("partner_catalog.services.invitations.emit_catalog_invitation_tracking_event")
    invitation = make_invitation(catalog, invite_email="someone@example.com")

    service.resend_invitation(invitation.id, user=manager_user)

    mock_emit.assert_called_once()
    assert mock_emit.call_args.kwargs["event_name"] == EVENT_NAME_INVITATION_RESENT
    assert mock_emit.call_args.kwargs["actor_user_id"] == manager_user.id


# ---------------------------------------------------------------------------
# CatalogInvitationListSerializer – batched account resolution (no N+1)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_invitation_list_resolves_unlinked_users_in_one_query(catalog, django_assert_num_queries):
    """
    Serializing many invitations with NULL user must issue a single User lookup,
    not one per distinct email.
    """
    from partner_catalog.api.v1.serializers import (  # pylint: disable=import-outside-toplevel
        CatalogInvitationListSerializer,
    )

    invitations = []
    for index in range(5):
        email = f"late_{index}@example.com"
        make_user(username=f"late_user_{index}", email=email)
        invitations.append(make_invitation(catalog, invite_email=email, user=None))

    # 1 query to resolve every unlinked invitee, and nothing per row.
    with django_assert_num_queries(1):
        data = CatalogInvitationListSerializer(invitations, many=True).data

    assert len(data) == 5
    assert all(row["is_registered"] is True for row in data)
    assert {row["username"] for row in data} == {f"late_user_{i}" for i in range(5)}


@pytest.mark.django_db
def test_invitation_list_marks_unregistered_invitees(catalog, django_assert_num_queries):
    """Emails with no account must serialize as not registered, still in one query."""
    from partner_catalog.api.v1.serializers import (  # pylint: disable=import-outside-toplevel
        CatalogInvitationListSerializer,
    )

    invitations = [
        make_invitation(catalog, invite_email=f"ghost_{index}@example.com", user=None)
        for index in range(3)
    ]

    with django_assert_num_queries(1):
        data = CatalogInvitationListSerializer(invitations, many=True).data

    assert all(row["is_registered"] is False for row in data)
    assert all(row["username"] is None for row in data)
