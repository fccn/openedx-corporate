"""
Django signal consumers for corporate partner access events.

This module defines signal handlers for events related to CatalogCourseEnrollmentAllowed
creation and updates. These handlers can be used to trigger side effects such as sending
notifications or creating enrollments when relevant events occur.
"""

import logging
from typing import Any

from django.dispatch import receiver

from corporate_partner_access.events.data import CatalogCourseEnrollmentAllowedData
from corporate_partner_access.events.signals import CATALOG_CEA_CREATED_V1, CATALOG_CEA_UPDATED_V1

logger = logging.getLogger("cpa.events")


@receiver(CATALOG_CEA_CREATED_V1)
def handle_catalog_cea_created(
    _sender: Any, invite: CatalogCourseEnrollmentAllowedData, **_kwargs: Any
) -> None:
    """Handle creation of a CatalogCourseEnrollmentAllowed."""
    # ToDo: Send email notification
    logger.warning("CEA CREATED fired: id=%s status=%s", invite.id, invite.status)


@receiver(CATALOG_CEA_UPDATED_V1)
def handle_catalog_cea_updated(
    _sender: Any, invite: CatalogCourseEnrollmentAllowedData, **_kwargs: Any
) -> None:
    """Handle updates to a CatalogCourseEnrollmentAllowed."""
    # ToDo: Create catalog course enrollment
    logger.warning("CEA UPDATED fired: id=%s status=%s", invite.id, invite.status)
