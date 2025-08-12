"""URLs for the Corporate Partner Access API."""

from django.urls import include, path

urlpatterns = [
    path("v0/", include(("corporate_partner_access.api.v0.urls", "v0"), namespace="v0")),
]
