"""Corporate Partner Access API v0 Views."""

from django_filters.rest_framework import DjangoFilterBackend
from edx_rest_framework_extensions.permissions import IsAuthenticated
from rest_framework import filters, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from corporate_partner_access.api.v0.serializers import (
    CatalogCourseSerializer,
    CatalogEmailRegexSerializer,
    CatalogLearnerSerializer,
    CorporatePartnerCatalogSerializer,
    CorporatePartnerSerializer,
)
from corporate_partner_access.models import (
    CorporatePartner,
    CorporatePartnerCatalog,
    CorporatePartnerCatalogCourse,
    CorporatePartnerCatalogEmailRegex,
    CorporatePartnerCatalogLearner,
)


class CorporatePartnerViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Corporate Partner data.
    Provides access to corporate partner information.
    """

    queryset = CorporatePartner.objects.all()
    serializer_class = CorporatePartnerSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["code", "name"]
    ordering_fields = ["name", "code", "id"]
    ordering = ["name"]


class CorporatePartnerCatalogViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Corporate Partner Catalog data.
    Provides access to corporate partner catalog information.
    """

    queryset = CorporatePartnerCatalog.objects.all()  # pylint: disable=E1111
    serializer_class = CorporatePartnerCatalogSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["corporate_partner", "is_public"]
    search_fields = ["name", "slug"]
    ordering_fields = ["name", "id", "available_start_date", "available_end_date"]
    ordering = ["name"]

    @action(detail=True, methods=["get"], url_path="learners")
    def learners(self, request, **kwargs):
        """Return learners for a catalog."""
        catalog = self.get_object()
        qs = CorporatePartnerCatalogLearner.objects.filter(catalog=catalog).only(
            "active", "user"
        )

        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = CatalogLearnerSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = CatalogLearnerSerializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"], url_path="courses")
    def courses(self, request, **kwargs):
        """Return courses for a catalog."""
        catalog = self.get_object()
        qs = CorporatePartnerCatalogCourse.objects.filter(
            catalog=catalog
        ).select_related("course_overview")

        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = CatalogCourseSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = CatalogCourseSerializer(qs, many=True)
        return Response(serializer.data)


class CorporatePartnerCatalogLearnerViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Corporate Partner Catalog Learner data.
    Provides access to corporate partner catalog learner information.
    """

    queryset = CorporatePartnerCatalogLearner.objects.select_related("catalog", "user")
    serializer_class = CatalogLearnerSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["catalog", "active", "user"]
    search_fields = ["user__username", "user__email"]
    ordering_fields = ["id", "user_id"]
    ordering = ["id"]


class CorporatePartnerCatalogCourseViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Corporate Partner Catalog Course data.
    Provides access to corporate partner catalog course information.
    """

    queryset = CorporatePartnerCatalogCourse.objects.select_related(
        "course_overview", "catalog"
    )
    serializer_class = CatalogCourseSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["catalog", "course_overview"]
    search_fields = ["course_overview__display_name"]
    ordering_fields = ["id", "position"]
    ordering = ["position"]


class CorporatePartnerCatalogEmailRegexViewSet(viewsets.ModelViewSet):
    """ViewSet for catalog email regex patterns."""

    queryset = CorporatePartnerCatalogEmailRegex.objects.all()
    serializer_class = CatalogEmailRegexSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["catalog"]
