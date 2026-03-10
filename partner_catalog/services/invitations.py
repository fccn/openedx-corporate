"""
Service layer for handling invitation status transitions and persistence.

This module provides the InvitationService class, which encapsulates business logic
for updating the status of CatalogCourseEnrollmentAllowed invitations, including
timestamp management and atomic database updates. It delegates event emission to
Django model signals, ensuring side effects are handled consistently elsewhere.
"""

from celery.result import AsyncResult
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from partner_catalog.events.data import CatalogLearnerInvitationData
from partner_catalog.events.signals import (
    CATALOG_LEARNER_INVITATION_ACCEPTED_V1,
    CATALOG_LEARNER_INVITATION_CREATED_V1,
    CATALOG_LEARNER_INVITATION_DECLINED_V1,
    CATALOG_LEARNER_INVITATION_REMOVED_V1,
)
from partner_catalog.helpers.email import normalize_email
from partner_catalog.models import CatalogLearnerInvitation
from partner_catalog.xapi.constants import (
    EVENT_NAME_INVITATION_ACCEPTED,
    EVENT_NAME_INVITATION_DECLINED,
    EVENT_NAME_INVITATION_REMOVED,
    EVENT_NAME_INVITATION_SENT,
    INVITATION_CHANNEL_MANUAL,
)
from partner_catalog.xapi.emitter import emit_catalog_invitation_tracking_event

User = get_user_model()
Status = CatalogLearnerInvitation.Status


class CatalogLearnerInvitationService:
    """
    Service for managing CatalogLearnerInvitation status transitions.

    This service handles creating, accepting, and declining invitations,
    managing status timestamps, and ensuring atomic updates to the database.
    """

    ERROR_ACTIVE_INVITATION_EXISTS = "An active invitation already exists for this user."
    ERROR_DECLINE_NOT_ALLOWED = "This invitation can not be declined."
    ERROR_ACCEPT_NOT_ALLOWED = "This invitation can not be accepted."
    ERROR_REMOVE_NOT_ALLOWED = "This invitation can not be removed."
    ERROR_INVITATION_NOT_FOUND = "Invitation not found."

    _EVENT_MAP = {
        Status.SENT: CATALOG_LEARNER_INVITATION_CREATED_V1,
        Status.ACCEPTED: CATALOG_LEARNER_INVITATION_ACCEPTED_V1,
        Status.DECLINED: CATALOG_LEARNER_INVITATION_DECLINED_V1,
        Status.REMOVED: CATALOG_LEARNER_INVITATION_REMOVED_V1,
    }
    _TRACKING_EVENT_MAP = {
        Status.SENT: EVENT_NAME_INVITATION_SENT,
        Status.ACCEPTED: EVENT_NAME_INVITATION_ACCEPTED,
        Status.DECLINED: EVENT_NAME_INVITATION_DECLINED,
        Status.REMOVED: EVENT_NAME_INVITATION_REMOVED,
    }

    ALLOWED_TRANSITIONS = {
        Status.SENT: [Status.ACCEPTED, Status.DECLINED],
        Status.ACCEPTED: [Status.REMOVED],
        Status.DECLINED: [],
        Status.REMOVED: [],
        Status.FAILED: [],
    }

    @transaction.atomic
    def create_new_invitation(
        self,
        invite_email: str,
        catalog_id: int,
        invited_by=None,
        emit_event=True,
        invitation_channel: str = INVITATION_CHANNEL_MANUAL,
    ):
        """
        Create a new CatalogLearnerInvitation.
        """
        if self._has_active_invitations(invite_email, catalog_id):
            raise ValidationError(self.ERROR_ACTIVE_INVITATION_EXISTS)

        user = self._get_user_by_email(invite_email)
        try:
            invitation = CatalogLearnerInvitation.objects.create(
                invite_email=normalize_email(invite_email),
                catalog_id=catalog_id,
                user=user,
                invited_by=invited_by,
            )
        except IntegrityError as exc:
            raise ValidationError(self.ERROR_ACTIVE_INVITATION_EXISTS) from exc

        if emit_event:
            self._emit_invitation_event(
                invitation,
                actor_user_id=getattr(invited_by, "id", None),
                invitation_channel=invitation_channel,
            )
        return invitation

    def _transition_status(
        self,
        invitation: CatalogLearnerInvitation,
        new_status: Status,
        user,
        timestamp_field: str,
        *,
        extra_updates: dict = None,
        error_msg: str = "",
    ):
        """
        Generic method to transition an invitation to a new status.
        Handles validation, timestamp updates, extra field updates, saving, and event emission.
        """

        if not self._is_status_transition_allowed(invitation, new_status):
            raise ValidationError(error_msg or f"Cannot transition to {new_status}")

        if not self._validate_invitation_status_access(user, invitation, new_status):
            raise ValidationError(error_msg or "Unauthorized to perform this action")

        if timestamp_field:
            setattr(invitation, timestamp_field, timezone.now())

        if extra_updates:
            for field, value in extra_updates.items():
                setattr(invitation, field, value)

        invitation.save()
        self._emit_invitation_event(invitation, actor_user_id=getattr(user, "id", None))

        return invitation

    @transaction.atomic
    def decline_invitation(self, invitation_id: int, user):
        """
        Decline an existing CatalogLearnerInvitation.
        Update status and timestamps accordingly.
        """
        invitation = self.get_invitation_or_raise(invitation_id)
        return self._transition_status(
            invitation=invitation,
            new_status=Status.DECLINED,
            user=user,
            timestamp_field='declined_at',
            error_msg=self.ERROR_DECLINE_NOT_ALLOWED,
        )

    @transaction.atomic
    def accept_invitation(self, invitation_id: int, user):
        """
        Accept an existing CatalogLearnerInvitation.
        Update status and timestamps accordingly.
        """
        invitation = self.get_invitation_or_raise(invitation_id)
        return self._transition_status(
            invitation=invitation,
            new_status=Status.ACCEPTED,
            user=user,
            timestamp_field='accepted_at',
            extra_updates={'user': user},
            error_msg=self.ERROR_ACCEPT_NOT_ALLOWED,
        )

    @transaction.atomic
    def remove_invitation(self, invitation_id: int, user):
        """
        Mark as removed an existing CatalogLearnerInvitation.
        Update status and timestamps accordingly.
        """
        invitation = self.get_invitation_or_raise(invitation_id)
        return self._transition_status(
            invitation=invitation,
            new_status=Status.REMOVED,
            user=user,
            timestamp_field='removed_at',
            extra_updates={'removed_by': user},
            error_msg=self.ERROR_REMOVE_NOT_ALLOWED,
        )

    def get_invitation_or_raise(self, invitation_id: int) -> CatalogLearnerInvitation:
        """
        Get an invitation by ID or raise ValidationError if not found.
        """
        try:
            return CatalogLearnerInvitation.objects.get(id=invitation_id)
        except CatalogLearnerInvitation.DoesNotExist as exc:
            raise ValidationError(self.ERROR_INVITATION_NOT_FOUND) from exc

    def get_latest_sent_invitation(self, user, catalog):
        """
        Get the latest pending (sent) invitation for a user in a catalog.

        Args:
            user: The user to check for.
            catalog: The catalog to check in.
        Returns:
            The pending CatalogLearnerInvitation instance, or None if not found.
        """

        invitation = CatalogLearnerInvitation.objects.filter(
            catalog=catalog,
            status=Status.SENT
        ).filter(
            Q(user=user) | Q(invite_email=user.email)
        ).order_by('-invited_at').first()

        return invitation

    def _emit_invitation_event(
        self,
        invitation: CatalogLearnerInvitation,
        actor_user_id: int = None,
        invitation_channel: str | None = None,
    ):
        """
        Emit invitation lifecycle events for both Open edX signals and tracking.

        Uses the status computed from the timestamps updated during the save()
        operation.
        """
        status = invitation.status
        signal = self._EVENT_MAP.get(status)
        tracking_event_name = self._TRACKING_EVENT_MAP.get(status)

        if not signal and not tracking_event_name:
            return

        if signal:
            event_data = self._to_event_data(invitation)
            signal.send_event(invitation=event_data)

        if tracking_event_name:
            emit_catalog_invitation_tracking_event(
                event_name=tracking_event_name,
                invitation=invitation,
                actor_user_id=actor_user_id,
                invitation_channel=invitation_channel,
            )

    def _is_status_transition_allowed(self, invitation, new_status: Status):
        """Return True if invitation can transition from its current status to new_status."""
        current = invitation.status

        return new_status in self.ALLOWED_TRANSITIONS.get(current, [])

    def _validate_invitation_status_access(self, user, invitation, new_status: Status) -> bool:
        """
        Validate if the given user can perform the status transition on the invitation.
        """
        is_invitation_user = (user == invitation.user or user.email == invitation.invite_email)
        if new_status in [Status.ACCEPTED, Status.DECLINED]:
            return getattr(user, "is_authenticated", False) and is_invitation_user
        elif new_status == Status.REMOVED:
            return is_invitation_user or user.is_staff or user.is_superuser
        return False

    def _get_user_by_email(self, invite_email: str):
        """
        Validate if a user with the given email exists.
        Normalize email before lookup.
        """
        normalized_email = normalize_email(invite_email)
        return User.objects.filter(email=normalized_email).first()

    def _has_active_invitations(self, invite_email: str, catalog_id: int):
        """
        Validate if an invitation already exists for the given user and catalog.
        Normalize email before lookup.
        """
        normalized_email = normalize_email(invite_email)
        return CatalogLearnerInvitation.objects.filter(
            invite_email=normalized_email,
            catalog_id=catalog_id,
            status__in=[Status.SENT, Status.ACCEPTED]
        ).exists()

    def get_task_status(self, task_id: str) -> dict:
        """
        Get the status of a Celery task.
        """
        task_result = AsyncResult(task_id)
        response_data = {
            "task_id": task_id,
            "status": task_result.status,
        }

        if task_result.ready():
            if task_result.successful():
                response_data["result"] = task_result.result
            else:
                response_data["error"] = str(task_result.info)

        return response_data

    def _to_event_data(self, invitation: CatalogLearnerInvitation):
        """
        Convert a CatalogLearnerInvitation instance to event data structure.
        """
        return CatalogLearnerInvitationData(
            id=invitation.id,
            catalog_id=invitation.catalog_id,
            status=invitation.get_status_display(),
            invited_at=invitation.invited_at,
            invite_email=invitation.invite_email,
            user_id=invitation.user_id,
            learner_id=invitation.learner_id,
            invited_by_id=invitation.invited_by_id,
            accepted_at=invitation.accepted_at,
            declined_at=invitation.declined_at,
            removed_at=invitation.removed_at,
            removed_by_id=invitation.removed_by_id,
        )
