"""
Signals for corporate partner access models.

This module handles cache invalidation when email regex patterns are modified.
"""

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from corporate_partner_access.helpers.regex_cache import clear_email_regex_cache
from corporate_partner_access.models import CorporatePartnerCatalogEmailRegex


@receiver([post_save, post_delete], sender=CorporatePartnerCatalogEmailRegex)
def _invalidate_catalog_regex_cache(sender, instance, **kwargs):  # pylint: disable=unused-argument
    """
    Invalidate compiled regex cache when a catalog regex is created/updated/deleted.
    """
    clear_email_regex_cache()
