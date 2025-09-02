"""
Service layer for handling invitation status transitions and persistence.

This module provides the InvitationService class, which encapsulates business logic
for updating the status of CatalogCourseEnrollmentAllowed invitations, including
timestamp management and atomic database updates. It delegates event emission to
Django model signals, ensuring side effects are handled consistently elsewhere.
"""

from __future__ import annotations

from typing import Iterable, Optional

from django.contrib.auth import get_user_model
from django.db import transaction

from corporate_partner_access.helpers.email import normalize_email
from corporate_partner_access.models import CatalogCourseEnrollmentAllowed
from corporate_partner_access.policies.invitations import compute_status_timestamps


class InvitationService:
    """
    Use-cases for CatalogCourseEnrollmentAllowed.
    App-level signals emit events after save; do NOT publish here.
    """

    @staticmethod
    @transaction.atomic
    def apply_status(
        invitation: CatalogCourseEnrollmentAllowed,
        new_status: int,
        *,
        update_fields: Optional[Iterable[str]] = None,
    ) -> CatalogCourseEnrollmentAllowed:
        """
        Apply a new status and persist required timestamp changes atomically.
        """
        changes = compute_status_timestamps(invitation, new_status)

        touched = set(update_fields or [])
        old_status = invitation.status

        invitation.user = get_user_model().objects.get(email=invitation.invite_email)
        touched.add("user")

        # Update status (and ensure status_changed_at is persisted on transitions)
        if old_status != new_status:
            invitation.status = new_status
            touched.add("status")
            touched.add("status_changed_at")

        # Sync timestamps as per policy
        if invitation.accepted_at != changes.accepted_at:
            invitation.accepted_at = changes.accepted_at
            touched.add("accepted_at")

        if invitation.declined_at != changes.declined_at:
            invitation.declined_at = changes.declined_at
            touched.add("declined_at")

        invitation.save(update_fields=list(touched) if touched else None)
        return invitation

    @staticmethod
    @transaction.atomic
    def apply_status_as_user(
        invitation: CatalogCourseEnrollmentAllowed,
        acting_user,
        new_status: int,
    ) -> CatalogCourseEnrollmentAllowed:
        """
        Like apply_status, but (idempotently) binds the acting user to the invitation
        when: invitation.user is null AND invite_email matches acting_user.email (ci),
        and there's no conflicting invite for the same (catalog_course, user).
        """
        touched: set[str] = set()

        can_bind_user = (
            getattr(acting_user, "is_authenticated", False)
            and invitation.user_id is None
            and normalize_email(invitation.invite_email)
            and normalize_email(getattr(acting_user, "email", None))
            and normalize_email(invitation.invite_email) == normalize_email(getattr(acting_user, "email", None))
        )

        if can_bind_user:
            # Avoid violating the unique (catalog_course, user) constraint (when user is not null)
            exists_conflict = CatalogCourseEnrollmentAllowed.objects.filter(
                catalog_course_id=invitation.catalog_course_id,
                user_id=getattr(acting_user, "id", None),
            ).exclude(pk=invitation.pk).exists()

            if not exists_conflict:
                invitation.user = acting_user
                touched.add("user")

        return InvitationService.apply_status(invitation, new_status, update_fields=touched)

    @staticmethod
    def accept(invitation: CatalogCourseEnrollmentAllowed) -> CatalogCourseEnrollmentAllowed:
        return InvitationService.apply_status(invitation, CatalogCourseEnrollmentAllowed.Status.ACCEPTED)

    @staticmethod
    def decline(invitation: CatalogCourseEnrollmentAllowed) -> CatalogCourseEnrollmentAllowed:
        return InvitationService.apply_status(invitation, CatalogCourseEnrollmentAllowed.Status.DECLINED)

    @staticmethod
    def mark_sent(invitation: CatalogCourseEnrollmentAllowed) -> CatalogCourseEnrollmentAllowed:
        return InvitationService.apply_status(invitation, CatalogCourseEnrollmentAllowed.Status.SENT)
