"""Course module definitions."""


from importlib import import_module

from django.conf import settings


def course_overview():
    """Get get_course_overview method."""

    backend_function = settings.COURSE_OVERVIEW_BACKEND
    backend = import_module(backend_function)

    return backend.course_overview_model()


def course_overview_base_serializer():
    """Get course_overview_base_serializer method."""

    backend_function = settings.COURSE_OVERVIEW_BACKEND
    backend = import_module(backend_function)

    return backend.course_overview_base_serializer()
