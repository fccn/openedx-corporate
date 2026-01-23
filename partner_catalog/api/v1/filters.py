"""Custom filters for Partner Catalog API v1."""

import django_filters
from rest_framework.filters import OrderingFilter

from partner_catalog.models import Partner, PartnerCatalog


class PartnerFilter(django_filters.FilterSet):
    """
    Custom filters for Partner model.

    Allows filtering by organization fields with shorter parameter names:
    - slug: filters by organization__short_name
    - name: filters by organization__name (exact or icontains)
    """

    slug = django_filters.CharFilter(
        field_name="organization__short_name",
        lookup_expr="iexact",
        help_text="Filter by organization short name (case-insensitive)",
    )

    name = django_filters.CharFilter(
        field_name="organization__name",
        lookup_expr="icontains",
        help_text="Filter by organization name (case-insensitive, partial match)",
    )

    class Meta:
        model = Partner
        fields = [
            "slug",
            "name",
        ]


class PartnerCatalogFilter(django_filters.FilterSet):
    """
    Custom filters for PartnerCatalog model.

    Allows filtering by partner ID:
    - partner: filters by partner__id
    """

    partner = django_filters.NumberFilter(
        field_name="partner__id",
        help_text="Filter by partner ID",
    )

    class Meta:
        model = PartnerCatalog
        fields = [
            "partner",
        ]


class CatalogCourseOrderingFilter(OrderingFilter):
    """
    Ordering filter for CatalogCourse model.

    Allows ordering of catalog courses using custom parameter names mapped to
    annotated/model fields such as course start/end, enrollment periods,
    enrollments count, and certified learners count.
    """

    ordering_map = {
        # Course dates
        "course_start": "course_overview__start",
        "course_end": "course_overview__end",

        # Enrollment dates
        "enrollment_start": "course_overview__enrollment_start",
        "enrollment_end": "course_overview__enrollment_end",

        # Metrics
        "enrollments": "enrollments_count",
        "certified": "certified_count",

        # Base fields
        "position": "position",
        "id": "id",
    }

    def get_ordering(self, request, queryset, view):
        """
        Return the list of ordering fields for the specified request.

        Uses the custom ordering_map to translate API ordering parameter names
        (e.g., "course_start") into the underlying annotated/model field names
        (e.g., "course_overview__start"). Handles support for descending order
        (leading "-") and ignores any ordering keys not present in ordering_map.
        """

        params = request.query_params.get(self.ordering_param)
        if not params:
            return self.get_default_ordering(view)

        fields = [p.strip() for p in params.split(",")]
        ordering = []

        for field in fields:
            desc = field.startswith("-")
            key = field[1:] if desc else field
            mapped = self.ordering_map.get(key)

            if mapped:
                ordering.append(f"-{mapped}" if desc else mapped)

        return ordering
