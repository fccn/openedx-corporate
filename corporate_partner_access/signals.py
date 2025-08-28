"""
Signals for corporate partner access models.

This module handles cache invalidation when email regex patterns are modified,
and emits events when CatalogCourseEnrollmentAllowed records are created or updated.
"""

from __future__ import annotations

import typing as t

from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from corporate_partner_access.events.data import CatalogCourseEnrollmentAllowedData
from corporate_partner_access.events.signals import CATALOG_CEA_CREATED_V1, CATALOG_CEA_UPDATED_V1

from corporate_partner_access.helpers.regex_cache import clear_email_regex_cache
from corporate_partner_access.models import CorporatePartnerCatalogEmailRegex, CatalogCourseEnrollmentAllowed


@receiver([post_save, post_delete], sender=CorporatePartnerCatalogEmailRegex)
def _invalidate_catalog_regex_cache(sender, instance, **kwargs):  # pylint: disable=unused-argument
    """
    Invalidate compiled regex cache when a catalog regex is created/updated/deleted.
    """
    clear_email_regex_cache()


def _to_event_data(instance: CatalogCourseEnrollmentAllowed) -> CatalogCourseEnrollmentAllowedData:
    """Convert a CatalogCourseEnrollmentAllowed instance into event data."""
    return CatalogCourseEnrollmentAllowedData(
        id=instance.id,
        catalog_course_id=instance.catalog_course_id,
        status=instance.get_status_display().upper(),
        invited_at=instance.invited_at,
        invite_email=instance.invite_email,
        user_id=instance.user_id,
        accepted_at=instance.accepted_at,
        declined_at=instance.declined_at,
    )


@receiver(post_save, sender=CatalogCourseEnrollmentAllowed)
def emit_catalog_cea_events(_sender: t.Any, instance: CatalogCourseEnrollmentAllowed, created: bool, **_kwargs):
    """Emit events after a CatalogCourseEnrollmentAllowed is created or updated."""

    def after_commit():
        data = _to_event_data(instance)
        if created:
            CATALOG_CEA_CREATED_V1.send_event(invite=data)
        else:
            CATALOG_CEA_UPDATED_V1.send_event(invite=data)

    transaction.on_commit(after_commit)
