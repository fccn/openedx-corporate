"""
Signals for corporate partner access models.

This module handles cache invalidation when email regex patterns are modified.
"""

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from corporate_partner_access.models import CorporatePartnerCatalog, CorporatePartnerCatalogEmailRegex


def _clear_regex_cache_for_catalog(_catalog_id: int | None = None):
    """Clear the regex cache for a catalog."""
    CorporatePartnerCatalog._compiled_regexes_for_catalog.cache_clear()  # pylint: disable=protected-access


@receiver(post_save, sender=CorporatePartnerCatalogEmailRegex)
def on_regex_saved(sender, instance, **kwargs):  # pylint: disable=unused-argument
    """Clear cache when a regex pattern is saved."""
    _clear_regex_cache_for_catalog(instance.catalog_id)


@receiver(post_delete, sender=CorporatePartnerCatalogEmailRegex)
def on_regex_deleted(sender, instance, **kwargs):  # pylint: disable=unused-argument
    """Clear cache when a regex pattern is deleted."""
    _clear_regex_cache_for_catalog(instance.catalog_id)
