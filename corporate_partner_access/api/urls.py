"""URLs for the Corporate Partner Access API."""

from django.urls import include, path

urlpatterns = [
    path("v1/", include(("corporate_partner_access.api.v1.urls", "v1"), namespace="v1")),
]
