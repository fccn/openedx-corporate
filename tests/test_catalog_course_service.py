"""
Tests for CatalogCourseService - Catalog Course Positioning (Suite 7).

Covers:
- add_catalog_courses: adds a course at a specified position
- add_catalog_courses: shifts existing courses when inserting at an occupied position
- add_catalog_courses: appends at the end when no position is specified
- remove_catalog_courses: removes courses and reorganizes remaining positions
- update_course_position: reorders a course and adjusts sibling positions

Note: can_course_be_added_to_catalog is mocked in all add tests to isolate
the service's positioning logic from the catalog policy layer.
"""

from unittest.mock import patch

import pytest

from partner_catalog.models import CatalogCourse
from partner_catalog.services.catalog_courses import CatalogCourseService, CourseOverview
from tests.factories import make_catalog

PATCH_POLICY = "partner_catalog.services.catalog_courses.can_course_be_added_to_catalog"


def make_course():
    """Create a CourseOverviewTestModel instance."""
    return CourseOverview.objects.create()


def make_catalog_course(catalog, course, position):
    """Create a CatalogCourse at the given position."""
    return CatalogCourse.objects.create(
        catalog=catalog,
        course_overview=course,
        position=position,
    )


# ---------------------------------------------------------------------------
# add_catalog_courses — position insertion
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_add_course_at_specified_position():
    """add_catalog_courses creates a CatalogCourse at the given position."""
    catalog = make_catalog()
    course = make_course()

    with patch(PATCH_POLICY, return_value=True):
        created = CatalogCourseService.add_catalog_courses(catalog, [course.id], position=0)

    assert len(created) == 1
    assert created[0].position == 0
    assert created[0].catalog == catalog
    assert created[0].course_overview == course


@pytest.mark.django_db
def test_add_course_shifts_existing_courses():
    """add_catalog_courses shifts courses at or after the insertion point up by one."""
    catalog = make_catalog()
    c0, c1, c_new = make_course(), make_course(), make_course()

    cc0 = make_catalog_course(catalog, c0, position=0)
    cc1 = make_catalog_course(catalog, c1, position=1)

    with patch(PATCH_POLICY, return_value=True):
        CatalogCourseService.add_catalog_courses(catalog, [c_new.id], position=0)

    cc0.refresh_from_db()
    cc1.refresh_from_db()
    inserted = CatalogCourse.objects.get(catalog=catalog, course_overview=c_new)

    assert inserted.position == 0
    assert cc0.position == 1
    assert cc1.position == 2


@pytest.mark.django_db
def test_add_course_appends_at_end_when_no_position_given():
    """add_catalog_courses appends at the end when position=None."""
    catalog = make_catalog()
    c0, c1 = make_course(), make_course()

    make_catalog_course(catalog, c0, position=0)

    with patch(PATCH_POLICY, return_value=True):
        created = CatalogCourseService.add_catalog_courses(catalog, [c1.id], position=None)

    assert created[0].position == 1


# ---------------------------------------------------------------------------
# remove_catalog_courses
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_remove_catalog_course_deletes_it():
    """remove_catalog_courses deletes the specified CatalogCourse."""
    catalog = make_catalog()
    c0, c1 = make_course(), make_course()

    make_catalog_course(catalog, c0, position=0)
    cc1 = make_catalog_course(catalog, c1, position=1)

    deleted = CatalogCourseService.remove_catalog_courses(catalog, [cc1.id])

    assert deleted == 1
    assert not CatalogCourse.objects.filter(id=cc1.id).exists()


@pytest.mark.django_db
def test_remove_catalog_course_reorganizes_positions():
    """remove_catalog_courses fills the gap left by the deleted course."""
    catalog = make_catalog()
    c0, c1, c2 = make_course(), make_course(), make_course()

    cc0 = make_catalog_course(catalog, c0, position=0)
    cc1 = make_catalog_course(catalog, c1, position=1)
    cc2 = make_catalog_course(catalog, c2, position=2)

    CatalogCourseService.remove_catalog_courses(catalog, [cc1.id])

    cc0.refresh_from_db()
    cc2.refresh_from_db()

    assert cc0.position == 0
    assert cc2.position == 1


# ---------------------------------------------------------------------------
# update_course_position
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_update_course_position_moves_forward():
    """Moving a course to a higher index shifts intermediate courses down by one."""
    catalog = make_catalog()
    c0, c1, c2 = make_course(), make_course(), make_course()

    cc0 = make_catalog_course(catalog, c0, position=0)
    cc1 = make_catalog_course(catalog, c1, position=1)
    cc2 = make_catalog_course(catalog, c2, position=2)

    # Move cc0 from position 0 → 2
    CatalogCourseService.update_course_position(cc0, new_position=2)

    cc0.refresh_from_db()
    cc1.refresh_from_db()
    cc2.refresh_from_db()

    assert cc0.position == 2
    assert cc1.position == 0
    assert cc2.position == 1


@pytest.mark.django_db
def test_update_course_position_moves_backward():
    """Moving a course to a lower index shifts intermediate courses up by one."""
    catalog = make_catalog()
    c0, c1, c2 = make_course(), make_course(), make_course()

    cc0 = make_catalog_course(catalog, c0, position=0)
    cc1 = make_catalog_course(catalog, c1, position=1)
    cc2 = make_catalog_course(catalog, c2, position=2)

    # Move cc2 from position 2 → 0
    CatalogCourseService.update_course_position(cc2, new_position=0)

    cc0.refresh_from_db()
    cc1.refresh_from_db()
    cc2.refresh_from_db()

    assert cc2.position == 0
    assert cc0.position == 1
    assert cc1.position == 2
