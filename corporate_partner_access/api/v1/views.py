"""Corporate Partner Access API v1 Views."""

from django_filters.rest_framework import DjangoFilterBackend
from edx_rest_framework_extensions.permissions import IsAuthenticated
from rest_framework import filters, viewsets

from corporate_partner_access.api.v1.serializers import (
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


class InjectNestedFKMixin:
    """Generic mixin to inject/override a nested FK id from URL kwargs into serializer data.

    Subclasses set:
      nested_lookup_kwarg: name of kwarg added by nested router.
      target_field_name: serializer field to populate.
    """

    nested_lookup_kwarg = None
    target_field_name = None

    def get_serializer(self, *args, **kwargs):
        """Inject the nested FK id into serializer data if applicable."""
        if (
            "data" in kwargs
            and self.nested_lookup_kwarg
            and self.target_field_name
            and self.kwargs.get(self.nested_lookup_kwarg)
        ):
            data = kwargs["data"]
            if hasattr(data, "copy"):
                data = data.copy()
            data[self.target_field_name] = self.kwargs[self.nested_lookup_kwarg]
            kwargs["data"] = data
        return super().get_serializer(*args, **kwargs)


class CorporatePartnerCatalogViewSet(InjectNestedFKMixin, viewsets.ModelViewSet):
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

    # Mixin config
    nested_lookup_kwarg = "partner_pk"
    target_field_name = "corporate_partner"

    def get_queryset(self):
        """Get the queryset for corporate partner catalogs."""
        qs = super().get_queryset()
        partner_pk = self.kwargs.get("partner_pk")
        if partner_pk:
            qs = qs.filter(corporate_partner_id=partner_pk)
        return qs


class CorporatePartnerCatalogLearnerViewSet(InjectNestedFKMixin, viewsets.ModelViewSet):
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

    # Mixin config
    nested_lookup_kwarg = "catalog_pk"
    target_field_name = "catalog_id"

    def get_queryset(self):
        """Get the queryset for catalog learners."""
        qs = self.queryset
        catalog_pk = self.kwargs.get("catalog_pk")
        return qs.filter(catalog_id=catalog_pk) if catalog_pk else qs


class CorporatePartnerCatalogCourseViewSet(InjectNestedFKMixin, viewsets.ModelViewSet):
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

    # Mixin config
    nested_lookup_kwarg = "catalog_pk"
    target_field_name = "catalog_id"

    def get_queryset(self):
        """Get the queryset for catalog courses."""
        qs = self.queryset
        catalog_pk = self.kwargs.get("catalog_pk")
        return qs.filter(catalog_id=catalog_pk) if catalog_pk else qs


class CorporatePartnerCatalogEmailRegexViewSet(
    InjectNestedFKMixin, viewsets.ModelViewSet
):
    """ViewSet for catalog email regex patterns."""

    queryset = CorporatePartnerCatalogEmailRegex.objects.all()
    serializer_class = CatalogEmailRegexSerializer
    permission_classes = [IsAuthenticated]
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
