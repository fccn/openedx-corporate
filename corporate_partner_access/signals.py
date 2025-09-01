"""
Signals for corporate partner access models.

This module handles cache invalidation when email regex patterns are modified,
and emits events when CatalogCourseEnrollmentAllowed records are created or updated.
"""

from __future__ import annotations

import typing as t

from django.db import transaction
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from corporate_partner_access.events.data import CatalogCourseEnrollmentAllowedData
from corporate_partner_access.events.signals import (
    CATALOG_CEA_ACCEPTED_V1,
    CATALOG_CEA_CREATED_V1,
    CATALOG_CEA_DECLINED_V1,
    CATALOG_CEA_UPDATED_V1,
)
from corporate_partner_access.helpers.regex_cache import clear_email_regex_cache
from corporate_partner_access.models import CatalogCourseEnrollmentAllowed, CorporatePartnerCatalogEmailRegex


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


@receiver(pre_save, sender=CatalogCourseEnrollmentAllowed)
def _cea_stash_previous_status(
    sender: t.Any,  # pylint: disable=unused-argument
    instance: CatalogCourseEnrollmentAllowed, **_kwargs
) -> None:
    """Stash previous status in-memory so post_save can detect real transitions."""
    if instance.pk:
        try:
            instance._old_status = (  # pylint: disable=protected-access
                type(instance).objects.only("status").get(pk=instance.pk).status
            )  # noqa: SLF001
        except type(instance).DoesNotExist:
            instance._old_status = None  # pylint: disable=protected-access


@receiver(post_save, sender=CatalogCourseEnrollmentAllowed)
def emit_catalog_cea_events(
    sender: t.Any,  # pylint: disable=unused-argument
    instance: CatalogCourseEnrollmentAllowed,
    created: bool,
    **_kwargs,
) -> None:
    """Emit CREATED/UPDATED, and ACCEPTED/DECLINED on real transitions."""

    def after_commit() -> None:
        data = _to_event_data(instance)

        if created:
            CATALOG_CEA_CREATED_V1.send_event(invite=data)
            return

        # Always emit UPDATED for non-create saves
        CATALOG_CEA_UPDATED_V1.send_event(invite=data)

        old = getattr(instance, "_old_status", None)
        new = instance.status

        if old is None:
            return

        if old != new:
            if new == CatalogCourseEnrollmentAllowed.Status.ACCEPTED:
                CATALOG_CEA_ACCEPTED_V1.send_event(invite=data)
            elif new == CatalogCourseEnrollmentAllowed.Status.DECLINED:
                CATALOG_CEA_DECLINED_V1.send_event(invite=data)

    transaction.on_commit(after_commit)
