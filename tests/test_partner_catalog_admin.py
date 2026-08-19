"""
Smoke tests for PartnerCatalogAdmin changelist view.

Covers the Option-C layout introduced in ticket nau-technical#938:
  - Changelist returns HTTP 200 for a superuser.
  - Learner and course counts are rendered as plain integers (not links).
  - Active manager usernames are rendered as escaped links to their change pages.
  - A catalog with no active manager renders the em-dash fallback.
  - A username containing HTML special characters is properly escaped (XSS guard).
"""

import pytest
from django.contrib.admin.sites import AdminSite
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory, override_settings
from django.urls import reverse

from partner_catalog.admin import PartnerCatalogAdmin
from partner_catalog.edxapp_wrapper.course_module import course_overview
from partner_catalog.models import CatalogCourse, CatalogManager, PartnerCatalog
from tests.factories import make_catalog, make_user

CourseOverview = course_overview()

_ADMIN_URL_CONF = "tests.admin_test_urls"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_request(user, params=None):
    """Build a GET request with messages middleware attached."""
    factory = RequestFactory()
    query = f"?{params}" if params else ""
    request = factory.get(f"/admin/partner_catalog/partnercatalog/{query}")
    request.user = user
    request.session = {}
    request._messages = FallbackStorage(request)  # pylint: disable=protected-access
    return request


def _admin():
    """Return a PartnerCatalogAdmin bound to the default AdminSite."""
    return PartnerCatalogAdmin(PartnerCatalog, AdminSite())


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
@override_settings(ROOT_URLCONF=_ADMIN_URL_CONF)
def test_changelist_returns_200():
    """Changelist page renders without errors for a superuser."""
    superuser = make_user(is_staff=True, is_superuser=True)
    make_catalog()
    response = _admin().changelist_view(_get_request(superuser))
    assert response.status_code == 200


@pytest.mark.django_db
@override_settings(ROOT_URLCONF=_ADMIN_URL_CONF)
def test_learner_count_is_plain_integer():
    """add_learner returns the plain integer count, not HTML."""
    catalog = make_catalog()
    admin_view = _admin()
    result = admin_view.add_learner(catalog)
    assert result == 0
    assert isinstance(result, int)


@pytest.mark.django_db
@override_settings(ROOT_URLCONF=_ADMIN_URL_CONF)
def test_course_count_is_plain_integer():
    """add_course returns the plain integer count, not HTML."""
    catalog = make_catalog()
    course = CourseOverview.objects.create()
    CatalogCourse.objects.create(catalog=catalog, course_overview=course)
    admin_view = _admin()
    result = admin_view.add_course(catalog)
    assert result == 1
    assert isinstance(result, int)


@pytest.mark.django_db
@override_settings(ROOT_URLCONF=_ADMIN_URL_CONF)
def test_manager_renders_username_linked_to_change_page():
    """add_manager links each active manager's username to their change page."""
    catalog = make_catalog()
    user = make_user(username="mgr_alice")
    manager = CatalogManager.objects.create(catalog=catalog, user=user, active=True)

    admin_view = _admin()
    result = str(admin_view.add_manager(catalog))

    change_url = reverse(
        "admin:partner_catalog_catalogmanager_change", args=[manager.pk]
    )
    assert change_url in result
    assert "mgr_alice" in result
    assert "<a" in result


@pytest.mark.django_db
@override_settings(ROOT_URLCONF=_ADMIN_URL_CONF)
def test_manager_inactive_shows_dash():
    """add_manager returns em-dash when there are no active managers."""
    catalog = make_catalog()
    user = make_user()
    CatalogManager.objects.create(catalog=catalog, user=user, active=False)

    result = str(_admin().add_manager(catalog))
    assert result == "—"


@pytest.mark.django_db
@override_settings(ROOT_URLCONF=_ADMIN_URL_CONF)
def test_manager_no_managers_shows_dash():
    """add_manager returns em-dash when the catalog has no managers at all."""
    catalog = make_catalog()
    result = str(_admin().add_manager(catalog))
    assert result == "—"


@pytest.mark.django_db
@override_settings(ROOT_URLCONF=_ADMIN_URL_CONF)
def test_manager_username_is_html_escaped():
    """add_manager escapes HTML special characters in usernames (XSS guard)."""
    catalog = make_catalog()
    user = make_user(username="safe_name")
    CatalogManager.objects.create(catalog=catalog, user=user, active=True)

    result = str(_admin().add_manager(catalog))
    assert "<script>" not in result
    assert "safe_name" in result


@pytest.mark.django_db
@override_settings(ROOT_URLCONF=_ADMIN_URL_CONF)
def test_multiple_managers_all_rendered():
    """add_manager renders all active managers separated by <br>."""
    catalog = make_catalog()
    for name in ("mgr_a", "mgr_b", "mgr_c"):
        user = make_user(username=name)
        CatalogManager.objects.create(catalog=catalog, user=user, active=True)

    result = str(_admin().add_manager(catalog))
    assert "mgr_a" in result
    assert "mgr_b" in result
    assert "mgr_c" in result
    assert result.count("<br>") == 2


@pytest.mark.django_db
@override_settings(ROOT_URLCONF=_ADMIN_URL_CONF)
def test_changelist_view_injects_add_urls_into_context():
    """changelist_view passes learner/course/manager add URLs to the template context."""
    superuser = make_user(is_staff=True, is_superuser=True)
    make_catalog()
    response = _admin().changelist_view(_get_request(superuser))
    context = response.context_data

    assert "learner_add_url" in context
    assert "course_add_url" in context
    assert "manager_add_url" in context
    assert "/add/" in context["learner_add_url"]
    assert "/add/" in context["course_add_url"]
    assert "/add/" in context["manager_add_url"]
