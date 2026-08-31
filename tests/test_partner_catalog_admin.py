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
    """add_manager escapes HTML special characters in usernames (XSS guard).

    create_user bypasses form validators so the malicious string reaches the DB,
    letting us verify that format_html_join escapes it on output.
    """
    catalog = make_catalog()
    user = make_user(username="<script>alert(1)</script>")
    CatalogManager.objects.create(catalog=catalog, user=user, active=True)

    result = str(_admin().add_manager(catalog))
    assert "<script>" not in result
    assert "&lt;script&gt;" in result


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
def test_manager_prefetch_path_matches_fallback_path():
    """add_manager produces the same output via the prefetch path as via the fallback path.

    When the catalog object is fetched through PartnerCatalogAdmin.get_queryset,
    obj.active_managers_list is populated by the Prefetch. This test confirms that
    the prefetch path (production code path) behaves identically to the direct
    fallback path exercised by the other manager tests.
    """
    superuser = make_user(is_staff=True, is_superuser=True)
    catalog = make_catalog()
    user = make_user(username="mgr_prefetch")
    manager = CatalogManager.objects.create(catalog=catalog, user=user, active=True)

    admin_view = _admin()
    request = _get_request(superuser)

    catalog_from_qs = admin_view.get_queryset(request).get(pk=catalog.pk)
    result_prefetch = str(admin_view.add_manager(catalog_from_qs))

    result_fallback = str(admin_view.add_manager(catalog))

    change_url = reverse("admin:partner_catalog_catalogmanager_change", args=[manager.pk])
    assert change_url in result_prefetch
    assert "mgr_prefetch" in result_prefetch
    assert result_prefetch == result_fallback


@pytest.mark.django_db
@override_settings(ROOT_URLCONF=_ADMIN_URL_CONF)
def test_manager_prefetch_excludes_inactive_managers():
    """get_queryset Prefetch only loads active managers into active_managers_list."""
    superuser = make_user(is_staff=True, is_superuser=True)
    catalog = make_catalog()
    active_user = make_user(username="mgr_active")
    inactive_user = make_user(username="mgr_inactive")
    CatalogManager.objects.create(catalog=catalog, user=active_user, active=True)
    CatalogManager.objects.create(catalog=catalog, user=inactive_user, active=False)

    admin_view = _admin()
    catalog_from_qs = admin_view.get_queryset(_get_request(superuser)).get(pk=catalog.pk)

    assert len(catalog_from_qs.active_managers_list) == 1
    assert catalog_from_qs.active_managers_list[0].user.username == "mgr_active"


@pytest.mark.django_db
@override_settings(ROOT_URLCONF=_ADMIN_URL_CONF)
def test_changelist_view_injects_add_urls_into_context():
    """changelist_view passes the exact learner/course/manager add URLs to the template context."""
    superuser = make_user(is_staff=True, is_superuser=True)
    make_catalog()
    response = _admin().changelist_view(_get_request(superuser))
    context = response.context_data

    assert context["learner_add_url"] == reverse("admin:partner_catalog_cataloglearnerinvitation_add")
    assert context["course_add_url"] == reverse("admin:partner_catalog_catalogcourse_add")
    assert context["manager_add_url"] == reverse("admin:partner_catalog_catalogmanager_add")
