"""Production settings for partner_catalog app."""

import os

LOCALE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "conf", "locale")


def plugin_settings(settings):
    """
    Add the package's translation catalog to LOCALE_PATHS.

    The LMS and CMS only turn LOCALE_PATHS into a list when they derive their settings, after the
    common plugin settings run and before these. The catalog is appended, so the theme and platform
    catalogs listed before it keep priority.
    """
    locale_paths = list(settings.LOCALE_PATHS)
    if LOCALE_DIR not in [str(path) for path in locale_paths]:
        settings.LOCALE_PATHS = locale_paths + [LOCALE_DIR]
