"""
corporate_partner_access Django application initialization.
"""

from django.apps import AppConfig
from edx_django_utils.plugins import PluginURLs


class CorporatePartnerAccessConfig(AppConfig):
    """
    Configuration for the corporate_partner_access Django application.
    """

    name = "corporate_partner_access"

    plugin_app = {
        PluginURLs.CONFIG: {
            'lms.djangoapp': {
                PluginURLs.NAMESPACE: "corporate_partner_access",
                PluginURLs.REGEX: r"^corporate-access/",
                PluginURLs.RELATIVE_PATH: "urls",
            },
            'cms.djangoapp': {
                PluginURLs.NAMESPACE: "corporate_partner_access",
                PluginURLs.REGEX: r"^corporate-access/",
                PluginURLs.RELATIVE_PATH: "urls",
            },
        }
    }
