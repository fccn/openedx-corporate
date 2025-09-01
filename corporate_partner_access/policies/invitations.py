"""
Policies and utilities for handling invitations to enroll in corporate partner catalog courses.

This module provides pure functions and data structures to reason about invitation status
transitions, including timestamp management for accepted/declined states, without side effects.
It is intended to encapsulate business logic for invitation state changes, separate from
database or signal handling.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from django.utils import timezone

from corporate_partner_access.helpers.email import normalize_email
from corporate_partner_access.models import CatalogCourseEnrollmentAllowed


@dataclass(frozen=True)
class StatusTimestampChanges:
    """Desired timestamp values for a status change."""
    accepted_at: Optional[datetime]
    declined_at: Optional[datetime]
    touch_status_changed_at: bool


def compute_status_timestamps(
    invitation: CatalogCourseEnrollmentAllowed,
    new_status: int,
) -> StatusTimestampChanges:
    """
    Pure rule: given a new status, compute the desired timestamp values.
    """
    now = timezone.now()
    old_status = invitation.status

    if new_status == CatalogCourseEnrollmentAllowed.Status.ACCEPTED:
        return StatusTimestampChanges(
            accepted_at=invitation.accepted_at or now,
            declined_at=None,
            touch_status_changed_at=(old_status != new_status),
        )

    if new_status == CatalogCourseEnrollmentAllowed.Status.DECLINED:
        return StatusTimestampChanges(
            accepted_at=None,
            declined_at=invitation.declined_at or now,
            touch_status_changed_at=(old_status != new_status),
        )

    # SENT
    return StatusTimestampChanges(
        accepted_at=None,
        declined_at=None,
        touch_status_changed_at=(old_status != new_status),
    )


def can_user_act_on_invitation(user, invitation: CatalogCourseEnrollmentAllowed) -> bool:
    """
    Authorization rule for self-accept/decline.
    - staff/superuser → allowed
    - if invitation.user is set → only that user
    - else compare invitation.invite_email with user's email (case-insensitive)
    """
    if getattr(user, "is_staff", False) or getattr(user, "is_superuser", False):
        return True

    if invitation.user_id:
        return invitation.user_id == getattr(user, "id", None)

    inv_email = normalize_email(invitation.invite_email)
    usr_email = normalize_email(getattr(user, "email", None))
    return bool(inv_email and usr_email and inv_email == usr_email)
