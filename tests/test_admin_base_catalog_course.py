"""
Tests for BaseCatalogCourseAdmin sticky base_catalog behaviour.

When the user clicks "Save and add another" after creating a BaseCatalogCourse,
the redirect URL should carry the same base_catalog ID so that the next add-form
comes pre-populated.
"""

import pytest
from django.contrib.admin.sites import AdminSite
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory, override_settings

from partner_catalog.admin import BaseCatalogCourseAdmin
from partner_catalog.edxapp_wrapper.course_module import course_overview
from partner_catalog.models import BaseCatalog, BaseCatalogCourse

from tests.factories import make_user

_ADMIN_URL_CONF = "tests.admin_test_urls"

CourseOverview = course_overview()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_course():
    """Create and return a CourseOverview instance."""
    return CourseOverview.objects.create()


def _make_base_catalog(name="Test Base Catalog"):
    """Create and return a BaseCatalog with the given name."""
    return BaseCatalog.objects.create(name=name, slug=name.lower().replace(" ", "-"))


def _post_request(user, data=None):
    """Build a POST request with messages middleware attached."""
    factory = RequestFactory()
    request = factory.post("/fake-admin/", data=data or {})
    request.user = user
    request.session = {}
    request._messages = FallbackStorage(request)  # pylint: disable=protected-access
    return request


def _get_request(user, params=None):
    """Build a GET request with messages middleware attached."""
    factory = RequestFactory()
    query = f"?{params}" if params else ""
    request = factory.get(f"/fake-admin/{query}")
    request.user = user
    request.session = {}
    request._messages = FallbackStorage(request)  # pylint: disable=protected-access
    return request


def _admin_view():
    return BaseCatalogCourseAdmin(BaseCatalogCourse, AdminSite())


# ---------------------------------------------------------------------------
# response_add — redirect preserves base_catalog when "_addanother" posted
# ---------------------------------------------------------------------------

@pytest.mark.django_db
@override_settings(ROOT_URLCONF=_ADMIN_URL_CONF)
def test_response_add_addanother_redirects_with_base_catalog():
    """Clicking 'Save and add another' redirects to the add URL with base_catalog param."""
    admin_user = make_user(is_staff=True, is_superuser=True)
    catalog = _make_base_catalog()
    course = _make_course()
    entry = BaseCatalogCourse.objects.create(
        base_catalog=catalog,
        course_overview=course,
        added_by=admin_user,
    )

    request = _post_request(admin_user, data={"_addanother": "1"})
    response = _admin_view().response_add(request, entry)

    assert response.status_code == 302
    assert f"base_catalog={catalog.pk}" in response["Location"]


@pytest.mark.django_db
@override_settings(ROOT_URLCONF=_ADMIN_URL_CONF)
def test_response_add_save_does_not_add_base_catalog_param():
    """A plain 'Save' (no _addanother) does not append base_catalog to the redirect."""
    admin_user = make_user(is_staff=True, is_superuser=True)
    catalog = _make_base_catalog()
    course = _make_course()
    entry = BaseCatalogCourse.objects.create(
        base_catalog=catalog,
        course_overview=course,
        added_by=admin_user,
    )

    request = _post_request(admin_user, data={})
    response = _admin_view().response_add(request, entry)

    assert response.status_code == 302
    assert "base_catalog" not in response["Location"]


# ---------------------------------------------------------------------------
# get_changeform_initial_data — pre-populates from GET param
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_get_changeform_initial_data_sets_base_catalog_from_get():
    """GET ?base_catalog=<id> pre-populates the initial form data."""
    admin_user = make_user(is_staff=True, is_superuser=True)
    catalog = _make_base_catalog()

    request = _get_request(admin_user, params=f"base_catalog={catalog.pk}")
    initial = _admin_view().get_changeform_initial_data(request)

    assert str(initial.get("base_catalog")) == str(catalog.pk)


@pytest.mark.django_db
def test_get_changeform_initial_data_without_param_is_empty():
    """Without a GET param, base_catalog is absent from initial data."""
    admin_user = make_user(is_staff=True, is_superuser=True)

    request = _get_request(admin_user)
    initial = _admin_view().get_changeform_initial_data(request)

    assert "base_catalog" not in initial
