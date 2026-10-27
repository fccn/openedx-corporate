"""
Tests for the metrics exposed by the manager API: partners, catalogs, courses and learners.
"""

# pylint: disable=redefined-outer-name

from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from partner_catalog.api.v1.serializers import PartnerSerializer
from partner_catalog.api.v1.views import (
    CatalogCourseViewSet,
    CatalogLearnerViewset,
    PartnerCatalogViewSet,
    PartnerViewset,
)
from partner_catalog.edxapp_wrapper.certificates_module import certificate_statuses_model, generated_certificate_model
from partner_catalog.edxapp_wrapper.course_module import course_overview
from partner_catalog.models import CatalogCourse, CatalogCourseEnrollment, CatalogManager
from partner_catalog.services import progress
from tests.factories import make_catalog, make_catalog_learner, make_certificate, make_invitation, make_user

pytestmark = pytest.mark.django_db

CourseOverview = course_overview()
GeneratedCertificate = generated_certificate_model()
CertificateStatuses = certificate_statuses_model()


def test_partner_enrollments_counts_only_active_learners():
    catalog = make_catalog()
    other_catalog = make_catalog(partner=catalog.partner)
    make_catalog_learner(catalog)
    make_catalog_learner(other_catalog)
    make_catalog_learner(catalog, removed=True)

    view = PartnerViewset()
    view.request = SimpleNamespace(user=make_user(is_staff=True))
    partner = view.get_queryset().get(pk=catalog.partner.pk)

    assert PartnerSerializer(partner).data["enrollments"] == 2


# ---------------------------------------------------------------------------
# Certificate based metrics through the real list/detail endpoints
# ---------------------------------------------------------------------------

def _add_courses(catalog, count):
    return [
        CatalogCourse.objects.create(catalog=catalog, course_overview=CourseOverview.objects.create(), position=i)
        for i in range(count)
    ]


def _get(viewset, action, user, params=None, **kwargs):
    """Call a viewset action through APIRequestFactory and return the response data."""
    request = APIRequestFactory().get("/", params)
    force_authenticate(request, user=user)
    response = viewset.as_view({"get": action})(request, **kwargs)
    assert response.status_code == 200, response.data
    return response.data


def _post(viewset, action, user, data, **kwargs):
    """POST to a viewset action through APIRequestFactory and return the response data."""
    request = APIRequestFactory().post("/", data, format="json")
    force_authenticate(request, user=user)
    response = viewset.as_view({"post": action})(request, **kwargs)
    assert response.status_code == 201, response.data
    return response.data


def _catalog_list(user, params=None):
    return {row["id"]: row for row in _get(PartnerCatalogViewSet, "list", user, params)}


def _catalog_row(user, catalog):
    return _catalog_list(user)[str(catalog.pk)]


def _course_list(user, catalog):
    return {row["id"]: row for row in _get(CatalogCourseViewSet, "list", user, catalog_pk=str(catalog.pk))}


def _learner_list(user, catalog):
    return {row["id"]: row for row in _get(CatalogLearnerViewset, "list", user, catalog_pk=str(catalog.pk))}


@pytest.fixture
def staff():
    return make_user(is_staff=True)


@pytest.fixture
def catalog_3x4():
    """3 active learners, 4 courses, 6 passed certificates, plus noise that must not be counted."""
    catalog = make_catalog()
    courses = _add_courses(catalog, 4)
    learners = [make_catalog_learner(catalog) for _ in range(3)]
    for course in courses[:3]:
        make_certificate(learners[0].user, course)
    for course in courses[:2]:
        make_certificate(learners[1].user, course)
    make_certificate(learners[2].user, courses[3])
    for course in courses[:2]:
        CatalogCourseEnrollment.objects.create(user=learners[0].user, catalog_course=course, active=True)

    removed = make_catalog_learner(catalog, removed=True)
    make_certificate(removed.user, courses[3])
    make_certificate(learners[2].user, courses[0], status=CertificateStatuses.notpassing)
    make_invitation(catalog, invite_email="pending@example.com")

    return SimpleNamespace(catalog=catalog, courses=courses, learners=learners, removed=removed)


@pytest.mark.parametrize("as_staff", [True, False])
def test_catalog_list_returns_every_count(catalog_3x4, staff, as_staff):
    catalog = catalog_3x4.catalog
    if as_staff:
        user = staff
    else:
        user = make_user()
        CatalogManager.objects.create(catalog=catalog, user=user, active=True)
    make_catalog()  # a catalog the non-staff manager does not manage

    rows = _catalog_list(user)

    assert len(rows) == (2 if as_staff else 1)
    row = rows[str(catalog.pk)]
    assert {key: row[key] for key in (
        "courses", "enrollments", "total_learners", "active_learners", "pending_invitations", "certified",
        "completion_rate",
    )} == {
        "courses": 4,
        "enrollments": 2,
        "total_learners": 4,
        "active_learners": 3,
        "pending_invitations": 1,
        "certified": 3,
        "completion_rate": 50.0,
    }


def test_learners_list_returns_certificates_per_learner(catalog_3x4, staff):
    rows = _learner_list(staff, catalog_3x4.catalog)

    assert {pk: row["certified"] for pk, row in rows.items()} == {
        catalog_3x4.learners[0].pk: 3,
        catalog_3x4.learners[1].pk: 2,
        catalog_3x4.learners[2].pk: 1,
        catalog_3x4.removed.pk: 0,
    }


def test_course_list_returns_certified_learners_and_completion_rate(catalog_3x4, staff):
    rows = _course_list(staff, catalog_3x4.catalog)

    assert {pk: (row["certified"], row["completion_rate"]) for pk, row in rows.items()} == {
        catalog_3x4.courses[0].pk: (2, 66.7),
        catalog_3x4.courses[1].pk: (2, 66.7),
        catalog_3x4.courses[2].pk: (1, 33.3),
        catalog_3x4.courses[3].pk: (1, 33.3),
    }


def test_course_completion_rate_is_certified_over_active_catalog_learners(staff):
    catalog = make_catalog()
    (course,) = _add_courses(catalog, 1)
    learners = [make_catalog_learner(catalog) for _ in range(4)]
    make_certificate(learners[0].user, course)
    make_certificate(learners[1].user, course)

    assert _course_list(staff, catalog)[course.pk]["completion_rate"] == 50.0


def test_certificate_counts_as_completed_regardless_of_unit_progress(staff, mocker):
    catalog = make_catalog()
    (course,) = _add_courses(catalog, 1)
    certified_at_70, uncertified_at_100, certified_at_70_too = (make_catalog_learner(catalog).user for _ in range(3))
    for user in (certified_at_70, uncertified_at_100, certified_at_70_too):
        CatalogCourseEnrollment.objects.create(user=user, catalog_course=course, active=True)
    make_certificate(certified_at_70, course)
    make_certificate(certified_at_70_too, course)
    mocker.patch.object(
        progress,
        "get_course_blocks_completion_summary",
        side_effect=lambda course_key, user: (
            {"complete_count": 10, "incomplete_count": 0} if user == uncertified_at_100
            else {"complete_count": 7, "incomplete_count": 3}
        ),
    )

    assert _course_list(staff, catalog)[course.pk]["completion_rate"] == 66.7
    assert _catalog_row(staff, catalog)["completion_rate"] == 66.7


def test_catalog_without_courses_has_zero_completion_rate(staff):
    catalog = make_catalog()
    make_catalog_learner(catalog)
    make_catalog_learner(catalog)

    assert _catalog_row(staff, catalog)["completion_rate"] == 0.0


def test_catalog_without_active_learners_has_zero_completion_rate(staff):
    catalog = make_catalog()
    (course,) = _add_courses(catalog, 1)
    removed = make_catalog_learner(catalog, removed=True)
    make_certificate(removed.user, course)

    assert _catalog_row(staff, catalog)["completion_rate"] == 0.0
    assert _course_list(staff, catalog)[course.pk]["completion_rate"] == 0.0


def test_one_course_catalog_numbers_are_consistent(staff):
    catalog = make_catalog()
    (course,) = _add_courses(catalog, 1)
    learners = [make_catalog_learner(catalog) for _ in range(3)]
    make_certificate(learners[0].user, course)

    catalog_row = _catalog_row(staff, catalog)
    catalog_detail = _get(PartnerCatalogViewSet, "retrieve", staff, pk=str(catalog.pk))
    course_row = _course_list(staff, catalog)[course.pk]
    course_detail = _get(
        CatalogCourseViewSet, "retrieve", staff, catalog_pk=str(catalog.pk), course_id=str(course.course_overview_id)
    )
    partner = PartnerViewset()
    partner.request = SimpleNamespace(user=staff)
    partner_row = PartnerSerializer(partner.get_queryset().get(pk=catalog.partner.pk)).data

    assert catalog_row["certified"] == catalog_detail["certified"] == partner_row["certified"] == 1
    assert course_row["certified"] == course_detail["certified"] == 1
    assert catalog_row["completion_rate"] == catalog_detail["completion_rate"] == 33.3
    assert course_row["completion_rate"] == course_detail["completion_rate"] == 33.3


@pytest.mark.parametrize("list_endpoint", ["catalogs", "courses"])
def test_list_endpoints_query_count_does_not_grow_with_learners(staff, mocker, list_endpoint):
    summary = mocker.patch.object(progress, "get_course_blocks_completion_summary", return_value=None)

    def query_count(learners):
        catalog = make_catalog()
        courses = _add_courses(catalog, 2)
        for _ in range(learners):
            learner = make_catalog_learner(catalog)
            make_certificate(learner.user, courses[0])
            CatalogCourseEnrollment.objects.create(user=learner.user, catalog_course=courses[0], active=True)
        with CaptureQueriesContext(connection) as queries:
            if list_endpoint == "catalogs":
                _catalog_list(staff, {"partner": catalog.partner_id})
            else:
                _course_list(staff, catalog)
        return len(queries)

    assert query_count(2) == query_count(50)
    summary.assert_not_called()


# ---------------------------------------------------------------------------
# Responses built from instances created in the request
# ---------------------------------------------------------------------------

def test_add_courses_response_has_the_same_metrics_as_the_course_list(staff):
    catalog = make_catalog()
    learners = [make_catalog_learner(catalog) for _ in range(2)]
    overview = CourseOverview.objects.create(org=catalog.partner.organization.short_name)
    GeneratedCertificate.objects.create(
        user=learners[0].user, course_id=overview.id, status=CertificateStatuses.downloadable
    )

    (added,) = _post(
        PartnerCatalogViewSet, "add_courses", staff, {"course_ids": [overview.id]}, pk=str(catalog.pk)
    )
    listed = _course_list(staff, catalog)[added["id"]]

    assert {key: added[key] for key in ("enrollments", "certified", "completion_rate")} == {
        "enrollments": 0,
        "certified": 1,
        "completion_rate": 50.0,
    }
    assert {key: added[key] for key in ("enrollments", "certified", "completion_rate")} == {
        key: listed[key] for key in ("enrollments", "certified", "completion_rate")
    }


def test_catalog_create_response_has_the_same_metrics_as_the_catalog_list(staff):
    partner = make_catalog().partner
    now = timezone.now()

    created = _post(PartnerCatalogViewSet, "create", staff, {
        "name": "Created catalog",
        "partner": partner.pk,
        "available_start_date": now - timedelta(days=1),
        "available_end_date": now + timedelta(days=30),
    })
    metrics = ("courses", "enrollments", "total_learners", "active_learners", "pending_invitations", "certified",
               "completion_rate")

    assert {key: created[key] for key in metrics} == {
        "courses": 0,
        "enrollments": 0,
        "total_learners": 0,
        "active_learners": 0,
        "pending_invitations": 0,
        "certified": 0,
        "completion_rate": 0.0,
    }
    assert {key: created[key] for key in metrics} == {
        key: _catalog_list(staff)[created["id"]][key] for key in metrics
    }
