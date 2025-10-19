"""Partner Catalog API v1 Views."""

from celery.result import AsyncResult
from django.db.models import Count, Q
from django.db.models.functions import Coalesce
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response

from partner_catalog.api.v1 import tasks as partner_tasks
from partner_catalog.api.v1.mixins import InjectNestedFKMixin
from partner_catalog.api.v1.schemas import bulk_status_learner_schema, bulk_upload_learner_schema
from partner_catalog.api.v1.serializers import (
    CatalogCourseEnrollmentSerializer,
    CatalogCourseSerializer,
    CatalogEmailRegexSerializer,
    CatalogLearnerSerializer,
    CorporatePartnerCatalogSerializer,
    CorporatePartnerSerializer,
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
    annotate_partner_certified_count,
)


class CorporatePartnerViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for Corporate Partner data.
    Provides access to corporate partner information.
    """

    queryset = Partner.objects.all()
    serializer_class = CorporatePartnerSerializer
    permission_classes = [IsPartnerCatalogManager]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["code", "name"]
    ordering_fields = ["name", "code", "id"]
    ordering = ["name"]

    def get_queryset(self):
        """
        Limit non-staff users to partners where they are active members.
        Staff/superusers see all.
        """
        qs = self.queryset
        user = self.request.user
        if not (user.is_staff or user.is_superuser):
            managed_partner_ids = (
                PartnerCatalog.objects.filter(
                    catalog_managers__user=user,
                    catalog_managers__active=True,
                )
                .values_list("corporate_partner_id", flat=True)
                .distinct()
            )
            qs = qs.filter(id__in=managed_partner_ids)

        qs = qs.annotate(
            catalogs_count=Count("catalogs", distinct=True),
            courses_count=Count("catalogs__courses", distinct=True),
            total_enrollments=Coalesce(
                Count(
                    "catalogs__catalog_courses__enrollments",
                    filter=Q(catalogs__catalog_courses__enrollments__active=True),
                    distinct=True,
                ),
                0,
            ),
        )
        qs = annotate_partner_certified_count(qs)
        return qs


class CorporatePartnerCatalogViewSet(
    InjectNestedFKMixin, viewsets.ModelViewSet
):
    """
    ViewSet for Corporate Partner Catalog data.
    Provides access to corporate partner catalog information.
    """

    # pylint: disable=E1111
    queryset = PartnerCatalog.objects.all()
    serializer_class = CorporatePartnerCatalogSerializer
    permission_classes = [IsPartnerCatalogManager]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["corporate_partner", "is_public"]
    search_fields = ["name", "slug"]
    ordering_fields = ["name", "id", "available_start_date", "available_end_date"]
    ordering = ["name"]

    # Mixin config
    nested_lookup_kwarg = "partner_pk"
    target_field_name = "corporate_partner"

    def get_queryset(self):
        """Limit catalogs to those the user manages or views; staff see all."""
        qs = self.queryset
        user = self.request.user
        partner_pk = self.kwargs.get("partner_pk")
        if partner_pk:
            qs = qs.filter(corporate_partner_id=partner_pk)

        if not (user.is_staff or user.is_superuser):
            qs = qs.filter(
                catalog_managers__user=user,
                catalog_managers__active=True,
            ).distinct()

        qs = qs.annotate(
            courses_count=Count("courses", distinct=True),
            total_enrollments=Coalesce(
                Count(
                    "catalog_courses__enrollments",
                    filter=Q(catalog_courses__enrollments__active=True),
                    distinct=True,
                ),
                0,
            ),
        )
        qs = annotate_catalog_certified_count(qs)
        return qs


class CorporatePartnerCatalogLearnerViewSet(InjectNestedFKMixin, viewsets.ModelViewSet):
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
    ordering_fields = ["id", "user_id"]
    ordering = ["id"]

    # Mixin config
    nested_lookup_kwarg = "catalog_pk"
    target_field_name = "catalog_id"

    def get_queryset(self):
        """Get the queryset for catalog learners."""
        qs = self.queryset
        catalog_pk = self.kwargs.get("catalog_pk")
        return qs.filter(catalog_id=catalog_pk) if catalog_pk else qs

    @bulk_upload_learner_schema
    @action(
        detail=False,
        methods=["post"],
        url_path="bulk",
        parser_classes=[MultiPartParser],
    )
    def bulk(
        self, request, partner_pk=None, catalog_pk=None
    ):  # pylint: disable=unused-argument
        """
        Bulk upload learners to a catalog via CSV file (async).
        CSV columns: username (or email), optional active (defaults to True)
        Returns a Celery task ID for status tracking.
        """
        file = request.FILES.get("file")
        if not file:
            return Response(
                {"detail": "No file uploaded."}, status=status.HTTP_400_BAD_REQUEST
            )
        # Save file content to pass to Celery (as string)
        csv_content = file.read().decode(request.encoding or "utf-8")
        # Enqueue Celery task
        task = partner_tasks.bulk_upload_learners.delay(
            csv_content=csv_content,
            catalog_id=catalog_pk,
        )
        return Response(
            {"task_id": task.id, "status": "processing"},
            status=status.HTTP_202_ACCEPTED,
        )

    @bulk_status_learner_schema
    @action(
        detail=False,
        methods=["get"],
        url_path="bulk_status",
    )
    def bulk_status(
        self, request, partner_pk=None, catalog_pk=None
    ):  # pylint: disable=unused-argument
        """
        Check the status of a bulk upload task by task_id.
        Query parameter: task_id
        """
        task_id = request.query_params.get("task_id")
        if not task_id:
            return Response(
                {"detail": "task_id parameter is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        task_result = AsyncResult(task_id)
        response_data = {
            "task_id": task_id,
            "status": task_result.status,
        }
        if task_result.ready():
            if task_result.successful():
                response_data["result"] = task_result.result
            else:
                response_data["error"] = str(task_result.info)
        return Response(response_data, status=status.HTTP_200_OK)


class CorporatePartnerCatalogCourseViewSet(
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
        qs = qs.filter(catalog__corporate_partner_id=partner_pk) if partner_pk else qs

        qs = qs.annotate(
            enrollments_count=Count(
                "enrollments",
                filter=Q(enrollments__active=True),
                distinct=True,
            )
        )
        qs = annotate_course_certified_count(qs)
        return qs


class CorporatePartnerCatalogEmailRegexViewSet(
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
