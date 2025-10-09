"""Assessment-related services: completed/pending counts per enrollment."""

from typing import Optional

from opaque_keys.edx.keys import CourseKey  # type: ignore

from partner_catalog.edxapp_wrapper.grade_factory_module import course_grade_factory_class

CourseGradeFactory = course_grade_factory_class()


def get_assessments_counts(course_key_str: str, user) -> Optional[dict]:
    """Counts completed and pending graded assessments for the user in course.

    Returns a dict with 'completed' and 'pending' keys, or None if no data.
    Definitions simplified:
        - pending  = graded subsections (possible > 0) without learner attempt
        - completed = graded subsections where there was an attempt
    """

    course_key = CourseKey.from_string(course_key_str)
    course_grade = CourseGradeFactory().read(user, course_key=course_key)

    completed = 0
    pending = 0

    for subsection_grade in course_grade.subsection_grades.values():

        if not grade_subsection_has_grade(subsection_grade):
            continue

        if subsection_attempted(subsection_grade):
            completed += 1
        else:
            pending += 1

    return {
        "completed": completed,
        "pending": pending,
    }


def grade_subsection_has_grade(subsection_grade) -> bool:
    """Return True if the subsection_grade has a grade (possible > 0).

    Checks if the subsection_grade has a graded_total with possible > 0.
    """

    if not subsection_grade:
        return False

    try:
        graded_total = getattr(subsection_grade, "graded_total", None)

        if not graded_total:
            return False

        possible = getattr(graded_total, "possible", None)

        if not possible or possible <= 0:
            return False

    except Exception:  # pylint: disable=broad-except
        return False

    return True


def subsection_attempted(subsection_grade) -> bool:
    """Return True if learner has attempted the graded subsection.

    Attempt definition:
      - Any problem_score within problem_scores has a non-None 'earned'.
      - Fallback: graded_total.earned is not None.
    """
    try:
        problem_scores = getattr(subsection_grade, "problem_scores", None)

        if problem_scores:
            for ps in problem_scores:
                if getattr(ps, "earned", None) is not None:
                    return True

        graded_total = getattr(subsection_grade, "graded_total", None)

        if graded_total and getattr(graded_total, "earned", None) is not None:
            return True

    except Exception:  # pylint: disable=broad-except
        return False
    return False
