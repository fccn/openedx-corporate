"""Common settings for corporate_partner_access app."""


def plugin_settings(settings):
    """
    Add settings for the corporate_partner_access app.
    """

    settings.INSTALLED_APPS += ["flex_catalog"]

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
