"""
Tests for the settings that make the app's translation catalog reachable in the LMS and CMS.
"""

import os
from types import SimpleNamespace

import pytest
from django.conf import settings as django_settings
from edx_django_utils.plugins import PluginSettings

from partner_catalog.apps import PartnerCatalogConfig
from partner_catalog.settings.production import LOCALE_DIR, plugin_settings

THEME_LOCALE_DIR = "/openedx/themes/nau-basic/conf/locale"


def test_locale_dir_is_the_package_catalog():
    """LOCALE_DIR points at the directory that holds the shipped pt_PT catalog."""
    assert LOCALE_DIR.endswith(os.path.join("partner_catalog", "conf", "locale"))
    assert os.path.isfile(os.path.join(LOCALE_DIR, "pt_PT", "LC_MESSAGES", "django.mo"))


def test_test_settings_get_the_catalog_from_the_app():
    """The test settings rely on the app's own settings for the catalog path."""
    assert list(django_settings.LOCALE_PATHS) == [LOCALE_DIR]


def test_catalog_is_added_after_the_theme():
    """The theme stays first, so its translations keep priority over the package's."""
    settings = SimpleNamespace(LOCALE_PATHS=[THEME_LOCALE_DIR])

    plugin_settings(settings)

    assert settings.LOCALE_PATHS == [THEME_LOCALE_DIR, LOCALE_DIR]


def test_applying_twice_does_not_duplicate_the_catalog():
    """Running the plugin settings again leaves a single entry for the catalog."""
    settings = SimpleNamespace(LOCALE_PATHS=[THEME_LOCALE_DIR])

    plugin_settings(settings)
    plugin_settings(settings)

    assert settings.LOCALE_PATHS.count(LOCALE_DIR) == 1


def test_catalog_is_added_to_a_tuple():
    """A LOCALE_PATHS tuple is accepted and becomes a list with the catalog last."""
    settings = SimpleNamespace(LOCALE_PATHS=(THEME_LOCALE_DIR,))

    plugin_settings(settings)

    assert settings.LOCALE_PATHS == [THEME_LOCALE_DIR, LOCALE_DIR]


@pytest.mark.parametrize("project_type", ["lms.djangoapp", "cms.djangoapp"])
def test_production_settings_are_registered(project_type):
    """The LMS and CMS run these settings after LOCALE_PATHS is derived into a list."""
    config = PartnerCatalogConfig.plugin_app[PluginSettings.CONFIG][project_type]

    assert config["production"][PluginSettings.RELATIVE_PATH] == "settings.production"
