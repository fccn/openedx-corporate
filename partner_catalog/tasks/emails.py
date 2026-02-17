"""Celery tasks for partner_catalog emails."""

import logging
from typing import Any

from celery import shared_task

from partner_catalog.services.emails import InvitationEmailService

logger = logging.getLogger("partner_catalog.tasks.emails")


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 3})
def send_catalog_invitation_created_email(self: Any, invitation_id: int) -> None:
    """Task: send email notification when an invitation is created.

    The heavy lifting is delegated to InvitationEmailService to keep logic testable.
    """
    try:
        InvitationEmailService().send_invitation_created(invitation_id)
    except Exception as exc:  # pragma: no cover - task retry behavior
        logger.exception("Error sending invitation created email for id=%s", invitation_id)
        raise
