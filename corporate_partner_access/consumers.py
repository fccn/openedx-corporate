"""
Django signal consumers for corporate partner access events.

This module defines signal handlers for events related to CatalogCourseEnrollmentAllowed
creation and updates. These handlers can be used to trigger side effects such as sending
notifications or creating enrollments when relevant events occur.
"""

import logging
from typing import Any

from django.db import transaction
from django.dispatch import receiver

from corporate_partner_access.events.data import CatalogCourseEnrollmentAllowedData
from corporate_partner_access.events.signals import (
    CATALOG_CEA_ACCEPTED_V1,
    CATALOG_CEA_CREATED_V1,
    CATALOG_CEA_DECLINED_V1,
    CATALOG_CEA_UPDATED_V1,
)
from corporate_partner_access.services.workflows import accept_invite_workflow

logger = logging.getLogger("cpa.events")


@receiver(CATALOG_CEA_CREATED_V1)
def handle_catalog_cea_created(
    sender: Any,  # pylint: disable=unused-argument
    invite: CatalogCourseEnrollmentAllowedData, **_kwargs: Any
) -> None:
    """Handle creation of a CatalogCourseEnrollmentAllowed."""
    # TODO: Send email notification
    logger.warning("CEA CREATED fired: id=%s status=%s", invite.id, invite.status)


@receiver(CATALOG_CEA_UPDATED_V1)
def handle_catalog_cea_updated(
    sender: Any,  # pylint: disable=unused-argument
    invite: CatalogCourseEnrollmentAllowedData, **_kwargs: Any
) -> None:
    """Handle updates to a CatalogCourseEnrollmentAllowed."""
    # TODO: Create catalog course enrollment
    logger.warning("CEA UPDATED fired: id=%s status=%s", invite.id, invite.status)


@receiver(CATALOG_CEA_ACCEPTED_V1)
def handle_catalog_cea_accepted(
    sender: Any,  # pylint: disable=unused-argument
    invite: CatalogCourseEnrollmentAllowedData, **_kwargs: Any
) -> None:
    """When an invite is accepted, create/activate the enrollment (idempotent)."""
    def run_workflow() -> None:
        """
        Handle side effects when a catalog course enrollment invite is accepted.

        This function is called after a CatalogCourseEnrollmentAllowed invitation is accepted.
        It triggers the workflow to ensure the user is enrolled in the corresponding catalog course,
        creating the enrollment if it does not already exist. This operation is idempotent.
        """
        accept_invite_workflow(
            user_id=invite.user_id,
            catalog_course_id=invite.catalog_course_id,
        )

    transaction.on_commit(run_workflow)


@receiver(CATALOG_CEA_DECLINED_V1)
def handle_catalog_cea_declined(
    sender: Any,  # pylint: disable=unused-argument
    invite: CatalogCourseEnrollmentAllowedData, **_kwargs: Any
) -> None:
    """When an invite is declined, run any side effect you want (logging for now)."""
    def after_commit() -> None:
        """
        Handle side effects when a catalog course enrollment invite is declined.

        This function is called after a CatalogCourseEnrollmentAllowed invitation is declined.
        You can implement any necessary side effects here, such as logging, notifying staff,
        or freeing up a quota slot.
        """
        # TODO: implement decline-specific side effects if/when needed.
        logger.info("CEA DECLINED: id=%s email=%s user_id=%s", invite.id, invite.invite_email, invite.user_id)

    transaction.on_commit(after_commit)
