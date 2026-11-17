"""
Tests for the endpoint that logs the courses a catalog page could not load.

``POST /api/v1/catalogs/<id>/course-load-failures/`` on ``LearnerCatalogViewSet``.
"""

import logging

import pytest
from django.core.cache import cache
from django.urls import resolve
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from partner_catalog.api.throttles import CourseLoadFailuresThrottle
from partner_catalog.edxapp_wrapper.course_module import course_overview
from partner_catalog.models import CatalogCourse
from tests.factories import make_catalog, make_invitation, make_learner, make_user

CourseOverview = course_overview()

LOGGER_NAME = "partner_catalog.api.v1.learner_views"

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def clear_throttle_history():
    """Start and end every test without throttle history, which lives in the cache."""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture(name="records")
def fixture_records(caplog):
    """Return a function that lists the entries written by the learner views logger."""
    caplog.set_level(logging.WARNING, logger=LOGGER_NAME)
    return lambda: [record for record in caplog.records if record.name == LOGGER_NAME]


def make_catalog_with_courses(count, **kwargs):
    """Create a catalog with ``count`` courses; return it and the course keys, in order."""
    catalog = make_catalog(**kwargs)
    course_keys = []
    for position in range(count):
        course = CourseOverview.objects.create()
        CatalogCourse.objects.create(catalog=catalog, course_overview=course, position=position)
        course_keys.append(str(course.id))
    return catalog, course_keys


def make_active_learner(catalog):
    """Create a user who has accepted an invitation to the catalog."""
    user = make_user()
    invitation = make_invitation(catalog, user=user, invite_email=user.email, accepted_at=timezone.now())
    make_learner(catalog, user, invitation)
    return user


def post_report(catalog, body, user=None):
    """
    POST ``body`` to the catalog's endpoint, authenticated as ``user`` when there is one.

    The URL is resolved to the view the router builds, so the action's route and throttle are the
    real ones. The view is called directly because the test settings have no session middleware.
    """
    path = f"/api/v1/catalogs/{catalog.id}/course-load-failures/"
    request = APIRequestFactory().post(path, body, format="json")
    if user is not None:
        force_authenticate(request, user=user)
    match = resolve(path)
    return match.func(request, *match.args, **match.kwargs)


def test_some_courses_failed_writes_one_warning(records):
    catalog, keys = make_catalog_with_courses(3, slug="psp-onboarding")
    user = make_active_learner(catalog)

    response = post_report(catalog, {"failures": [{"course_key": keys[1], "status": 404}]}, user=user)

    assert response.status_code == 204
    [record] = records()
    assert record.levelno == logging.WARNING
    assert record.getMessage() == (
        f"Catalog courses failed to load (catalog_id={catalog.id}, catalog_slug=psp-onboarding, "
        f"failed=1/3): {keys[1]} (404)"
    )


def test_all_courses_failed_writes_one_error(records):
    catalog, keys = make_catalog_with_courses(2)
    user = make_active_learner(catalog)

    response = post_report(
        catalog,
        {"failures": [{"course_key": keys[0], "status": 404}, {"course_key": keys[1], "status": 500}]},
        user=user,
    )

    assert response.status_code == 204
    [record] = records()
    assert record.levelno == logging.ERROR
    assert record.getMessage().endswith(f"failed=2/2): {keys[0]} (404), {keys[1]} (500)")


def test_failure_without_a_status_is_logged_as_no_response(records):
    catalog, keys = make_catalog_with_courses(3)
    user = make_active_learner(catalog)

    response = post_report(
        catalog,
        {"failures": [{"course_key": keys[0], "status": None}, {"course_key": keys[1]}]},
        user=user,
    )

    assert response.status_code == 204
    [record] = records()
    assert record.getMessage().endswith(f"failed=2/3): {keys[0]} (no response), {keys[1]} (no response)")


def test_course_reported_twice_counts_once(records):
    catalog, keys = make_catalog_with_courses(2)
    user = make_active_learner(catalog)

    response = post_report(
        catalog,
        {"failures": [{"course_key": keys[0], "status": 404}, {"course_key": keys[0], "status": 404}]},
        user=user,
    )

    assert response.status_code == 204
    [record] = records()
    assert record.levelno == logging.WARNING
    assert record.getMessage().endswith(f"failed=1/2): {keys[0]} (404)")


@pytest.mark.parametrize(
    "build_body",
    [
        pytest.param(lambda keys, other_key: {}, id="no failures field"),
        pytest.param(lambda keys, other_key: {"failures": []}, id="empty list"),
        pytest.param(lambda keys, other_key: {"failures": [{"status": 404}]}, id="no course key"),
        pytest.param(
            lambda keys, other_key: {"failures": [{"course_key": keys[0], "status": 42}]},
            id="status out of range",
        ),
        pytest.param(
            lambda keys, other_key: {"failures": [{"course_key": keys[0], "status": "not found"}]},
            id="status not a number",
        ),
        pytest.param(
            lambda keys, other_key: {"failures": [{"course_key": other_key, "status": 404}]},
            id="course of another catalog",
        ),
        pytest.param(
            lambda keys, other_key: {
                "failures": [
                    {"course_key": keys[0], "status": 404},
                    {"course_key": "course-v1:Org+Course+Run\nERROR forged entry", "status": 404},
                ]
            },
            id="unknown course next to a valid one",
        ),
    ],
)
def test_invalid_report_is_rejected_and_not_logged(records, build_body):
    catalog, keys = make_catalog_with_courses(2)
    _, [other_key] = make_catalog_with_courses(1)
    user = make_active_learner(catalog)

    response = post_report(catalog, build_body(keys, other_key), user=user)

    assert response.status_code == 400
    assert not records()


def test_user_who_cannot_see_the_catalog_gets_404(records):
    catalog, keys = make_catalog_with_courses(2)

    response = post_report(catalog, {"failures": [{"course_key": keys[0], "status": 404}]}, user=make_user())

    assert response.status_code == 404
    assert not records()


def test_anonymous_user_is_rejected(records):
    catalog, keys = make_catalog_with_courses(2)

    response = post_report(catalog, {"failures": [{"course_key": keys[0], "status": 404}]})

    assert response.status_code in (401, 403)
    assert not records()


def test_reports_are_limited_per_user(records):
    catalog, keys = make_catalog_with_courses(2)
    user = make_active_learner(catalog)
    other_user = make_active_learner(catalog)
    body = {"failures": [{"course_key": keys[0], "status": 404}]}
    allowed = CourseLoadFailuresThrottle().num_requests

    statuses = [post_report(catalog, body, user=user).status_code for _ in range(allowed + 1)]

    assert statuses == [204] * allowed + [429]
    assert len(records()) == allowed
    assert post_report(catalog, body, user=other_user).status_code == 204
