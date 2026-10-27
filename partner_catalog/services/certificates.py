"""Certificate based metrics: certified learners, certificates and completion rates.

A certificate counts when its status is one of ``CertificateStatuses.PASSED_STATUSES``
and it belongs to an **active** learner of the catalog, for a course of that catalog.
Every metric is computed per catalog, so a learner or course shared by several
catalogs is counted separately in each of them.
"""

from django.db.models import Case, Count, Exists, IntegerField, OuterRef, Subquery, Value, When
from django.db.models.functions import Coalesce

from partner_catalog.edxapp_wrapper.certificates_module import certificate_statuses_model, generated_certificate_model
from partner_catalog.models import CatalogCourse, CatalogLearner

CertificateStatuses = certificate_statuses_model()
GeneratedCertificate = generated_certificate_model()


def annotate_course_certified_count(qs):
    """Annotate a CatalogCourse queryset with certified_count.

    It counts the active learners of the course's catalog that have a passed certificate
    for this course, whether or not they have a CatalogCourseEnrollment for it.
    """
    def users_qs(ref):
        return CatalogLearner.objects.filter(
            catalog__catalog_courses__pk=ref,
            active=True,
        ).values("user_id")

    def courses_qs(ref):
        return CatalogCourse.objects.filter(
            pk=ref,
        ).values("course_overview__id")

    return annotate_certified_count(qs, users_qs, courses_qs)


def annotate_course_learners_count(qs):
    """Annotate a CatalogCourse queryset with catalog_learners_count.

    It is the number of active learners of the course's catalog, the denominator of the
    course completion rate.
    """
    learners_count_sq = (
        CatalogLearner.objects.filter(
            catalog_id=OuterRef("catalog_id"),
            active=True,
        )
        .annotate(_group=Value(1))
        .values("_group")
        .annotate(cnt=Count("id"))
        .values("cnt")[:1]
    )
    return qs.annotate(
        catalog_learners_count=Coalesce(Subquery(learners_count_sq, output_field=IntegerField()), 0)
    )


def _catalog_users_qs(ref):
    return CatalogLearner.objects.filter(
        catalog_id=ref,
        active=True,
    ).values("user_id")


def _catalog_courses_qs(ref):
    return CatalogCourse.objects.filter(
        catalog_id=ref,
    ).values("course_overview__id")


def annotate_catalog_certified_count(qs):
    """Annotate a Catalog queryset with certified_count.

    It gets the count of users that are present in a catalog based on its active learners.
    The courses_qs gets the course_overview__id, of the courses related to the catalog.
    """
    return annotate_certified_count(qs, _catalog_users_qs, _catalog_courses_qs)


def annotate_catalog_certificates_count(qs):
    """Annotate a Catalog queryset with certificates_count.

    It is the number of passed certificates of the catalog's active learners in the
    catalog's courses, the numerator of the catalog completion rate.
    """
    return annotate_certified_count(
        qs, _catalog_users_qs, _catalog_courses_qs, annotation="certificates_count", distinct_users=False
    )


def annotate_partner_certified_count(qs):
    """Annotate a Partner queryset with certified_count.

    It gets the count of users that are present in a corporate partner based on the active
    learners of each of its catalogs. The courses_qs gets the course_overview__id, of the courses
    related to the corporate partner through its catalogs as well.
    """
    def users_qs(ref):
        return CatalogLearner.objects.filter(
            catalog__partner_id=ref,
            active=True,
        ).values("user_id")

    def courses_qs(ref):
        return CatalogCourse.objects.filter(
            catalog__partner_id=ref,
        ).values("course_overview__id")

    return annotate_certified_count(qs, users_qs, courses_qs)


def annotate_learner_certified_count(qs):
    """Annotate a CatalogLearner queryset with certified_count.

    It is the number of courses of the learner's catalog for which the learner has a
    passed certificate. A removed (inactive) learner counts 0.
    """
    def users_qs(ref):
        return CatalogLearner.objects.filter(
            pk=ref,
            active=True,
        ).values("user_id")

    def courses_qs(ref):
        return CatalogCourse.objects.filter(
            catalog__catalog_learners__pk=ref,
        ).values("course_overview__id")

    return annotate_certified_count(qs, users_qs, courses_qs, distinct_users=False)


def annotate_certified_count(
    qs, users_qs_factory, courses_qs_factory, annotation="certified_count", distinct_users=True
):
    """Generic annotator for certificate counts using provided users and courses subquery factories.

    It counts the certificates with a passed status for the provided courses and users
    subqueries. For each model (CatalogCourse, Catalog, CorporatePartner, CatalogLearner) it is
    necessary to provide factories that build the corresponding users and courses subqueries.

    With ``distinct_users`` it counts the distinct certified users; otherwise it counts the
    certificates themselves. The LMS keeps one certificate per (user, course), so the latter
    is the number of (user, course) pairs with a passed certificate.

    The factories receive the ``OuterRef`` expression to correlate against, because the
    subqueries are used at two different nesting depths:
    - directly inside ``Exists`` (one level deep -> ``OuterRef("pk")``)
    - inside the certificate count ``Subquery`` (two levels deep -> ``OuterRef(OuterRef("pk"))``)

    Using a single queryset built with ``OuterRef("pk")`` at both depths would make Django
    resolve the reference against the certificates queryset instead of the annotated model,
    silently matching nothing.
    """
    shallow_ref = OuterRef("pk")
    deep_ref = OuterRef(OuterRef("pk"))

    # group by a constant so the subquery returns a single row with the
    # count (grouping by model fields would count per row)
    certificates_count_sq = (
        GeneratedCertificate.objects.filter(
            course_id__in=Subquery(courses_qs_factory(deep_ref)),
            user_id__in=Subquery(users_qs_factory(deep_ref)),
            status__in=CertificateStatuses.PASSED_STATUSES,
        )
        .annotate(_group=Value(1))
        .values("_group")
        .annotate(cnt=Count("user_id", distinct=True) if distinct_users else Count("id"))
        .values("cnt")[:1]
    )

    has_users = Exists(users_qs_factory(shallow_ref))
    has_courses = Exists(courses_qs_factory(shallow_ref))

    return qs.annotate(**{
        annotation: Case(
            When(~has_users, then=Value(0)),
            When(~has_courses, then=Value(0)),
            default=Coalesce(
                Subquery(certificates_count_sq, output_field=IntegerField()), 0
            ),
            output_field=IntegerField(),
        )
    })


def compute_completion_rate(certificates: int | None, learners: int | None, courses: int | None) -> float | None:
    """Return the passed certificates as a percentage of the possible ones (learners x courses).

    It is 0.0 when there are no learners or no courses, rounded to one decimal and never
    above 100. Returns None when a count is missing (e.g. an instance that was not
    annotated by the viewset).
    """
    if None in (certificates, learners, courses):
        return None
    possible = learners * courses
    if possible <= 0:
        return 0.0
    return round(min(100.0, certificates * 100.0 / possible), 1)


def user_has_certificate(course_id, user_id):
    """Check if a user has a passed certificate for a given course.

    Args:
        course_id: The course ID to check.
        user_id: The user ID to check.

    Returns:
        bool: True if the user has a passed certificate, False otherwise.
    """
    return GeneratedCertificate.objects.filter(
        course_id=course_id,
        user_id=user_id,
        status__in=CertificateStatuses.PASSED_STATUSES,
    ).exists()
