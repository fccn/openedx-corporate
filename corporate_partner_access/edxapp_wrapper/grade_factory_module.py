"""Grade factory wrapper module providing indirection via settings backend."""

from importlib import import_module
from django.conf import settings


def _backend():
    path = getattr(
        settings,
        "GRADE_FACTORY_MODULE_BACKEND",
        "corporate_partner_access.edxapp_wrapper.backends.grade_factory_module_v1",
    )
    return import_module(path)


def course_grade_factory_class():
    """Return the CourseGradeFactory class."""
    return _backend().course_grade_factory_class()
