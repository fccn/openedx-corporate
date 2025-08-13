"""Common settings for corporate_partner_access app."""


def plugin_settings(settings):
    """
    Add settings for the corporate_partner_access app.
    """

    settings.INSTALLED_APPS += ["flex_catalog"]
    settings.COURSE_OVERVIEW_BACKEND = (
        "corporate_partner_access.edxapp_wrapper.backends.course_module_v1"
    )
