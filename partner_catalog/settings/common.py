"""Common settings for partner_catalog app."""

from partner_catalog.xapi.constants import ALL_EVENTS as PARTNER_CATALOG_XAPI_EVENTS

try:
    from event_routing_backends.utils.settings import event_tracking_backends_config
except ImportError:  # pragma: no cover
    event_tracking_backends_config = None


def _append_unique(target_list, values):
    """
    Append values to a list while preserving order and avoiding duplicates.
    """
    for value in values:
        if value not in target_list:
            target_list.append(value)


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

    settings.SYSTEM_WIDE_ROLE_CLASSES = [
        "partner_catalog.policies.rbac.get_catalog_role_assignments",
    ]
    # Base Catalog settings
    settings.PARTNER_CATALOG_BASE_CATALOG_SLUG = "NAU-base-catalog"
    settings.PARTNER_CATALOG_BASE_CATALOG_NAME = "NAU Base Catalog"

    # Whitelist partner catalog xAPI events for event-routing-backends.
    if not hasattr(settings, "EVENT_TRACKING_BACKENDS_ALLOWED_XAPI_EVENTS"):
        settings.EVENT_TRACKING_BACKENDS_ALLOWED_XAPI_EVENTS = []
    if not hasattr(settings, "EVENT_TRACKING_BACKENDS_ALLOWED_CALIPER_EVENTS"):
        settings.EVENT_TRACKING_BACKENDS_ALLOWED_CALIPER_EVENTS = []
    if not hasattr(settings, "EVENT_TRACKING_BACKENDS"):
        settings.EVENT_TRACKING_BACKENDS = {}

    _append_unique(
        settings.EVENT_TRACKING_BACKENDS_ALLOWED_XAPI_EVENTS,
        PARTNER_CATALOG_XAPI_EVENTS,
    )

    if event_tracking_backends_config:
        settings.EVENT_TRACKING_BACKENDS.update(
            event_tracking_backends_config(
                settings,
                settings.EVENT_TRACKING_BACKENDS_ALLOWED_XAPI_EVENTS,
                settings.EVENT_TRACKING_BACKENDS_ALLOWED_CALIPER_EVENTS,
            )
        )
