"""
URLs for corporate_partner_access.
"""

from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

from corporate_partner_access import views

urlpatterns = [
    path("info/", views.info_view, name="corporate-access-info"),
    path("api/", include("corporate_partner_access.api.urls")),
]

urlpatterns += [
    path('schema/', SpectacularAPIView.as_view(), name='schema'),
    path('swagger/', SpectacularSwaggerView.as_view(url_name='corporate_partner_access:schema'), name='swagger-ui'),
    path('redoc/', SpectacularRedocView.as_view(url_name='corporate_partner_access:schema'), name='redoc-ui'),
]
