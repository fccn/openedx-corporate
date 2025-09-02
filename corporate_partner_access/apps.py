"""
corporate_partner_access Django application initialization.
"""

import importlib

from django.apps import AppConfig
from edx_django_utils.plugins import PluginSettings, PluginURLs


class CorporatePartnerAccessConfig(AppConfig):
    """
    Configuration for the corporate_partner_access Django application.
    """

    name = "corporate_partner_access"

    plugin_app = {
        PluginURLs.CONFIG: {
            'lms.djangoapp': {
                PluginURLs.NAMESPACE: "corporate_partner_access",
                PluginURLs.REGEX: r"^corporate_access/",
                PluginURLs.RELATIVE_PATH: "urls",
            },
            'cms.djangoapp': {
                PluginURLs.NAMESPACE: "corporate_partner_access",
                PluginURLs.REGEX: r"^corporate_access/",
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
        importlib.import_module("corporate_partner_access.signals")
        importlib.import_module("corporate_partner_access.consumers")
