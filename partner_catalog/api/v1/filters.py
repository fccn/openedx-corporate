"""Custom filters for Partner Catalog API v1."""

import django_filters

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
