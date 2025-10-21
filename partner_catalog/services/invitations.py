"""
Service layer for handling invitation status transitions and persistence.

This module provides the InvitationService class, which encapsulates business logic
for updating the status of CatalogCourseEnrollmentAllowed invitations, including
timestamp management and atomic database updates. It delegates event emission to
Django model signals, ensuring side effects are handled consistently elsewhere.
"""

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
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

User = get_user_model()
Status = CatalogLearnerInvitation.Status


class CatalogLearnerInvitationService:
    """
    Service for managing CatalogLearnerInvitation status transitions.

    This service handles creating, accepting, and declining invitations,
    managing status timestamps, and ensuring atomic updates to the database.
    """

    _EVENT_MAP = {
        Status.SENT: CATALOG_LEARNER_INVITATION_CREATED_V1,
        Status.ACCEPTED: CATALOG_LEARNER_INVITATION_ACCEPTED_V1,
        Status.DECLINED: CATALOG_LEARNER_INVITATION_DECLINED_V1,
        Status.REMOVED: CATALOG_LEARNER_INVITATION_REMOVED_V1,
    }

    @transaction.atomic
    def create_new_invitation(self, invite_email: str, catalog_id: int):
        """
        Create a new CatalogLearnerInvitation.
        """

        # Validate no existing accepted or sent invitations
        already_invited = self.has_active_invitations(invite_email, catalog_id)
        if already_invited:
            raise ValidationError("An active invitation already exists for this user and catalog.")

        user = self.validate_existing_user_from_email(invite_email)

        try:
            invitation = CatalogLearnerInvitation.objects.create(
                invite_email=normalize_email(invite_email),
                catalog_id=catalog_id,
                user=user,
            )
        except IntegrityError as exc:
            raise ValidationError(
                "An active invitation already exists for this user and catalog."
            ) from exc

        self._emit_invitation_event(invitation)
        return invitation

    @transaction.atomic
    def decline_invitation(self, invitation_id: int, user):
        """
        Decline an existing CatalogLearnerInvitation.
        Update status and timestamps accordingly.
        """

        invitation = CatalogLearnerInvitation.objects.get(id=invitation_id)
        can_act = self.validate_user_action(user, invitation)

        if not can_act:
            raise ValidationError("User is not authorized to decline this invitation.")

        invitation.declined_at = timezone.now()
        invitation.save()
        self._emit_invitation_event(invitation)
        return invitation

    @transaction.atomic
    def accept_invitation(self, invitation_id: int, user):
        """
        Accept an existing CatalogLearnerInvitation.
        Update status and timestamps accordingly.
        """
        invitation = CatalogLearnerInvitation.objects.get(id=invitation_id)
        can_act = self.validate_user_action(user, invitation)

        if not can_act:
            raise ValidationError("User is not authorized to accept this invitation.")

        invitation.user = user
        invitation.accepted_at = timezone.now()
        invitation.save()

        # CatalogLearner creation is handled by signal handler
        self._emit_invitation_event(invitation)
        return invitation

    @transaction.atomic
    def revoke_invitation(self, invitation_id: int, user):
        """
        Revoke an existing CatalogLearnerInvitation.
        Update status and timestamps accordingly.
        """

        invitation = CatalogLearnerInvitation.objects.get(id=invitation_id)

        if not (user.is_staff or user.is_superuser):
            raise ValidationError("Only staff users can revoke invitations.")

        if invitation.status != Status.ACCEPTED:
            raise ValidationError("Can only revoke accepted invitations.")

        invitation.revoked_at = timezone.now()
        invitation.removed_by = user
        invitation.save()

        # Triggers the learner save to update active related state
        learner = invitation.learner
        learner.refresh_from_db()
        learner.save()

        self._emit_invitation_event(invitation)
        return invitation

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

    def _emit_invitation_event(self, invitation: CatalogLearnerInvitation):
        """
        Emit the appropriate event signal based on the invitation's status.

        Uses the status computed from the timestamps updated during the save()
        operation.
        """
        status = invitation.status
        signal = self._EVENT_MAP.get(status)

        if not signal:
            return

        def after_commit() -> None:
            """Send invitation event after transaction commit."""
            event_data = self._to_event_data(invitation)
            signal.send_event(invitation=event_data)

        transaction.on_commit(after_commit)

    def validate_existing_user_from_email(self, invite_email: str):
        """
        Validate if a user with the given email exists.
        Normalize email before lookup.
        """
        normalized_email = normalize_email(invite_email)
        return User.objects.filter(email=normalized_email).first()

    def has_active_invitations(self, invite_email: str, catalog_id: int):
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

    def validate_user_action(self, user, invitation: CatalogLearnerInvitation) -> bool:
        """
        Validate if the given user can act on the invitation (accept/decline).
        """
        return getattr(user, "is_authenticated", False) and user == invitation.user
