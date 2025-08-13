"""Corporate Partner Access API v0 Views."""

from edx_rest_framework_extensions.permissions import IsAuthenticated
from rest_framework import viewsets
from rest_framework.decorators import action

from corporate_partner_access.api.v0.serializers import (
    CatalogCourseSerializer,
    CatalogLearnerSerializer,
    CorporatePartnerCatalogSerializer,
    CorporatePartnerSerializer,
)
from corporate_partner_access.models import (
    CorporatePartner,
    CorporatePartnerCatalog,
    CorporatePartnerCatalogCourse,
    CorporatePartnerCatalogLearner,
)


class CorporatePartnerViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Corporate Partner data.
    Provides read-only access to corporate partner information.
    """

    queryset = CorporatePartner.objects.all()
    serializer_class = CorporatePartnerSerializer
    permission_classes = [IsAuthenticated]


class CorporatePartnerCatalogViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Corporate Partner Catalog data.
    Provides read-only access to corporate partner catalog information.
    """

    queryset = CorporatePartnerCatalog.objects.all()  # pylint: disable=E1111
    serializer_class = CorporatePartnerCatalogSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=True, methods=["get"], url_path="learners")
    def learners(self, request, **kwargs):
        """Return learners for a catalog."""
        catalog = self.get_object()
        qs = CorporatePartnerCatalogLearner.objects.filter(catalog=catalog).only(
            "active", "user"
        )

        page = self.paginate_queryset(qs)
        serializer = CatalogLearnerSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @action(detail=True, methods=["get"], url_path="courses")
    def courses(self, request, **kwargs):
        """Return courses for a catalog."""
        catalog = self.get_object()
        qs = CorporatePartnerCatalogCourse.objects.filter(
            catalog=catalog
        ).select_related("course_overview")

        page = self.paginate_queryset(qs)
        serializer = CatalogCourseSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)
