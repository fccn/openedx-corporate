"""Common settings for partner_catalog app."""


def plugin_settings(settings):
    """
    Add settings for the partner_catalog app.
    """

    settings.INSTALLED_APPS += ["flex_catalog"]

    if "drf_spectacular" not in settings.INSTALLED_APPS:
        settings.INSTALLED_APPS += ["drf_spectacular"]

    settings.REST_FRAMEWORK["DEFAULT_SCHEMA_CLASS"] = "drf_spectacular.openapi.AutoSchema"
    settings.SPECTACULAR_SETTINGS = {
        "TITLE": "Partner Catalog API",
        "DESCRIPTION": "API documentation for Partner Catalog endpoints.",
        "VERSION": "1.0.0",
        "PREPROCESSING_HOOKS": [
            "partner_catalog.helpers.spectacular.spectacular_filter_hook",
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
        "partner_catalog.edxapp_wrapper.backends.course_module_v1"
    )

    settings.SEARCH_ENGINE = (
        "partner_catalog.search_engine.FlexibleCatalogCompatibleSearchEngine"
    )
