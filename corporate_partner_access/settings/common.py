"""Common settings for corporate_partner_access app."""


def plugin_settings(settings):
    """
    Add settings for the corporate_partner_access app.
    """

    settings.INSTALLED_APPS += ["flex_catalog"]

    if "drf_spectacular" not in settings.INSTALLED_APPS:
        settings.INSTALLED_APPS += ["drf_spectacular"]

    settings.REST_FRAMEWORK["DEFAULT_SCHEMA_CLASS"] = "drf_spectacular.openapi.AutoSchema"
    settings.SPECTACULAR_SETTINGS = {
        "TITLE": "Corporate Partner Access API",
        "DESCRIPTION": "API documentation for Corporate Partner Access endpoints.",
        "VERSION": "1.0.0",
        "PREPROCESSING_HOOKS": [
            "corporate_partner_access.utils.spectacular_filter_hook",
        ],
    }

    settings.REST_FRAMEWORK.update(
        {
            "DEFAULT_FILTER_BACKENDS": [
                "django_filters.rest_framework.DjangoFilterBackend",
                "rest_framework.filters.SearchFilter",
                "rest_framework.filters.OrderingFilter",
            ],
        }
    )

    settings.COURSE_OVERVIEW_BACKEND = (
        "corporate_partner_access.edxapp_wrapper.backends.course_module_v1"
    )

    settings.SEARCH_ENGINE = (
        "corporate_partner_access.search_engine.FlexibleCatalogCompatibleSearchEngine"
    )
