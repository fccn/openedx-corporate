"""
partner_catalog Django application initialization.
"""

import importlib

from django.apps import AppConfig
from edx_django_utils.plugins import PluginSettings, PluginURLs


class PartnerCatalogConfig(AppConfig):
    """
    Configuration for the partner_catalog Django application.
    """

    name = "partner_catalog"

    plugin_app = {
        PluginURLs.CONFIG: {
            'lms.djangoapp': {
                PluginURLs.NAMESPACE: "partner_catalog",
                PluginURLs.REGEX: r"^partner_catalog/",
                PluginURLs.RELATIVE_PATH: "urls",
            },
            'cms.djangoapp': {
                PluginURLs.NAMESPACE: "partner_catalog",
                PluginURLs.REGEX: r"^partner_catalog/",
                PluginURLs.RELATIVE_PATH: "urls",
            },
        },
        PluginSettings.CONFIG: {
            'lms.djangoapp': {
                'common': {PluginSettings.RELATIVE_PATH: 'settings.common'}
            },
            'cms.djangoapp': {
                'common': {PluginSettings.RELATIVE_PATH: 'settings.common'}
            },
        },
    }

    def ready(self):
        """Initialize the application by importing signals module."""
        importlib.import_module("partner_catalog.signals")
        importlib.import_module("partner_catalog.consumers")
        importlib.import_module("partner_catalog.tasks.emails")
