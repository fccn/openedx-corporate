"""Backend abstraction for grade factory (course grades) from edx-platform."""

# pylint: disable=import-error
from lms.djangoapps.grades.course_grade_factory import CourseGradeFactory


def course_grade_factory_class():
    """Return CourseGradeFactory class."""
    return CourseGradeFactory
