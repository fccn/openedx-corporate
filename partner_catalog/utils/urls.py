"""Utility helpers for partner_catalog URLs."""

from django.conf import settings


def build_catalog_url(partner_slug: str, catalog_slug: str) -> str:
    """Build a URL to the corporate catalogs MFE for given partner and catalog slugs.

    Result: {BASE_URL}/learning-paths/<partner_slug>/catalog/<catalog_slug>

    BASE_URL comes from ``settings.CORPORATE_CATALOGS_MFE_BASE_URL``.
    This setting must be the root of the MFE host WITHOUT the /learning-paths prefix
    (e.g. ``https://apps.example.com``), because this function always appends
    /learning-paths/ itself. If the setting already includes /learning-paths,
    the generated URL will have a duplicate segment.

    Falls back to ``settings.LMS_ROOT_URL`` when the setting is absent.
    """
    base = getattr(settings, "CORPORATE_CATALOGS_MFE_BASE_URL", "") or ""
    if not base:
        base = getattr(settings, "LMS_ROOT_URL", "").rstrip("/")
    base = base.rstrip("/")
    # Normalize: if the base already ends with /learning-paths, strip it so we
    # always append it exactly once below.
    if base.endswith("/learning-paths"):
        base = base[: -len("/learning-paths")]
    return f"{base}/learning-paths/{partner_slug}/catalog/{catalog_slug}"
