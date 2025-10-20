"""Services to annotate certified users counts for catalogs and courses."""

from django.db.models import Case, Count, Exists, IntegerField, OuterRef, Subquery, Value, When
from django.db.models.functions import Coalesce

from partner_catalog.edxapp_wrapper.certificates_module import certificate_statuses_model, generated_certificate_model
from partner_catalog.models import (
    CatalogCourseEnrollment,
    CorporatePartnerCatalogCourse,
    CorporatePartnerCatalogLearner,
)

CertificateStatuses = certificate_statuses_model()
GeneratedCertificate = generated_certificate_model()


def annotate_course_certified_count(qs):
    """Annotate a CatalogCourse queryset with certified_count.

    It reuses the generic helper by providing:
    - users_qs: active enrolled users for this course
    - courses_qs: the single course_overview id for this row
    """
    users_qs = (
        CatalogCourseEnrollment.objects.filter(
            catalog_course_id=OuterRef("pk"),
            active=True
        ).values("user_id")
    )
    courses_qs = (
        CorporatePartnerCatalogCourse.objects.filter(
            pk=OuterRef("pk")
        ).values("course_overview__id")
    )
    return annotate_certified_count(qs, users_qs, courses_qs)


def annotate_catalog_certified_count(qs):
    """Annotate a Catalog queryset with certified_count.

    It gets the count of users that are present in a catalog based on its active learners.
    The courses_qs gets the course_overview__id, of the courses related to the catalog.
    """
    users_qs = CorporatePartnerCatalogLearner.objects.filter(
        catalog_id=OuterRef("pk"),
        active=True,
    ).values("user_id")
    courses_qs = CorporatePartnerCatalogCourse.objects.filter(
        catalog_id=OuterRef("pk"),
    ).values("course_overview__id")

    annotated = annotate_certified_count(qs, users_qs, courses_qs)
    return annotated


def annotate_partner_certified_count(qs):
    """Annotate a CorporatePartner queryset with certified_count.

    It gets the count of users that are present in a corporate partner based on the active
    learners of each of its catalogs. The courses_qs gets the course_overview__id, of the courses
    related to the corporate partner through its catalogs as well.
    """
    users_qs = CorporatePartnerCatalogLearner.objects.filter(
        catalog__corporate_partner_id=OuterRef("pk"),
        active=True,
    ).values("user_id")
    courses_qs = CorporatePartnerCatalogCourse.objects.filter(
        catalog__corporate_partner_id=OuterRef("pk"),
    ).values("course_overview__id")

    annotated = annotate_certified_count(qs, users_qs, courses_qs)
    return annotated


def annotate_certified_count(qs, users_qs, courses_qs):
    """Generic annotator for certified_count using provided users and courses subqueries.

    It counts the distinct users that have a certificate with a passed status for the provided
    courses and users subqueries. For each model (CatalogCourse, Catalog, CorporatePartner) is
    necessary to provide the corresponding users and courses subqueries.
    """

    certificates_count_sq = (
        GeneratedCertificate.objects.filter(
            course_id__in=Subquery(courses_qs),
            user_id__in=Subquery(users_qs),
            status__in=CertificateStatuses.PASSED_STATUSES,
        )
        .values()
        .annotate(cnt=Count("user_id", distinct=True))
        .values("cnt")[:1]
    )

    has_users = Exists(users_qs)
    has_courses = Exists(courses_qs)

    return qs.annotate(
        certified_count=Case(
            When(~has_users, then=Value(0)),
            When(~has_courses, then=Value(0)),
            default=Coalesce(
                Subquery(certificates_count_sq, output_field=IntegerField()), 0
            ),
            output_field=IntegerField(),
        )
    )
