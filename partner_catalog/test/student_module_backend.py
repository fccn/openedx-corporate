"""Test backend for student module operations."""

from dataclasses import dataclass
from typing import Any, List, Optional


class _EmptyQuery:
    """Tiny helper to mimic queryset chaining used in tests (filter().values_list().first())."""

    def filter(self, **kwargs):
        """Return self to allow for queryset chaining."""
        return self

    def values_list(self, field: str, flat: bool = False):  # pylint: disable=unused-argument
        """Return self to allow for queryset chaining."""
        return self

    def first(self):
        return None


class _ObjectsManager:
    """Very small stand-in for a Django manager used by tests that don't hit the DB."""

    def get(self, **kwargs):
        raise CourseEnrollmentTestModel.DoesNotExist()


@dataclass
class CourseEnrollmentTestModel:
    """Minimal mock of CourseEnrollment for tests."""

    user_id: Optional[int] = None
    course_id: Optional[str] = None

    attributes: Any = _EmptyQuery()
    objects: Any = _ObjectsManager()

    class DoesNotExist(Exception):
        """Raised when an enrollment isn't found (mirrors Django model exception)."""


class CourseModeTestModel:
    """Minimal mock of CourseMode for tests."""

    DEFAULT_MODE_SLUG = "audit"

    @classmethod
    def modes_for_course(cls, course_key):  # pylint: disable=unused-argument
        """Return a list of available modes for the course in tests."""

        class _Mode:
            def __init__(self, slug: str):
                self.slug = slug

        # Provide at least one mode to choose from in tests
        return [_Mode("audit")]


def course_enrollment_model():
    """Return the test CourseEnrollment class."""
    return CourseEnrollmentTestModel


def course_mode_model():
    """Return the test CourseMode class."""
    return CourseModeTestModel


def enroll_user(
    *,
    user,
    course_key,
    mode: Optional[str] = None,
    check_access: bool = False  # pylint: disable=unused-argument
):
    """Idempotent-ish test enroll: return a mock enrollment object.

    The real implementation returns a CourseEnrollment instance; for tests we can return
    a CourseEnrollmentTestModel with fields set.
    """
    # Mode selection exists in the real impl; here we keep behavior minimal.
    _ = mode or CourseModeTestModel.DEFAULT_MODE_SLUG  # keep for parity, avoid unused var
    # Pack the selected data in a simple structure akin to a model instance
    return CourseEnrollmentTestModel(user_id=getattr(user, "id", None), course_id=str(course_key))


def available_modes(course_key) -> List[str]:  # pylint: disable=unused-argument
    """Return a list of available modes for the course in tests."""
    return ["audit"]
