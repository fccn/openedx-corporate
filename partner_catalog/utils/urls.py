"""Utility helpers for partner_catalog URLs."""

from django.conf import settings


def build_catalog_url(partner_slug: str, catalog_slug: str) -> str:
    """Build a URL to the corporate catalogs MFE for given partner and catalog slugs.

    Result: {BASE_URL}/learning-paths/<partner_slug>/catalog/<catalog_slug>

    BASE_URL comes from ``settings.CORPORATE_CATALOGS_MFE_BASE_URL``, which should
    be the root of the MFE host WITHOUT the /learning-paths prefix
    (e.g. ``https://apps.example.com``), because this function appends
    /learning-paths/ itself. A base that already ends with /learning-paths is
    normalized so the segment is never duplicated.

    Falls back to ``settings.LMS_ROOT_URL`` when the setting is absent. If both
    settings are unset the result is a host-less relative path, which would make a
    broken link in an email; callers that embed the URL should check for that (see
    ``partner_catalog.services.emails``).
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
