"""
Django signal consumers for partner catalog events.

These handlers can be used to trigger side effects such as sending notifications
when relevant events occur.
"""

import logging
from typing import Any

from django.dispatch import receiver

from partner_catalog.events.data import CatalogLearnerInvitationData
from partner_catalog.events.signals import (
    CATALOG_LEARNER_INVITATION_ACCEPTED_V1,
    CATALOG_LEARNER_INVITATION_CREATED_V1,
    CATALOG_LEARNER_INVITATION_DECLINED_V1,
    CATALOG_LEARNER_INVITATION_REMOVED_V1,
)
from partner_catalog.models import CatalogLearner

logger = logging.getLogger("partner_catalog.events")


@receiver(CATALOG_LEARNER_INVITATION_CREATED_V1)
def handle_catalog_learner_invitation_created(
    sender: Any,  # pylint: disable=unused-argument
    invitation: CatalogLearnerInvitationData,
    **_kwargs: Any
) -> None:
    """Handle creation of a CatalogLearnerInvitation."""
    # TODO: Add the needed logic when an invitation is created, like send notification email.
    # TODO: Catch errors, retry or set the invitation status to FAILED
    logger.info(
        "CATALOG_LEARNER_INVITATION_CREATED: id=%s catalog_id=%s status=%s",
        invitation.id,
        invitation.catalog_id,
        invitation.status,
    )


@receiver(CATALOG_LEARNER_INVITATION_ACCEPTED_V1)
def handle_catalog_learner_invitation_accepted(
    sender: Any,  # pylint: disable=unused-argument
    invitation: CatalogLearnerInvitationData,
    **_kwargs: Any
) -> None:
    """Handle acceptance of a CatalogLearnerInvitation."""
    learner, created = CatalogLearner.objects.get_or_create(
        user_id=invitation.user_id,
        catalog_id=invitation.catalog_id,
        defaults={'current_invitation_id': invitation.id}
    )

    # If learner existed but has different invitation, update it
    if not created and learner.current_invitation_id != invitation.id:
        learner.current_invitation_id = invitation.id
        learner.save()

    logger.info(
        "CATALOG_LEARNER_INVITATION_ACCEPTED: Learner %s for invitation id=%s catalog_id=%s user_id=%s",
        "created" if created else "updated",
        invitation.id,
        invitation.catalog_id,
        invitation.user_id,
    )


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
    # TODO: Add the needed logic when an invitation is removed.
    logger.info(
        "CATALOG_LEARNER_INVITATION_REMOVED: id=%s catalog_id=%s removed_by_id=%s",
        invitation.id,
        invitation.catalog_id,
        invitation.removed_by_id,
    )
