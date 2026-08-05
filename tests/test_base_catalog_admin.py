"""
Tests for BaseCatalog admin — form pre-population and save_related sync logic (Suite 10).

Covers:
- BaseCatalogAdminForm.__init__: courses queryset is set on all forms
- BaseCatalogAdminForm.__init__: courses initial is empty for a new catalog
- BaseCatalogAdminForm.__init__: courses initial is pre-populated for an existing catalog
- BaseCatalogAdmin.save_related: adds newly selected courses
- BaseCatalogAdmin.save_related: removes deselected courses
- BaseCatalogAdmin.save_related: no-op when selection matches current state
- BaseCatalogAdmin.save_related: records added_by from request.user
- BaseCatalogAdmin.save_related: clears all courses when selection is empty
"""

from unittest.mock import MagicMock

import pytest
from django.contrib.admin.sites import AdminSite

from partner_catalog.admin import BaseCatalogAdmin, BaseCatalogAdminForm
from partner_catalog.models import BaseCatalog, BaseCatalogCourse
from partner_catalog.services.catalog_courses import CourseOverview
from tests.factories import make_user

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_base_catalog(slug_suffix="1"):
    """Create and return a BaseCatalog for testing."""
    return BaseCatalog.objects.create(name=f"Test Catalog {slug_suffix}", slug=f"test-catalog-{slug_suffix}")


def make_course():
    """Create and return a CourseOverview (test backend) instance."""
    return CourseOverview.objects.create()


def _admin():
    """Return a BaseCatalogAdmin instance bound to a fresh AdminSite."""
    return BaseCatalogAdmin(BaseCatalog, AdminSite())


def _request(user=None):
    """Return a mock request with the given user (or a new staff user)."""
    req = MagicMock()
    req.user = user or make_user(is_staff=True)
    return req


def _form(instance, selected_courses):
    """Return a mock form with cleaned_data and instance set."""
    frm = MagicMock()
    frm.instance = instance
    frm.cleaned_data = {'courses': selected_courses}
    return frm


# ---------------------------------------------------------------------------
# BaseCatalogAdminForm — __init__ pre-population
# ---------------------------------------------------------------------------

class TestBaseCatalogAdminFormInit:
    """Tests for BaseCatalogAdminForm.__init__ initialization behaviour."""

    @pytest.mark.django_db
    def test_courses_queryset_includes_all_courses(self):
        """The courses queryset covers all CourseOverview objects."""
        make_course()
        make_course()

        form = BaseCatalogAdminForm()

        assert form.fields['courses'].queryset.count() == 2

    @pytest.mark.django_db
    def test_courses_initial_is_empty_for_new_catalog(self):
        """Without an existing instance the courses initial is not set."""
        form = BaseCatalogAdminForm()

        assert not form.fields['courses'].initial

    @pytest.mark.django_db
    def test_courses_initial_pre_populates_existing_courses(self):
        """With an existing catalog the initial value matches its current courses."""
        catalog = make_base_catalog()
        course1 = make_course()
        course2 = make_course()
        BaseCatalogCourse.objects.create(base_catalog=catalog, course_overview=course1)
        BaseCatalogCourse.objects.create(base_catalog=catalog, course_overview=course2)

        form = BaseCatalogAdminForm(instance=catalog)

        initial_ids = {c.pk for c in form.fields['courses'].initial}
        assert initial_ids == {course1.pk, course2.pk}

    @pytest.mark.django_db
    def test_courses_initial_is_empty_for_catalog_with_no_courses(self):
        """A catalog with no courses yields an empty initial queryset."""
        catalog = make_base_catalog()

        form = BaseCatalogAdminForm(instance=catalog)

        assert not list(form.fields['courses'].initial)


# ---------------------------------------------------------------------------
# BaseCatalogAdmin.save_related — course sync logic
# ---------------------------------------------------------------------------

class TestBaseCatalogAdminSaveRelated:
    """Tests for BaseCatalogAdmin.save_related diff/sync logic."""

    @pytest.mark.django_db
    def test_adds_newly_selected_courses(self):
        """save_related creates BaseCatalogCourse entries for newly selected courses."""
        catalog = make_base_catalog(slug_suffix="a")
        course1 = make_course()
        course2 = make_course()

        _admin().save_related(_request(), _form(catalog, [course1, course2]), [], change=True)

        assert catalog.courses.count() == 2
        assert BaseCatalogCourse.objects.filter(base_catalog=catalog, course_overview=course1).exists()
        assert BaseCatalogCourse.objects.filter(base_catalog=catalog, course_overview=course2).exists()

    @pytest.mark.django_db
    def test_removes_deselected_courses(self):
        """save_related deletes BaseCatalogCourse entries for deselected courses."""
        catalog = make_base_catalog(slug_suffix="b")
        course1 = make_course()
        course2 = make_course()
        BaseCatalogCourse.objects.create(base_catalog=catalog, course_overview=course1)
        BaseCatalogCourse.objects.create(base_catalog=catalog, course_overview=course2)

        _admin().save_related(_request(), _form(catalog, [course1]), [], change=True)

        assert catalog.courses.count() == 1
        assert BaseCatalogCourse.objects.filter(base_catalog=catalog, course_overview=course1).exists()
        assert not BaseCatalogCourse.objects.filter(base_catalog=catalog, course_overview=course2).exists()

    @pytest.mark.django_db
    def test_no_op_when_selection_matches_current_state(self):
        """save_related does not create duplicates when the selection is unchanged."""
        catalog = make_base_catalog(slug_suffix="c")
        course = make_course()
        BaseCatalogCourse.objects.create(base_catalog=catalog, course_overview=course)

        _admin().save_related(_request(), _form(catalog, [course]), [], change=True)

        assert catalog.courses.count() == 1
        assert BaseCatalogCourse.objects.filter(base_catalog=catalog).count() == 1

    @pytest.mark.django_db
    def test_records_added_by_from_request_user(self):
        """save_related sets the added_by field to the current request user."""
        catalog = make_base_catalog(slug_suffix="d")
        course = make_course()
        user = make_user()

        _admin().save_related(_request(user=user), _form(catalog, [course]), [], change=True)

        entry = BaseCatalogCourse.objects.get(base_catalog=catalog, course_overview=course)
        assert entry.added_by == user

    @pytest.mark.django_db
    def test_clears_all_courses_when_selection_is_empty(self):
        """save_related removes all entries when the submitted selection is empty."""
        catalog = make_base_catalog(slug_suffix="e")
        course1 = make_course()
        course2 = make_course()
        BaseCatalogCourse.objects.create(base_catalog=catalog, course_overview=course1)
        BaseCatalogCourse.objects.create(base_catalog=catalog, course_overview=course2)

        _admin().save_related(_request(), _form(catalog, []), [], change=True)

        assert not catalog.courses.count()
