"""
Service layer for handling invitation status transitions and persistence.

This module provides the InvitationService class, which encapsulates business logic
for updating the status of CatalogCourseEnrollmentAllowed invitations, including
timestamp management and atomic database updates. It delegates event emission to
Django model signals, ensuring side effects are handled consistently elsewhere.
"""

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from partner_catalog.helpers.email import normalize_email
from partner_catalog.models import CatalogLearnerInvitation

User = get_user_model()


class CatalogLearnerInvitationService:
    """
    Service for managing CatalogLearnerInvitation status transitions.

    This service handles creating, accepting, and declining invitations,
    managing status timestamps, and ensuring atomic updates to the database.
    """

    @transaction.atomic
    def create_new_invitation(self, invite_email: str, catalog_id: int):
        """
        Create a new CatalogLearnerInvitation.
        """

        already_invited = self.validate_existing_invitations(invite_email, catalog_id)
        if already_invited:
            raise ValidationError("An active invitation already exists for this user and catalog.")

        user = self.validate_existing_user_from_email(invite_email)
        return CatalogLearnerInvitation.objects.create(
            invite_email=normalize_email(invite_email),
            catalog_id=catalog_id,
            user=user,
        )

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
        return invitation.save()

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
        return invitation.save()

    @transaction.atomic
    def revoke_invitation(self, invitation_id: int, user):
        """
        Revoke an existing CatalogLearnerInvitation.
        Update status and timestamps accordingly.
        """

        invitation = CatalogLearnerInvitation.objects.get(id=invitation_id)

        if not user.is_staff or not user.is_superuser:
            raise ValidationError("Only staff users can revoke invitations.")

        invitation.revoked_at = timezone.now()
        return invitation.save()

    def validate_existing_user_from_email(self, invite_email: str):
        """
        Validate if a user with the given email exists.
        Normalize email before lookup.
        """
        normalized_email = normalize_email(invite_email)
        return User.objects.filter(email=normalized_email).first()

    def validate_existing_invitations(self, invite_email: str, catalog_id: int):
        """
        Validate if an invitation already exists for the given user and catalog.
        Normalize email before lookup.
        """
        normalized_email = normalize_email(invite_email)
        return CatalogLearnerInvitation.objects.filter(
            email=normalized_email,
            catalog_id=catalog_id,
            status=CatalogLearnerInvitation.Status.INVITED,
        ).exists()

    def validate_user_action(self, user, invitation: CatalogLearnerInvitation) -> bool:
        """
        Validate if the given user can act on the invitation (accept/decline).
        """
        return getattr(user, "is_authenticated", False) and user == invitation.user
