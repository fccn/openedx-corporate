"""
Tests for the certificate based metrics in partner_catalog.services.certificates.

These run the real SQL subqueries against the test GeneratedCertificate model. They lock in:
- the users/courses subqueries correlated at the right OuterRef depth;
- the count subquery returning one count, not 1 per certificate row;
- every number counting only the passed certificates of the catalog's active learners
  in the catalog's courses.
"""

# pylint: disable=redefined-outer-name

import pytest
from django.utils import timezone

from partner_catalog.edxapp_wrapper.certificates_module import certificate_statuses_model, generated_certificate_model
from partner_catalog.edxapp_wrapper.course_module import course_overview
from partner_catalog.models import CatalogCourse, CatalogCourseEnrollment, CatalogLearner, Partner, PartnerCatalog
from partner_catalog.services.certificates import (
    annotate_catalog_certificates_count,
    annotate_catalog_certified_count,
    annotate_course_certified_count,
    annotate_course_learners_count,
    annotate_learner_certified_count,
    annotate_partner_certified_count,
    compute_completion_rate,
)
from tests.factories import make_catalog, make_invitation, make_learner, make_partner, make_user

pytestmark = pytest.mark.django_db

CourseOverview = course_overview()
GeneratedCertificate = generated_certificate_model()
CertificateStatuses = certificate_statuses_model()
PASSED = CertificateStatuses.downloadable


def _certify(user, catalog_course, status=PASSED):
    """Create a certificate for the user in the catalog course's course run."""
    GeneratedCertificate.objects.create(
        user=user,
        course_id=catalog_course.course_overview_id,
        status=status,
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


def _add_course(catalog, overview=None):
    """Add a course (a new course run unless one is given) to the catalog."""
    return CatalogCourse.objects.create(catalog=catalog, course_overview=overview or CourseOverview.objects.create())


def _learner_counts():
    return dict(annotate_learner_certified_count(CatalogLearner.objects.all()).values_list("pk", "certified_count"))


def _course_counts():
    return dict(annotate_course_certified_count(CatalogCourse.objects.all()).values_list("pk", "certified_count"))


def _catalog_counts(annotator=annotate_catalog_certified_count, field="certified_count"):
    return dict(annotator(PartnerCatalog.objects.all()).values_list("pk", field))


def _partner_counts():
    return dict(annotate_partner_certified_count(Partner.objects.all()).values_list("pk", "certified_count"))


@pytest.fixture
def catalog():
    return make_catalog()


@pytest.fixture
def course_a(catalog):
    return _add_course(catalog)


@pytest.fixture
def course_b(catalog):
    return _add_course(catalog)


# ---------------------------------------------------------------------------
# Learner scope: certificates per learner
# ---------------------------------------------------------------------------

def test_learner_certificates_counts_each_certified_course(catalog, course_a, course_b):
    course_c = _add_course(catalog)
    three_certificates = _add_learner(catalog, make_user())
    one_certificate = _add_learner(catalog, make_user())
    none = _add_learner(catalog, make_user())
    for course in (course_a, course_b, course_c):
        _certify(three_certificates.user, course)
    _certify(one_certificate.user, course_b)

    assert _learner_counts() == {three_certificates.pk: 3, one_certificate.pk: 1, none.pk: 0}


def test_learner_certificates_ignore_courses_outside_the_catalog(catalog, course_a):  # pylint: disable=unused-argument
    learner = _add_learner(catalog, make_user())
    _certify(learner.user, _add_course(make_catalog()))

    assert _learner_counts()[learner.pk] == 0


# ---------------------------------------------------------------------------
# Course scope: certified learners
# ---------------------------------------------------------------------------

def test_course_certified_count_counts_active_learners_without_enrollment_rows(catalog, course_a, course_b):
    enrolled, not_enrolled, not_passed = (_add_learner(catalog, make_user()).user for _ in range(3))
    outsider = make_user()
    CatalogCourseEnrollment.objects.create(user=enrolled, catalog_course=course_a, active=True)
    _certify(enrolled, course_a)
    _certify(not_enrolled, course_a)
    _certify(not_passed, course_a, status=CertificateStatuses.notpassing)
    _certify(outsider, course_a)
    _certify(not_enrolled, course_b)

    assert _course_counts() == {course_a.pk: 2, course_b.pk: 1}


def test_course_shared_by_two_catalogs_is_counted_per_catalog(catalog, course_a):
    other_catalog = make_catalog()
    shared = _add_course(other_catalog, overview=course_a.course_overview)
    in_both, only_first = make_user(), make_user()
    _add_learner(catalog, in_both)
    _add_learner(catalog, only_first)
    _add_learner(other_catalog, in_both)
    _certify(in_both, course_a)
    _certify(only_first, course_a)

    assert _course_counts() == {course_a.pk: 2, shared.pk: 1}


def test_course_learners_count_is_the_active_learners_of_its_catalog(catalog, course_a, course_b):
    _add_learner(catalog, make_user())
    _add_learner(catalog, make_user())
    _add_learner(catalog, make_user(), removed=True)
    empty = _add_course(make_catalog())

    counts = dict(
        annotate_course_learners_count(CatalogCourse.objects.all()).values_list("pk", "catalog_learners_count")
    )

    assert counts == {course_a.pk: 2, course_b.pk: 2, empty.pk: 0}


# ---------------------------------------------------------------------------
# Catalog and partner scope
# ---------------------------------------------------------------------------

def test_catalog_certified_and_certificates_counts(catalog, course_a, course_b):
    courses = [course_a, course_b, _add_course(catalog), _add_course(catalog)]
    learners = [_add_learner(catalog, make_user()).user for _ in range(3)]
    for course in courses[:3]:
        _certify(learners[0], course)
    for course in courses[:2]:
        _certify(learners[1], course)
    _certify(learners[2], courses[3])
    empty_catalog = make_catalog()

    assert _catalog_counts() == {catalog.pk: 3, empty_catalog.pk: 0}
    assert _catalog_counts(annotate_catalog_certificates_count, "certificates_count") == {
        catalog.pk: 6,
        empty_catalog.pk: 0,
    }


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

    assert _partner_counts() == {catalog.partner.pk: 2, other_partner.pk: 0}


# ---------------------------------------------------------------------------
# Rules shared by every scope
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "status, counted",
    [
        (CertificateStatuses.downloadable, True),
        (CertificateStatuses.generating, True),
        (CertificateStatuses.notpassing, False),
        (CertificateStatuses.invalidated, False),
        (CertificateStatuses.unavailable, False),
    ],
)
def test_only_passed_statuses_are_counted(catalog, course_a, status, counted):
    learner = _add_learner(catalog, make_user())
    _certify(learner.user, course_a, status=status)
    expected = int(counted)

    assert _learner_counts()[learner.pk] == expected
    assert _course_counts()[course_a.pk] == expected
    assert _catalog_counts()[catalog.pk] == expected
    assert _catalog_counts(annotate_catalog_certificates_count, "certificates_count")[catalog.pk] == expected
    assert _partner_counts()[catalog.partner.pk] == expected


def test_removed_learner_is_not_counted_and_reactivation_restores_it(catalog, course_a, course_b):
    learner = _add_learner(catalog, make_user(), removed=True)
    _certify(learner.user, course_a)
    _certify(learner.user, course_b)

    assert _learner_counts()[learner.pk] == 0
    assert _course_counts() == {course_a.pk: 0, course_b.pk: 0}
    assert _catalog_counts()[catalog.pk] == 0
    assert _catalog_counts(annotate_catalog_certificates_count, "certificates_count")[catalog.pk] == 0
    assert _partner_counts()[catalog.partner.pk] == 0

    learner.current_invitation = make_invitation(
        catalog, user=learner.user, invite_email=learner.user.email, accepted_at=timezone.now()
    )
    learner.save()

    assert _learner_counts()[learner.pk] == 2
    assert _course_counts() == {course_a.pk: 1, course_b.pk: 1}
    assert _catalog_counts()[catalog.pk] == 1
    assert _catalog_counts(annotate_catalog_certificates_count, "certificates_count")[catalog.pk] == 2
    assert _partner_counts()[catalog.partner.pk] == 1


# ---------------------------------------------------------------------------
# compute_completion_rate
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "certificates, learners, courses, expected",
    [
        (6, 3, 4, 50.0),
        (1, 3, 1, 33.3),
        (2, 3, 1, 66.7),
        (4, 4, 1, 100.0),
        (0, 3, 4, 0.0),
        (0, 0, 4, 0.0),
        (0, 3, 0, 0.0),
        (5, 2, 2, 100.0),
        (None, 3, 4, None),
    ],
)
def test_compute_completion_rate(certificates, learners, courses, expected):
    assert compute_completion_rate(certificates, learners, courses) == expected
