"""
Event data structures for the corporate_partner_access app.

This module defines immutable data classes for use in event payloads,
such as those emitted for catalog course enrollment invitations.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import attr


@attr.s(frozen=True, slots=True)
class CatalogCourseEnrollmentAllowedData:
    """
    Data for: org.mondtic.catalog.course.enrollment.allowed.*.v1

    Required:
      - id, catalog_course_id, status, invited_at
    Optional:
      - invite_email, user_id, accepted_at, declined_at
    """
    id: int = attr.ib()
    catalog_course_id: int = attr.ib()
    status: str = attr.ib()          # "SENT" | "ACCEPTED" | "DECLINED"
    invited_at: datetime = attr.ib()
    invite_email: Optional[str] = attr.ib(default=None)
    user_id: Optional[int] = attr.ib(default=None)
    accepted_at: Optional[datetime] = attr.ib(default=None)
    declined_at: Optional[datetime] = attr.ib(default=None)
