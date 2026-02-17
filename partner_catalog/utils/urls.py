"""Utility helpers for partner_catalog URLs."""

from django.conf import settings


def build_catalog_url(partner_slug: str, catalog_slug: str) -> str:
    """Build a URL to the corporate catalogs MFE for given partner and catalog slugs.

    Result: {BASE_URL}/corporate-catalogs/catalog/<partner_slug>/<catalog_slug>
    BASE_URL comes from `settings.CORPORATE_CATALOGS_MFE_BASE_URL`.
    If not configured, returns a relative path.
    """
    base = getattr(settings, "CORPORATE_CATALOGS_MFE_BASE_URL", "") or ""
    base = base.rstrip("/")
    if not base:
        return f"/corporate-catalogs/catalog/{partner_slug}/{catalog_slug}"
    return f"{base}/corporate-catalogs/catalog/{partner_slug}/{catalog_slug}"
