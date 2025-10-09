"""URLs for the Partner Catalog API."""

from django.urls import include, path

urlpatterns = [
    path("v1/", include(("partner_catalog.api.v1.urls", "v1"), namespace="v1")),
]
