"""Courseware module definitions (wrapper around edx-platform)."""

from importlib import import_module

from django.conf import settings


def _backend():
    """Return the backend module for courseware operations."""
    path = getattr(
        settings,
        "COURSEWARE_MODULE_BACKEND",
        "partner_catalog.edxapp_wrapper.backends.courseware_module_v1",
    )
    return import_module(path)


def get_course_blocks_completion_summary(course_key, user):
    """Return completion summary for a user in a course (backend proxy)."""
    return _backend().get_course_blocks_completion_summary(course_key, user)
