"""
Django signal consumers for partner catalog events.

These handlers can be used to trigger side effects such as sending notifications
when relevant events occur.
"""

import logging
from typing import Any

from django.db import DatabaseError
from django.dispatch import receiver
from rest_framework.exceptions import ValidationError

from partner_catalog.events.data import CatalogLearnerInvitationData
from partner_catalog.events.signals import (
    CATALOG_LEARNER_INVITATION_ACCEPTED_V1,
    CATALOG_LEARNER_INVITATION_CREATED_V1,
    CATALOG_LEARNER_INVITATION_DECLINED_V1,
    CATALOG_LEARNER_INVITATION_REMOVED_V1,
)
from partner_catalog.services.catalogs import PartnerCatalogService
from partner_catalog.services.enrollments import CatalogCourseEnrollmentService
from partner_catalog.tasks.emails import send_catalog_invitation_created_email

logger = logging.getLogger("partner_catalog.events")


@receiver(CATALOG_LEARNER_INVITATION_CREATED_V1)
def handle_catalog_learner_invitation_created(
    sender: Any,  # pylint: disable=unused-argument
    invitation: CatalogLearnerInvitationData,
    **_kwargs: Any
) -> None:
    """Handle creation of a CatalogLearnerInvitation."""
    # Enqueue email sending to Celery worker (do not send inline).
    try:
        logger.info(
            "Enqueueing invitation created email: id=%s catalog_id=%s",
            invitation.id,
            invitation.catalog_id,
        )
        send_catalog_invitation_created_email.delay(invitation.id)
    except Exception:  # pragma: no cover - defensive logging
        logger.exception(
            "Failed to enqueue invitation created email for id=%s",
            getattr(invitation, "id", None),
        )


@receiver(CATALOG_LEARNER_INVITATION_ACCEPTED_V1)
def handle_catalog_learner_invitation_accepted(
    sender: Any,  # pylint: disable=unused-argument
    invitation: CatalogLearnerInvitationData,
    **_kwargs: Any
) -> None:
    """Handle acceptance of a CatalogLearnerInvitation."""
    try:

        catalog_service = PartnerCatalogService()
        _, created = catalog_service.create_or_update_learner_from_invitation(invitation.id)

        logger.info(
            "CATALOG_LEARNER_INVITATION_ACCEPTED: Learner %s for invitation id=%s catalog_id=%s user_id=%s",
            "created" if created else "updated",
            invitation.id,
            invitation.catalog_id,
            invitation.user_id,
        )
    except DatabaseError as exc:
        logger.error(
            "Database error processing invitation %s: %s",
            invitation.id,
            exc,
            exc_info=True
        )
        raise ValidationError("Error processing invitation acceptance.") from exc


@receiver(CATALOG_LEARNER_INVITATION_DECLINED_V1)
def handle_catalog_learner_invitation_declined(
    sender: Any,  # pylint: disable=unused-argument
    invitation: CatalogLearnerInvitationData,
    **_kwargs: Any
) -> None:
    """Handle declination of a CatalogLearnerInvitation."""
    # TODO: add the needed logic when an invitation is declined.
    logger.info(
        "CATALOG_LEARNER_INVITATION_DECLINED: id=%s catalog_id=%s user_id=%s",
        invitation.id,
        invitation.catalog_id,
        invitation.user_id,
    )


@receiver(CATALOG_LEARNER_INVITATION_REMOVED_V1)
def handle_catalog_learner_invitation_removed(
    sender: Any,  # pylint: disable=unused-argument
    invitation: CatalogLearnerInvitationData,
    **_kwargs: Any
) -> None:
    """Handle removal/revocation of a CatalogLearnerInvitation."""
    try:
        catalog_service = PartnerCatalogService()
        enrollments_service = CatalogCourseEnrollmentService()

        learner = catalog_service.deactivate_learner_from_invitation(invitation.id)
        enrollments_service.deactivate_enrollments_by_catalog(
            user_id=learner.user_id,
            catalog_id=invitation.catalog_id,
        )
        logger.info(
            "CATALOG_LEARNER_INVITATION_REMOVED: Learner %s deactivated catalog_id=%s removed_by_id=%s",
            learner.id,
            invitation.catalog_id,
            invitation.removed_by_id,
        )
    except DatabaseError as exc:
        logger.error(
            "Database error processing invitation removal %s: %s",
            invitation.id,
            exc,
            exc_info=True
        )
        raise ValidationError("Error processing invitation removal.") from exc
