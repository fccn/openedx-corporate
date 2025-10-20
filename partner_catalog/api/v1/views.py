"""Partner Catalog API v1 Views."""

from django.db.models import Count, OuterRef, Q, Subquery
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, viewsets

from partner_catalog.api.v1.filters import PartnerFilter
from partner_catalog.api.v1.mixins import InjectNestedFKMixin
from partner_catalog.api.v1.serializers import (
    CatalogCourseEnrollmentSerializer,
    CatalogCourseSerializer,
    CatalogEmailRegexSerializer,
    CatalogLearnerSerializer,
    PartnerCatalogSerializer,
    PartnerSerializer,
)
from partner_catalog.models import (
    CatalogCourse,
    CatalogCourseEnrollment,
    CatalogEmailRegex,
    CatalogLearner,
    Partner,
    PartnerCatalog,
)
from partner_catalog.permissions import IsPartnerCatalogManager
from partner_catalog.services.certificates import (
    annotate_catalog_certified_count,
    annotate_course_certified_count,
    annotate_learner_certified_count,
    annotate_partner_certified_count,
)


class PartnerViewset(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for Corporate Partner data.
    Provides access to corporate partner information.
    """

    queryset = Partner.objects.select_related("organization").all()
    serializer_class = PartnerSerializer
    permission_classes = [IsPartnerCatalogManager]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = PartnerFilter
    search_fields = ["organization__short_name", "organization__name"]
    ordering_fields = ["organization__name", "organization__short_name", "id"]
    ordering = ["organization__short_name"]

    def get_queryset(self):
        """
        Limit non-staff users to partners where they are active members.
        Staff/superusers see all.
        """
        qs = self.queryset
        qs = qs.annotate(
            catalogs_count=Count("catalogs", distinct=True),
            courses_count=Count("catalogs__catalog_courses", distinct=True),
            learners_count=Count("catalogs__catalog_learners", distinct=True)
        )
        qs = annotate_partner_certified_count(qs)
        return qs


class PartnerCatalogViewSet(
    InjectNestedFKMixin, viewsets.ModelViewSet
):
    """
    ViewSet for Corporate Partner Catalog data.
    Provides access to corporate partner catalog information.
    """

    # pylint: disable=E1111
    queryset = PartnerCatalog.objects.all()
    serializer_class = PartnerCatalogSerializer
    permission_classes = [IsPartnerCatalogManager]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["partner"]
    search_fields = ["name", "slug"]
    ordering_fields = ["name", "id", "available_start_date", "available_end_date"]
    ordering = ["name"]

    # Mixin config
    nested_lookup_kwarg = "partner_pk"
    target_field_name = "partner"

    def get_queryset(self):
        """Limit catalogs to those the user manages or views; staff see all."""
        qs = self.queryset
        user = self.request.user
        partner_pk = self.kwargs.get("partner_pk")
        if partner_pk:
            qs = qs.filter(partner_id=partner_pk)

        if not (user.is_staff or user.is_superuser):
            qs = qs.filter(
                catalog_managers__user=user,
                catalog_managers__active=True,
            ).distinct()

        qs = qs.annotate(
            courses_count=Count("catalog_courses", distinct=True),
            total_enrollments=Count("catalog_learners", distinct=True),
        )
        qs = annotate_catalog_certified_count(qs)
        return qs


class CatalogLearnerViewset(InjectNestedFKMixin, viewsets.ModelViewSet):
    """
    ViewSet for Corporate Partner Catalog Learner data.
    Provides access to corporate partner catalog learner information.
    """

    queryset = CatalogLearner.objects.select_related("catalog", "user")
    serializer_class = CatalogLearnerSerializer
    permission_classes = [IsPartnerCatalogManager]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["catalog", "active", "user"]
    search_fields = ["user__username", "user__email"]
    ordering_fields = [
        "id",
        "user_id",
        "accepted_at",
        "removed_at",
        "active",
    ]
    ordering = ["id"]

    # Mixin config
    nested_lookup_kwarg = "catalog_pk"
    target_field_name = "catalog_id"

    def get_queryset(self):
        """Get the queryset for catalog learners with enrollment counts."""
        qs = self.queryset
        catalog_pk = self.kwargs.get("catalog_pk")

        if catalog_pk:
            qs = qs.filter(catalog_id=catalog_pk)

        enrollments_subquery = CatalogCourseEnrollment.objects.filter(
            user_id=OuterRef("user_id"),
            catalog_course__catalog_id=OuterRef("catalog_id"),
            active=True,
        ).values("user_id").annotate(count=Count("id")).values("count")

        qs = qs.annotate(enrollments_count=Subquery(enrollments_subquery))
        qs = annotate_learner_certified_count(qs)
        return qs


class CatalogCourseViewSet(
    InjectNestedFKMixin, viewsets.ModelViewSet,
):
    """
    ViewSet for Corporate Partner Catalog Course data.
    Provides access to corporate partner catalog course information.
    """

    queryset = CatalogCourse.objects.select_related(
        "course_overview", "catalog"
    )
    serializer_class = CatalogCourseSerializer
    permission_classes = [IsPartnerCatalogManager]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["catalog", "course_overview"]
    search_fields = ["course_overview__display_name"]
    ordering_fields = ["id", "position"]
    ordering = ["position"]

    # Mixin config
    nested_lookup_kwarg = "catalog_pk"
    target_field_name = "catalog_id"

    def get_queryset(self):
        """Get the queryset for catalog courses."""
        qs = self.queryset

        catalog_pk = self.kwargs.get("catalog_pk")
        qs = qs.filter(catalog_id=catalog_pk) if catalog_pk else qs

        partner_pk = self.kwargs.get("partner_pk")
        qs = qs.filter(catalog__partner_id=partner_pk) if partner_pk else qs

        qs = qs.annotate(
            enrollments_count=Count(
                "enrollments",
                filter=Q(enrollments__active=True),
                distinct=True,
            )
        )
        qs = annotate_course_certified_count(qs)
        return qs


class CatalogEmailRegexViewSet(
    InjectNestedFKMixin, viewsets.ModelViewSet
):
    """ViewSet for catalog email regex patterns."""

    queryset = CatalogEmailRegex.objects.all()
    serializer_class = CatalogEmailRegexSerializer
    permission_classes = [IsPartnerCatalogManager]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["catalog"]

    # Mixin config
    nested_lookup_kwarg = "catalog_pk"
    target_field_name = "catalog_id"

    def get_queryset(self):
        """Get the queryset for catalog email regex patterns."""
        qs = self.queryset
        catalog_pk = self.kwargs.get("catalog_pk")
        return qs.filter(catalog_id=catalog_pk) if catalog_pk else qs


class CatalogCourseEnrollmentViewSet(
    viewsets.ReadOnlyModelViewSet, InjectNestedFKMixin
):
    """
    ViewSet for Catalog Course Enrollments.
    Provides read-only access to enrollments in a specific catalog course.
    """

    queryset = CatalogCourseEnrollment.objects.select_related("user", "catalog_course")
    serializer_class = CatalogCourseEnrollmentSerializer
    permission_classes = [IsPartnerCatalogManager]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["catalog_course", "user"]
    search_fields = ["user__username", "user__email"]
    ordering_fields = ["id", "user_id"]
    ordering = ["id"]

    # Mixin config
    nested_lookup_kwarg = "course_pk"
    target_field_name = "catalog_course_id"

    def get_queryset(self):
        """Get the queryset for catalog course enrollments."""
        qs = self.queryset
        course_pk = self.kwargs.get("course_pk")
        return qs.filter(catalog_course_id=course_pk) if course_pk else qs
