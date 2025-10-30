"""
Event data structures for the partner_catalog app.

This module defines immutable data classes for use in event payloads,
such as those emitted for catalog course enrollment invitations.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import attr


@attr.s(frozen=True, slots=True)
class CatalogLearnerInvitationData:
    """
    Dataclass for catalog learner invitation events.

    This class encapsulates the data related to a CatalogLearnerInvitation,
    ensuring immutability when sent as part of event payloads.
    """
    id: int = attr.ib()
    catalog_id: int = attr.ib()
    status: str = attr.ib()
    invited_at: datetime = attr.ib()
    invite_email: Optional[str] = attr.ib(default=None)
    user_id: Optional[int] = attr.ib(default=None)
    learner_id: Optional[int] = attr.ib(default=None)
    invited_by_id: Optional[int] = attr.ib(default=None)
    accepted_at: Optional[datetime] = attr.ib(default=None)
    declined_at: Optional[datetime] = attr.ib(default=None)
    removed_at: Optional[datetime] = attr.ib(default=None)
    removed_by_id: Optional[int] = attr.ib(default=None)
