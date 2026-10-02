"""
Tests for the certified_count annotations in partner_catalog.services.certificates.

These run the real SQL subqueries against the test GeneratedCertificate model,
locking in the two fixes that made certified_count always 0:
- the users/courses subqueries must be correlated at the right OuterRef depth;
- the count subquery must return the distinct user count, not 1 per certificate row.
"""

# pylint: disable=redefined-outer-name

import pytest
from django.utils import timezone

from partner_catalog.edxapp_wrapper.certificates_module import certificate_statuses_model, generated_certificate_model
from partner_catalog.edxapp_wrapper.course_module import course_overview
from partner_catalog.models import CatalogCourse, CatalogCourseEnrollment, Partner
from partner_catalog.services.certificates import annotate_course_certified_count, annotate_partner_certified_count
from tests.factories import make_catalog, make_invitation, make_learner, make_partner, make_user

pytestmark = pytest.mark.django_db

CourseOverview = course_overview()
GeneratedCertificate = generated_certificate_model()
PASSED = certificate_statuses_model().ACTIVE
NOT_PASSED = certificate_statuses_model().REVOKED


def _certify(user, catalog_course, status=PASSED):
    """Create a certificate for the user in the catalog course's course run."""
    GeneratedCertificate.objects.create(
        user=user,
        course_id=catalog_course.course_overview_id,
        status=status,
    )


def _enroll(user, catalog_course, active=True):
    """Create a CatalogCourseEnrollment for the user in the catalog course."""
    CatalogCourseEnrollment.objects.create(
        user=user,
        catalog_course=catalog_course,
        active=active,
    )


def _add_learner(catalog, user, removed=False):
    """Create a CatalogLearner, active unless its accepted invitation was later removed."""
    now = timezone.now()
    invitation = make_invitation(
        catalog,
        user=user,
        invite_email=user.email,
        accepted_at=now,
        removed_at=now if removed else None,
    )
    return make_learner(catalog, user, invitation)


@pytest.fixture
def catalog():
    return make_catalog()


@pytest.fixture
def course_a(catalog):
    return CatalogCourse.objects.create(catalog=catalog, course_overview=CourseOverview.objects.create())


@pytest.fixture
def course_b(catalog):
    return CatalogCourse.objects.create(catalog=catalog, course_overview=CourseOverview.objects.create())


def test_course_certified_count_counts_each_certified_enrolled_user(course_a, course_b):
    certified_1, certified_2, not_passed, inactive, not_enrolled, other = (make_user() for _ in range(6))

    for user in (certified_1, certified_2, not_passed):
        _enroll(user, course_a)
    _enroll(inactive, course_a, active=False)
    _certify(certified_1, course_a)
    _certify(certified_2, course_a)
    _certify(not_passed, course_a, status=NOT_PASSED)
    _certify(inactive, course_a)
    _certify(not_enrolled, course_a)

    _enroll(other, course_b)
    _certify(other, course_b)

    counts = dict(
        annotate_course_certified_count(CatalogCourse.objects.all()).values_list("pk", "certified_count")
    )

    assert counts == {course_a.pk: 2, course_b.pk: 1}


def test_course_certified_count_is_zero_without_enrollments(course_a):
    _certify(make_user(), course_a)

    annotated = annotate_course_certified_count(CatalogCourse.objects.filter(pk=course_a.pk)).get()

    assert annotated.certified_count == 0


def test_partner_certified_count_counts_active_learners_of_its_catalogs(catalog, course_a, course_b):
    learner_1, learner_2, removed = make_user(), make_user(), make_user()
    _add_learner(catalog, learner_1)
    _add_learner(catalog, learner_2)
    _add_learner(catalog, removed, removed=True)
    _certify(learner_1, course_a)
    _certify(learner_1, course_b)
    _certify(learner_2, course_b)
    _certify(removed, course_a)

    other_partner = make_partner()

    counts = dict(
        annotate_partner_certified_count(Partner.objects.all()).values_list("pk", "certified_count")
    )

    assert counts == {catalog.partner.pk: 2, other_partner.pk: 0}
